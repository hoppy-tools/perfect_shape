import atexit
import bpy
import bmesh

from functools import lru_cache

from bpy.app.handlers import persistent
from mathutils import Vector, Matrix

from perfect_shape.shaper import Shape
from perfect_shape.previews import PREVIEW_MAX_POINTS, render_preview


@persistent
def update_handler(scene, graph):
    if AppHelper.execute_operator_func is not None:
        AppHelper.execute_operator_func(scene, graph)
        AppHelper.execute_operator_func = None


class AppHelper:
    __slots__ = tuple()

    action_in_change_timer = None
    execute_operator_func = None
    active_tool_on_poll = False

    @classmethod
    def _check_tool_action(cls):
        wm = bpy.context.window_manager
        editable = wm.operators and wm.operators[-1].bl_idname == "PERFECT_SHAPE_OT_perfect_shape"
        if not editable:
            bpy.context.scene.perfect_shape_tool_settings.action = "NEW"
            cls.action_in_change_timer = None
            return None
        return 0

    @classmethod
    def check_tool_action(cls):
        if cls.action_in_change_timer is None:
            bpy.app.timers.register(cls._check_tool_action, first_interval=0)
            cls.action_in_change_timer = True

    @classmethod
    def get_perfect_shape_operator(cls):
        wm = bpy.context.window_manager
        if not wm.operators:
            return None
        op = wm.operators[-1]
        if op.bl_idname != "PERFECT_SHAPE_OT_perfect_shape":
            return None
        return op

    @classmethod
    def execute_perfect_shape_operator(cls, rotation, shift, span):
        def _execute_operator(scene, graph):
            op = cls.get_perfect_shape_operator()
            if op is None:
                return False

            op.rotation = rotation
            op.shift = shift
            op.span = span
            op.execute(bpy.context)
            return True

        if cls.execute_operator_func is None:
            cls.execute_operator_func = _execute_operator


