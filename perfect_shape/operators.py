from builtins import print

import bpy
import bmesh

from bpy.types import Operator
from bpy.props import StringProperty

from .properties import ShaperProperties
from .user_interface import PerfectShapeUI
from .helpers import ShapeHelper, AppHelper

from bl_ui.space_toolsystem_common import activate_by_id


class PERFECT_SHAPE_OT_select_and_shape(Operator):
    bl_label = "Select and Perfect Shape"
    bl_idname = "perfect_shape.select_and_shape"
    bl_options = {'INTERNAL'}

    select_method: StringProperty(default='CIRCLE')
    select_mode: StringProperty(default='SET')

    _release = False

    def modal(self, context, event):
        if self._release:
            self.execute(context)
            return {'FINISHED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._release = True
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        bpy.ops.perfect_shape.perfect_shape('INVOKE_REGION_WIN', True)
        return {'FINISHED'}

    def invoke(self, context, event):
        bpy.ops.view3d.select_circle('INVOKE_REGION_WIN', wait_for_input=False, mode=self.select_mode)
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

    def execute(self, context):
        print("Execute!!")

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
            ShapeHelper.generate_shapes(0, 0, 0.0, (1, 1))
            ShapeHelper.render_previews()

        return all((context.mode == "EDIT_MESH",
                    context.area.type == "VIEW_3D",
                    context.object is not None))

    def check(self, context):
        return True

    def update_shape_and_previews(self, key=None, main=None, exclude=None):
        refresh = ShapeHelper.generate_shapes(self.shift, self.span, self.rotation, (self.ratio_a, self.ratio_b),
                                              key, main, exclude,
                                              self.points_distribution, self.points_distribution_smooth)
        if refresh:
            ShapeHelper.render_previews(rotation=self.rotation)

        if ShapeHelper.max_points:
            self.report({'INFO'},
                        "The maximum number({}) of preview points has been reached.".format(ShapeHelper.max_points))

    def execute(self, context):
        if ShapeHelper.get_points_count() < 3:
            self.report({'WARNING'}, "Select at least 3 vertices.")
            return {'FINISHED'}

        for area in context.screen.areas:
            area.tag_redraw()
        context.object.update_from_editmode()
        self.update_shape_and_previews(self.shape)
        return {'FINISHED'}

    def invoke(self, context, event):
        ShapeHelper.clear_cache()
        object = context.object
        object.update_from_editmode()

        ShapeHelper.prepare_object(object)
        ShapeHelper.clear_best_shifts()

        self.update_shape_and_previews(main=self.shape)
        context.scene.perfect_shape_tool_settings.action = "TRANSFORM"
        return self.execute(context)


def register():
    from bpy.utils import register_class
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

