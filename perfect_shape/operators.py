import bmesh
import numpy

from bpy.types import Operator

from .properties import ShaperProperties
from .shaper import generate_previews_shapes




class PERFECT_SHAPE_OT_shaper(ShaperProperties, Operator):
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

    def update_previews(self, key=None):
        max_points = generate_previews_shapes(self.target_points_count,
                                              (self.ratio_a, self.ratio_b),
                                              self.span, self.shift, self.rotation, key, self.target_points_count,
                                              self.points_distribution, self.points_distribution_smooth)
        if max_points:
            self.report({'INFO'}, "The maximum number({}) of preview points has been reached.".format(max_points))

    def execute(self, context):
        self.update_previews(self.shape)

        return {'FINISHED'}

    def invoke(self, context, event):
        object = context.object
        object.update_from_editmode()

        object_bm = bmesh.from_edit_mesh(object.data)
        selected_verts = [v for v in object_bm.verts if v.select]
        self.target_points_count = len(selected_verts)

        self.update_previews()

        return self.execute(context)

    def draw(self, context):
        layout = self.layout

        split = layout.split()
        col = split.column()
        col.template_icon_view(self, "shape", show_labels=True, scale=13.2, scale_popup=6.0)
        col.prop(self, 'factor', expand=True)
        split = layout.split(factor=0.3)
        col = split.column(align=True)
        col.label(text="Source:")
        col = split.column(align=True)
        col.prop(self, "shape_source", text="")
        if self.shape in ["OBJECT", "PATTERN"]:
            col.prop_search(self, "target", context.scene, "objects", icon="OBJECT_DATAMODE", text="")

        split = layout.split(factor=0.3)
        col = split.column(align=True)
        col.label(text="Distribution:")
        col = split.column(align=True)

        if self.shape in ["OBJECT", "PATTERN"]:
            row = col.row(align=True)
            row.prop(self, "points_distribution", expand=True)
            row.prop(self, 'points_distribution_smooth', text="", icon="MOD_SMOOTH")

        if self.shape == "RECTANGLE":
            row = col.row(align=True)
            row.prop(self, 'ratio_a')
            row.prop(self, 'ratio_b')
            row.prop(self, 'is_square', text="", icon="PIVOT_BOUNDBOX")
            
        row = col.row(align=True)
        row.prop(self, 'span')
        row.prop(self, 'shift')
        col = row.column(align=True)
        col.prop(self, 'shift_next_better', text="", icon="CURVE_NCIRCLE")
        if self.shape_source == "GENERIC":
            col.active = False


        split = layout.split(factor=0.3)
        col = split.column(align=True)
        col.label(text="Projection:")

        col = split.column(align=True)
        row = col.row(align=True)
        row.prop(self, 'projection', expand=True)
        row.prop(self, 'projection_invert', text="", icon="FILE_REFRESH")
        row = col.row(align=True)
        row.prop(self, 'scale')
        row.prop(self, 'rotation')
        row.prop(self, 'projection_onto_self', text="", icon="MOD_SHRINKWRAP")




def register():
    from bpy.utils import register_class
    register_class(PERFECT_SHAPE_OT_shaper)


def unregister():
    from bpy.utils import unregister_class
    unregister_class(PERFECT_SHAPE_OT_shaper)
