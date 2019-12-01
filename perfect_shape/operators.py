import bmesh

from bpy.types import Operator

from .properties import ShaperProperties
from .user_interface import PerfectShapeUI
from .helpers import ShapeHelper


class PERFECT_SHAPE_OT_shaper(ShaperProperties, PerfectShapeUI, Operator):
    bl_label = "Perfect Shape"
    bl_idname = "mesh.perfect_shape"
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
    register_class(PERFECT_SHAPE_OT_shaper)


def unregister():
    from bpy.utils import unregister_class
    unregister_class(PERFECT_SHAPE_OT_shaper)
