import bpy


class PerfectShapeUI:
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


def perfect_shape_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("mesh.perfect_shape")


def register():
    bpy.types.VIEW3D_MT_edit_mesh_edges.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(perfect_shape_menu)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(perfect_shape_menu)
