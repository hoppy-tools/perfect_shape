import bpy
import bmesh

from bpy.types import Operator

from .properties import ShaperProperties, PerfectSelectOperatorProperties
from .user_interface import PerfectShapeUI, perfect_select_draw_callback
from .helpers import ShapeHelper, AppHelper

from bl_ui.space_toolsystem_common import activate_by_id
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_vector_3d, location_3d_to_region_2d

from mathutils import Vector, Matrix
from mathutils.geometry import intersect_point_line

from .geom_utils import (matrix_decompose_4x4, is_backface, create_kdtree, intersect_point_section,
                         points_3d_to_region_2d, points_pairs_3d_to_region_2d, region_2d_to_points_3d)


class PERFECT_SHAPE_OT_perfect_select(PerfectSelectOperatorProperties, Operator):
    bl_label = "Perfect Select"
    bl_idname = "perfect_shape.perfect_select"
    bl_options = {'UNDO'}

    @staticmethod
    def _get_mouse_region_pos(event):
        return event.mouse_region_x, event.mouse_region_y

    def select_operator(self, x=None, y=None, radius=None, mode=None):
        x = x or self.x
        y = y or self.y
        radius = radius or self.radius
        if mode is None:
            mode = self.mode
            if mode == "SET" and self._set_continue:
                mode = "ADD"

        bpy.ops.view3d.select_circle('EXEC_DEFAULT', x=x, y=y,
                                     wait_for_input=False, mode=mode, radius=radius)

    def _get_select_args(self, context):
        ps_tool_settings = self._get_tool_settings(context)
        use_snap = context.tool_settings.use_snap and ps_tool_settings.use_snap_perfect_select
        snap_edge_slide = ps_tool_settings.use_snap_edge_slide
        snap_elements = context.tool_settings.snap_elements
        snap_backface_culling = context.tool_settings.use_snap_backface_culling
        return context, use_snap, snap_elements, snap_edge_slide, snap_backface_culling

    def _init_loop(self, region, rv3d, backface_culling=False):
        bpy.ops.view3d.select(deselect_all=True)
        mtx = self._mtx
        mtx_sr = self._mtx_s @ self._mtx_r
        self._snap_edge.select = True
        self._bm.select_flush_mode()
        bpy.ops.mesh.loop_multi_select()
        eye = Vector(rv3d.view_matrix[2][:3])
        eye.length = rv3d.view_distance
        eye_location = rv3d.view_location + eye
        if backface_culling:
            self._loop = [e for e in self._bm.edges if e.select and not is_backface(e.verts[0], eye_location, mtx, mtx_sr)]
        else:
            self._loop = [e for e in self._bm.edges if e.select]
        self._loop_2d = points_pairs_3d_to_region_2d(((mtx @ e.verts[0].co, mtx @ e.verts[1].co) for e in self._loop),
                                                     region, rv3d)

    def _del_loop(self):
        self._loop = None
        self._loop_2d = None

    def _filter_loop_edges(self, edges):
        return (e for e in edges if e in self._loop)

    def _snap(self, co, pos, vert, selection_normal, view_location, snap_elements, snap_edge_slide,
              snap_backface_culling, region, rv3d):
        pos_2d = Vector(pos[:2])
        mtx, mtx_r, mtx_s = self._mtx, self._mtx_r, self._mtx_s
        mtx_sr = mtx_s @ mtx_r
        points = []
        if "VERTEX" in snap_elements:
            points.append(Vector(co[:2]))
            selection_normal = mtx_sr @ vert.normal
            view_location = mtx @ vert.co
        if any(e in snap_elements for e in ("EDGE", "EDGE_MIDPOINT", "EDGE_PERPENDICULAR")):
            edges = vert.link_edges
            if snap_edge_slide and self._snap_edge:
                if self._loop is None:
                    self._init_loop(region, rv3d, snap_backface_culling)
                edges_co = [(mtx @ e.verts[0].co, mtx @ e.verts[1].co) for e in self._filter_loop_edges(edges)]
                if not edges_co:
                    edges = self._loop
                    edges_co_2d = self._loop_2d
                else:
                    edges_co_2d = points_pairs_3d_to_region_2d(edges_co, region, rv3d)
            else:
                edges_co = [(mtx @ e.verts[0].co, mtx @ e.verts[1].co) for e in vert.link_edges]
                edges_co_2d = points_pairs_3d_to_region_2d(edges_co, region, rv3d)

            if edges_co_2d:
                self._debug_edges = edges_co_2d
                closest_points = [(i, e, intersect_point_section(pos_2d, e[0], e[1])[0]) for i, e in enumerate(edges_co_2d)]
                closest_points.sort(key=lambda i: (i[2] - pos_2d).length)
                closest_index, closest_edge_co, closest_point = closest_points[0]
                closest_edge = edges[closest_index]
                if snap_edge_slide:
                    self._snap_edge = closest_edge

                selection_normal = (mtx_sr @ closest_edge.verts[0].normal + mtx_sr @ closest_edge.verts[1].normal) / 2
                view_location = (mtx @ closest_edge.verts[0].co + mtx @ closest_edge.verts[1].co) / 2
                if "EDGE" in snap_elements:
                    points.append(closest_point)
                if "EDGE_MIDPOINT" in snap_elements:
                    closest_edge_co = edges_co_2d[closest_index]
                    points.append(closest_edge_co[0].lerp(closest_edge_co[1], 0.5))
                if "EDGE_PERPENDICULAR" in snap_elements:
                    points.append(closest_edge_co[0] if (closest_edge_co[0] - pos_2d).length < (
                            closest_edge_co[1] - pos_2d).length else closest_edge_co[1])

        if points:
            points.sort(key=lambda v: (Vector(v) - pos_2d).length)
            co = points[0]
            self._snap_point = co

        return co, selection_normal, view_location

    def select(self, context, use_snap, snap_elements, snap_edge_slide, snap_backface_culling):
        co = pos = Vector((self.x, self.y, 0.0))

        mtx = context.object.matrix_world
        mtx_t, mtx_r,  mtx_s = matrix_decompose_4x4(mtx)
        self._mtx, self._mtx_t, self._mtx_r, self._mtx_s = mtx, mtx_t, mtx_r, mtx_s

        rv3d = context.space_data.region_3d
        region = context.region
        view_location = Vector((0.0, 0.0, 0.0))

        selection_normal = None

        mesh = context.object.data
        if self._bm is None:
            context.object.update_from_editmode()
            self._bm = bmesh.from_edit_mesh(mesh)

        bm = self._bm

        verts_selected_original = [v for v in bm.verts if v.select]
        edges_selected_original = [e for e in bm.edges if e.select]
        faces_selected_original = [f for f in bm.faces if f.select]

        self.select_operator(mode="SET")
        if use_snap or self.align_to_normal:
            snap_edge = self._snap_edge
            verts_selected = [v for v in bm.verts if v.select]

            index = 0
            restore_values = False
            if verts_selected:
                verts_2d = points_3d_to_region_2d((mtx @ v.co for v in verts_selected), region, rv3d)
                kd = create_kdtree(verts_2d)
                co, index, dist = kd.find(co)
                if co is None:
                    restore_values = True
            if restore_values:
                co, index = pos, 0

            vert = verts_selected[index] if verts_selected else None
            if vert is None and snap_edge is not None:
                points_3d = region_2d_to_points_3d(pos[:2], region, rv3d)
                len_0 = (mtx @ snap_edge.verts[0].co - points_3d).length
                len_1 = (mtx @ snap_edge.verts[1].co - points_3d).length
                vert = snap_edge.verts[int(len_0 > len_1)]
            if vert is None:
                return

            if use_snap:
                co, selection_normal, view_location = self._snap(co, pos, vert, selection_normal, view_location,
                                                                 snap_elements, snap_edge_slide, snap_backface_culling,
                                                                 region, rv3d)
            else:
                self._snap_point = None
                view_location = mtx @ vert.co
                link_faces = vert.link_faces
                if link_faces:
                    n = Vector((0.0, 0.0, 0.0))
                    for f in link_faces:
                        n += mtx_s @ mtx_r @ f.normal
                    selection_normal = n / len(link_faces)

        bpy.ops.view3d.select(deselect_all=True)
        for vert in verts_selected_original:
            vert.select = True
        for edge in edges_selected_original:
            edge.select = True
        for face in faces_selected_original:
            face.select = True
        bm.select_flush_mode()

        if self._snap_point:
            co = self._snap_point

        if self.align_to_normal and selection_normal is not None:
            old_view_location = rv3d.view_location.copy()
            rv3d.view_location = view_location

            old_view_rotation = rv3d.view_rotation.copy()
            view_rotation = selection_normal.rotation_difference(Vector((0, 0, 1)))
            rv3d.view_rotation = view_rotation.inverted()

            rv3d.update()
            self.select_operator(context.region.width / 2, context.region.height / 2)
            rv3d.view_location = old_view_location
            rv3d.view_rotation = old_view_rotation
            rv3d.update()
        else:
            self.select_operator(co[0], co[1])

        self._set_continue = True

    def _clean(self):
        self._del_loop()
        self._snap_point = None
        self._snap_edge = None

    def _get_tool_settings(self, context):
        return context.scene.perfect_shape_tool_settings

    def _get_ps_tool(self, context):
        tool = context.workspace.tools.from_space_view3d_mode(context.mode)
        return tool if tool.idname == "perfect_shape.perfect_select_tool" else None

    def _check_init_attribs(self):
        names = "_set_continue", "_bm", "_snap_point", "_snap_edge", "_loop"
        for name in names:
            if not hasattr(self, name):
                setattr(self, name, None)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.mode == 'EDIT'

    def invoke(self, context, event):
        self._check_init_attribs()
        self.x, self.y = self._get_mouse_region_pos(event)
        ps_tool_settings = self._get_tool_settings(context)
        ps_tool_settings.show_select_cursor = False

        if not self.wait_for_input:
            if self.mode == "SET":
                tool = self._get_ps_tool(context)
                if tool is not None:
                    props = tool.operator_properties("perfect_shape.perfect_select")
                    self.mode = props.mode
            self.execute(context)
        else:
            self._select_enabled = False

        wm = context.window_manager
        wm.modal_handler_add(self)
        self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(perfect_select_draw_callback,
                                                                   (self, context),
                                                                   'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self._check_init_attribs()
        self.select(*self._get_select_args(context))
        return {'FINISHED'}

    def modal(self, context, event):
        context.area.tag_redraw()
        ps_tool_settings = self._get_tool_settings(context)
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            ps_tool_settings.show_select_cursor = True
            return {'CANCELLED'}

        if event.type in ['MOUSEMOVE']:
            self.x, self.y = self._get_mouse_region_pos(event)
            if (self.wait_for_input and self._select_enabled) or not self.wait_for_input:
                self.execute(context)

        if event.type in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE') and not event.ctrl:
            self.radius += 5 if event.type == 'WHEELDOWNMOUSE' else -5
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._select_enabled = True
            self.execute(context)

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self.wait_for_input:
                self._select_enabled = False
                self.mode = "ADD"
                self._clean()
                return {'RUNNING_MODAL'}

            self.wait_for_input = True
            self.mode = "ADD"
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            ps_tool_settings.show_select_cursor = True
            return {'FINISHED'}

        if event.type == 'MIDDLEMOUSE' and event.value == 'PRESS':
            self._select_enabled = True
            self.mode = "SUB"
            self.execute(context)

        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            if self.wait_for_input:
                self._select_enabled = False
                self.mode = "ADD"
                self._clean()
                return {'RUNNING_MODAL'}

        if event.type == "RET" and event.value == 'PRESS':
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self.wait_for_input = True
            ps_tool_settings.show_select_cursor = True
            return {'FINISHED'}

        return {'RUNNING_MODAL'}


class PERFECT_SHAPE_OT_select_and_shape(Operator):
    bl_label = "Select and Perfect Shape"
    bl_idname = "perfect_shape.select_and_shape"
    bl_options = {'INTERNAL'}

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.ops.ed.undo()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def execute(self, context):
        bpy.ops.perfect_shape.perfect_shape('INVOKE_REGION_WIN', True)
        tool_settings = self._get_tool_settings(context)
        tool_settings.snap_enabled = False
        return {'FINISHED'}

    def invoke(self, context, event):
        bpy.ops.ed.undo_push()
        wm = context.window_manager
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class WidgetOperator:
    bl_options = {'INTERNAL'}

    def get_perfect_shape_operator(self, context):
        wm = context.window_manager
        op = wm.operators[-1] if wm.operators else None
        if isinstance(op, PERFECT_SHAPE_OT_perfect_shape):
            return op
        return None

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' or event.type == 'RET':
            op = self.get_perfect_shape_operator(context)
            AppHelper.execute_perfect_shape_operator(op.rotation, op.shift, op.span)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class PERFECT_SHAPE_OT_widget_rotation(WidgetOperator, Operator):
    """Rotate shape"""
    bl_label = "Rotation"
    bl_idname = "perfect_shape.widget_rotation"


class PERFECT_SHAPE_OT_widget_shift(WidgetOperator, Operator):
    """Change index of the first vertex"""
    bl_label = "Shift"
    bl_idname = "perfect_shape.widget_shift"


class PERFECT_SHAPE_OT_widget_span(WidgetOperator, Operator):
    """Increase or decrease the shape mapping details"""
    bl_label = "Span"
    bl_idname = "perfect_shape.widget_span"


class PERFECT_SHAPE_OT_widget_extrude(WidgetOperator, Operator):
    """Extrude shape along the average normal"""
    bl_label = "Extrude"
    bl_idname = "perfect_shape.widget_extrude"


class PERFECT_SHAPE_OT_widget_scale(WidgetOperator, Operator):
    """Scale (resize) shape"""
    bl_label = "Scale"
    bl_idname = "perfect_shape.widget_scale"


class PERFECT_SHAPE_OT_widget_move(WidgetOperator, Operator):
    """Move shape"""
    bl_label = "Move"
    bl_idname = "perfect_shape.widget_move"


class PERFECT_SHAPE_OT_perfect_shape(ShaperProperties, PerfectShapeUI, Operator):
    bl_label = "Perfect Shape"
    bl_idname = "perfect_shape.perfect_shape"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    @classmethod
    def poll(cls, context):
        tool_settings = context.scene.perfect_shape_tool_settings
        if tool_settings.action != 'NEW':
            AppHelper.check_tool_action()

        if AppHelper.active_tool_on_poll:
            activate_by_id(context, "VIEW_3D", "perfect_shape.perfect_shape_tool")
            AppHelper.active_tool_on_poll = False

        if not ShapeHelper.initialized():
            ShapeHelper.generate_shapes()
            ShapeHelper.render_previews()

        return all((context.mode == "EDIT_MESH",
                    context.area.type == "VIEW_3D",
                    context.object is not None))

    def check(self, context):
        return True

    def update_shape_and_preview(self, key):
        ShapeHelper.generate_shapes(points_count=None,
                                    shift=self.shift,
                                    span=self.span,
                                    span_cuts=self.span_cuts,
                                    rotation=self.rotation,
                                    key=self.shape,
                                    # extra params
                                    ratio=(self.ratio_a, self.ratio_b),
                                    points_distribution=self.points_distribution,
                                    points_distribution_smooth=self.points_distribution_smooth
                                    )
        ShapeHelper.render_previews(self.shape, self.rotation)

        if ShapeHelper.max_points:
            self.report({'INFO'},
                        "The maximum number({}) of preview points has been reached.".format(ShapeHelper.max_points))

    def execute(self, context):
        if ShapeHelper.get_points_count() < 3:
            self.report({'WARNING'}, "Select at least 3 vertices.")
            return {'FINISHED'}

        # for area in context.screen.areas:
        #     area.tag_redraw()
        context.object.update_from_editmode()
        ShapeHelper._shape_key = self.shape
        self.update_shape_and_preview(self.shape)
        return {'FINISHED'}

    def invoke(self, context, event):
        ShapeHelper.clear_cache()

        object = context.object
        object.update_from_editmode()

        ShapeHelper.prepare_object(object)
        context.scene.perfect_shape_tool_settings.action = "TRANSFORM"

        return self.execute(context)


def register():
    from bpy.utils import register_class
    register_class(PERFECT_SHAPE_OT_perfect_select)
    register_class(PERFECT_SHAPE_OT_perfect_shape)
    register_class(PERFECT_SHAPE_OT_select_and_shape)
    register_class(PERFECT_SHAPE_OT_widget_rotation)
    register_class(PERFECT_SHAPE_OT_widget_shift)
    register_class(PERFECT_SHAPE_OT_widget_span)
    register_class(PERFECT_SHAPE_OT_widget_extrude)
    register_class(PERFECT_SHAPE_OT_widget_scale)
    register_class(PERFECT_SHAPE_OT_widget_move)


def unregister():
    from bpy.utils import unregister_class
    unregister_class(PERFECT_SHAPE_OT_widget_move)
    unregister_class(PERFECT_SHAPE_OT_widget_scale)
    unregister_class(PERFECT_SHAPE_OT_widget_extrude)
    unregister_class(PERFECT_SHAPE_OT_widget_span)
    unregister_class(PERFECT_SHAPE_OT_widget_shift)
    unregister_class(PERFECT_SHAPE_OT_widget_rotation)
    unregister_class(PERFECT_SHAPE_OT_select_and_shape)
    unregister_class(PERFECT_SHAPE_OT_perfect_shape)
    unregister_class(PERFECT_SHAPE_OT_perfect_select)

