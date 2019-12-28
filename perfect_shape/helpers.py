import atexit
import bpy
import functools
from .shaper import Shape
from .previews import PREVIEW_MAX_POINTS, render_preview
from bpy.app.handlers import persistent


@persistent
def update_handler(scene, graph):
    if AppHelper.action_in_change_func is not None:
        result_ok = AppHelper.action_in_change_func(scene, graph)
        if result_ok:
            AppHelper.action_in_change_func = None

    if AppHelper.execute_operator_func is not None:
        AppHelper.execute_operator_func(scene, graph)
        AppHelper.execute_operator_func = None


class AppHelper:
    action_in_change_func = None
    execute_operator_func = None

    @classmethod
    def _check_tool_action(cls, scene, graph):
        wm = bpy.context.window_manager
        if len(wm.operators) < 2:
            editable = False
        else:
            editable = wm.operators[-1].bl_idname == "PERFECT_SHAPE_OT_perfect_shape"
        if not editable:
            scene.perfect_shape_tool_settings.action = "NEW"
            return True
        else:
            pass
        return False

    @classmethod
    def check_tool_action(cls):
        if cls.action_in_change_func is None:
            cls.action_in_change_func = cls._check_tool_action

    @classmethod
    def execute_perfect_shape_operator(cls, rotation, shift, span):
        wm = bpy.context.window_manager
        if not wm.operators:
            return False
        op = wm.operators[-1]
        if op.bl_idname != "PERFECT_SHAPE_OT_perfect_shape":
            return False

        def _execute_operator(scene, graph):
            op.rotation = rotation
            op.shift = shift
            op.span = span
            op.execute(bpy.context)
            return True

        if cls.execute_operator_func is None:
            cls.execute_operator_func = _execute_operator


class ShapeHelper:
    _shape = None
    _shape_key = None
    _shape_preview = None
    _shape_best_shifts = []
    _shape_best_shift_cursor = 0
    _previews_shapes = {}

    max_points = None

    @classmethod
    def generate_shapes(cls, points_count, ratio, span, shift, rotation, shape_key=None, target_points_count=None,
                        points_distribution="SEQUENCE", points_distribution_smooth=False):

        shapes = {"CIRCLE":     lambda m: Shape.Circle(points_count, span, shift, rotation, max_points=m),
                  "RECTANGLE":  lambda m: Shape.Rectangle(points_count, ratio, span, shift, rotation, max_points=m),
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
                cls._shape = cls._shape_preview
        else:
            for key, func in shapes.items():
                cls._previews_shapes[key] = func(PREVIEW_MAX_POINTS)

        if points_count + span >= PREVIEW_MAX_POINTS:
            cls.max_points = PREVIEW_MAX_POINTS

    @classmethod
    def apply_transforms(cls):
        cls._shape.apply_subdivide()
        cls._shape.apply_rotation()

    @classmethod
    def render_previews(cls, shape_key=None):
        if shape_key is not None:
            render_preview("shape_types", shape_key, cls._previews_shapes[shape_key])
        else:
            for shape_key in ("CIRCLE", "RECTANGLE", "OBJECT"):
                render_preview("shape_types", shape_key, cls._previews_shapes[shape_key])

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
    def at_exit(cls):
        cls._shape = None
        cls._shape_preview = None
        cls._previews_shapes = None

    @classmethod
    def get_points_count(cls):
        return cls._shape.target_points_count


def register():
    bpy.app.handlers.depsgraph_update_post.append(update_handler)


def unregister():
    pass

atexit.register(ShapeHelper.at_exit)
