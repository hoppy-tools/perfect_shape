from builtins import print

import bpy
import bmesh

from bpy.types import Operator
from bpy.props import StringProperty

from .properties import ShaperProperties
from .user_interface import PerfectShapeUI, perfect_shape_tool
from .helpers import ShapeHelper



class PERFECT_SHAPE_OT_select_and_shape(Operator):
    bl_label = "Select and Perfect Shape"
    bl_idname = "perfect_shape.select_and_shape"

    bl_options = {'INTERNAL'}

    select = False

    select_method: StringProperty(default='CIRCLE')
    select_mode: StringProperty(default='SET')

    def modal(self, context, event):
        if not self.select:
            self.select = True
            bpy.ops.view3d.select_circle('INVOKE_DEFAULT', wait_for_input=False, mode=self.select_mode)
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        else:
            bpy.ops.perfect_shape.perfect_shape('INVOKE_DEFAULT', True)
            return {'FINISHED'}
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}



class PERFECT_SHAPE_OT_perfect_shape(ShaperProperties, PerfectShapeUI, Operator):
    bl_label = "Perfect Shape"
    bl_idname = "perfect_shape.perfect_shape"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return all((context.mode == "EDIT_MESH",
                    context.area.type == "VIEW_3D",
                    context.object is not None))

    def check(self, context):
        return True

    def update_shape_and_previews(self, key=None):
        ShapeHelper.generate_shapes(self.target_points_count,
                                    (self.ratio_a, self.ratio_b),
                                    self.span, self.shift, self.rotation, key, self.target_points_count,
                                    self.points_distribution, self.points_distribution_smooth)
        if key is not None:
            ShapeHelper.calc_best_shifts()
            ShapeHelper.apply_transforms()
        ShapeHelper.render_previews()
        if ShapeHelper.max_points:
            self.report({'INFO'},
                        "The maximum number({}) of preview points has been reached.".format(ShapeHelper.max_points))

    def execute(self, context):
        self.update_shape_and_previews(self.shape)
        context.scene.perfect_shape_tool_settings.action = "TRANSFORM"
        return {'FINISHED'}

    def invoke(self, context, event):
        object = context.object
        object.update_from_editmode()

        object_bm = bmesh.from_edit_mesh(object.data)
        selected_verts = [v for v in object_bm.verts if v.select]
        self.target_points_count = len(selected_verts)

        ShapeHelper.clear_best_shifts()

        self.update_shape_and_previews()

        return self.execute(context)


def register():
    from bpy.utils import register_class
    register_class(PERFECT_SHAPE_OT_perfect_shape)
    register_class(PERFECT_SHAPE_OT_select_and_shape)


def unregister():
    from bpy.utils import unregister_class
    unregister_class(PERFECT_SHAPE_OT_perfect_shape)
    unregister_class(PERFECT_SHAPE_OT_select_and_shape)