class ShapeHelper:
    __slots__ = tuple()

    _object = None
    _object_bm = None
    _object_selected_verts = []
    _object_selected_edges = []
    _object_selected_faces = []

    _pattern = None
    _pattern_bm = None

    _shape = None
    _shape_key = None
    _shape_preview = None
    _shape_best_shifts = []
    _shape_best_shift_cursor = 0

    _shape_last_props = ()
    _shape_last_rotation = 0.0

    _previews_shapes = {}

    max_points = None

    @classmethod
    def clear_cache(cls):
        cls.get_object_selected_avr_normal.cache_clear()
        cls.get_object_selected_avr_position.cache_clear()

    @classmethod
    def prepare_object(cls, object):
        cls._object = object
        cls._object_bm = bmesh.from_edit_mesh(cls._object.data)
        cls.refresh_selection()

    @classmethod
    def refresh_selection(cls):
        cls._object_selected_verts = [v for v in cls._object_bm.verts if v.select]
        cls._object_selected_edges = [e for e in cls._object_bm.edges if e.select]
        cls._object_selected_faces = [f for f in cls._object_bm.faces if f.select]

        # Cache data for transform orientation
        if cls._object_selected_verts:
            cls.get_object_selected_avr_position()
            cls.get_object_selected_avr_normal()

    @classmethod
    @lru_cache(maxsize=1)
    def get_object_selected_avr_position(cls):
        verts_co_average = Vector()
        for v in cls._object_selected_verts:
            verts_co_average += v.co
        return verts_co_average / len(cls._object_selected_verts)

    @classmethod
    @lru_cache(maxsize=1)
    def get_object_selected_avr_normal(cls):
        avr_normal = Vector()
        geometry = cls._object_selected_faces if cls._object_selected_faces else cls._object_selected_verts
        for v in geometry:
            avr_normal += v.normal
        return avr_normal / len(geometry)

    @classmethod
    def get_object_shape_projection_matrix(cls):
        op = AppHelper.get_perfect_shape_operator()
        position = cls.get_object_selected_avr_position()
        matrix_world = cls.get_object_matrix_world().copy()

        if op.projection == "N":
            direction = ShapeHelper.get_object_selected_avr_normal().copy()
        else:
            directions = {"X": Vector((1.0, 0.0, 0.0)),
                          "Y": Vector((0.0, 1.0, 0.0)),
                          "Z": Vector((0.0, 0.0, 1.0))}
            direction = directions[op.projection]
            if bpy.context.scene.transform_orientation_slots[0].type == "GLOBAL":
                direction = matrix_world.to_3x3().normalized().inverted() @ direction
        if op.projection_invert:
            direction *= -1

        matrix_translation = Matrix.Translation(position)
        matrix_rotation = direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()

        return matrix_world @ matrix_translation @ matrix_rotation

    @classmethod
    def get_object_matrix_world(cls):
        return cls._object.matrix_world

    @classmethod
    def initialized(cls):
        return cls._shape is not None

    @classmethod
    def generate_shapes(cls, shift, span, rotation, generic_params=None, shape_key=None, main_key=None,
                        exclude_key=None, points_distribution="SEQUENCE", points_distribution_smooth=False):
        points_count = len(cls._object_selected_verts)
        if points_count < 3:
            points_count = 8

        target_points_count = len(cls._object_selected_verts)
        if target_points_count < 3:
            target_points_count = 8

        shape_props = (shift, span, generic_params, shape_key, points_distribution, points_distribution_smooth)

        if cls._shape_last_props == shape_props:
            if cls._shape_last_rotation == rotation:
                return False
            return True

        shapes = {"CIRCLE":     lambda m: Shape.Circle(points_count, span, shift, rotation, max_points=m),
                  "RECTANGLE":  lambda m: Shape.Rectangle(points_count, generic_params, span, shift, rotation,
                                                          max_points=m),
                  "OBJECT":     lambda m: Shape.Object(points_count, span, shift, rotation,
                                                       max_points=m,
                                                       target_points_count=target_points_count,
                                                       points_distribution=points_distribution,
                                                       points_distribution_smooth=points_distribution_smooth)}

        if shape_key is not None:
            cls._previews_shapes[shape_key] = shapes[shape_key](PREVIEW_MAX_POINTS)
            cls._shape_preview = cls._shape = cls._previews_shapes[shape_key]
            if points_count + span >= PREVIEW_MAX_POINTS:
                cls._shape = shapes[shape_key](None)
        else:
            for key, func in shapes.items():
                if exclude_key == key:
                    continue
                cls._previews_shapes[key] = func(PREVIEW_MAX_POINTS)
                if main_key == key:
                    cls._shape = func(None) if points_count + span >= PREVIEW_MAX_POINTS else cls._previews_shapes[key]

        if points_count + span >= PREVIEW_MAX_POINTS:
            cls.max_points = PREVIEW_MAX_POINTS
        else:
            cls.max_points = None

        cls._shape_last_props = shape_props
        cls._shape_last_rotation = rotation
        return True

    @classmethod
    def render_previews(cls, shape_key=None, rotation=None):
        if shape_key is not None:
            render_preview("shape_types", shape_key, cls._previews_shapes[shape_key], rotation)
        else:
            for shape_key in ("CIRCLE", "RECTANGLE", "OBJECT"):
                render_preview("shape_types", shape_key, cls._previews_shapes[shape_key], rotation)

    @classmethod
    def get_shape(cls):
        return cls._shape

    @classmethod
    def calc_best_shifts(cls):
        pass

    @classmethod
    def get_best_shifts(cls):
        if not cls._shape_best_shifts:
            cls._shape_best_shifts.extend(cls._shape.calc_best_shifts())
            cls._shape_best_shift_cursor = 0
        return cls._shape_best_shifts

    @classmethod
    def clear_best_shifts(cls):
        cls._shape_best_shifts.clear()

    @classmethod
    def get_next_best_shift(cls):
        best_shifts = cls.get_best_shifts()
        best_shift = best_shifts[cls._shape_best_shift_cursor % len(best_shifts)]
        cls._shape_best_shift_cursor += 1
        return best_shift

    @classmethod
    def clear(cls):
        cls.clear_cache()

        cls._object = None
        cls._object_bm = None
        cls._object_selected_verts = None
        cls._object_selected_edges = None
        cls._object_selected_faces = None

        cls._pattern = None
        cls._pattern_bm = None

        cls._shape = None
        cls._shape_preview = None
        cls._previews_shapes = None

    @classmethod
    def get_points_count(cls):
        return len(cls._object_selected_verts)

    @classmethod
    def get_final_points_cout(cls):
        return cls.get_points_count() + cls._shape.span


def register():
    bpy.app.handlers.depsgraph_update_post.append(update_handler)


def unregister():
    pass

atexit.register(ShapeHelper.clear)
