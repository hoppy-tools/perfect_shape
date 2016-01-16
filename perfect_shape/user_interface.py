import bpy

from perfect_shape.properties import PerfectShape


class PerfectShapePanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'Tools'
    bl_context = "mesh_edit"
    bl_label = "Perfect Shape"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("mesh.perfect_shape")
        col.operator("mesh.perfect_pattern")


class PerfectShapeUI(PerfectShape):
    def draw(self, context):
        layout = self.layout

        split = layout.split(align=True)
        col = split.column(align=True)
        col.template_icon_view(self, "shape", show_labels=True)
        col = split.column(align=True)
        sub = col.column()
        sub.enabled = False
        sub.label("Mode:")
        sub.prop(self, "mode", text="")
        row = col.row()
        row.label("Fill Type:")
        row.prop(self, "fill_flatten")
        col.prop(self, "fill_type", text="")
        row = col.row(align=True)
        row.label("Influence:")
        row.label("Offset:")
        row = col.row(align=True)
        row.prop(self, "factor", text="")
        row.prop(self, "offset", text="")

        if self.shape == "RECTANGLE":
            col = layout.column(align=True)
            col.label("Rectangle Sides Ratio")
            row = col.row(align=True)
            row.prop(self, "ratio_a", text="a")
            row.prop(self, "ratio_b", text="b")
            row.prop(self, "is_square", toggle=True)
        elif self.shape == "OBJECT":
            col = layout.column()
            col.prop_search(self, "target", context.window_manager.perfect_shape, "objects", icon="OBJECT_DATAMODE")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "active_as_first")
        row.prop(self, "shape_rotation")


        col = layout.column(align=True)
        col.label("Projection")
        row = col.row(align=True)
        row.prop(self, "projection", expand=True)
        row = col.row(align=True)
        row.prop(self, "invert_projection", toggle=True)
        row.prop(self, "use_ray_cast", toggle=True)

        col = layout.column(align=True)
        col.label("Topology")

        row = col.row(align=True)
        row.prop(self, "shift")
        row.prop(self, "rotation")
        row.prop(self, "span")

        col = layout.column(align=True)
        col.label("Extrude")
        row = col.row(align=True)
        row.prop(self, "extrude", text="Value")
        row.prop(self, "inset")
        row.prop(self, "outset")


def perfect_shape_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.operator("mesh.perfect_shape")
    layout.operator("mesh.perfect_pattern")


def register():
    bpy.types.VIEW3D_MT_edit_mesh_edges.append(perfect_shape_menu)
    bpy.utils.register_class(PerfectShapePanel)


def unregister():
    bpy.utils.unregister_class(PerfectShapePanel)
    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(perfect_shape_menu)
