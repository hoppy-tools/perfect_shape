import bpy


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


class PerfectShapeUI:
    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label("A perfect")
        col.prop(self, "shape", text="")

        if self.shape in ["OBJECT", "PATTERN"]:
            col.label("Object and Pattern shapes are in beta.", icon="ERROR")

        if self.shape == "RECTANGLE":
            col.label("Sides Ratio")
            row = col.row(align=True)
            row.prop(self, "ratio_a", text="a")
            row.prop(self, "ratio_b", text="b")
            row.prop(self, "is_square", toggle=True)

        elif self.shape == "OBJECT":
            col.label("Object")
            col.prop(self, "target", text="")

        col = layout.column(align=True)
        col.label("Projection")
        row = col.row(align=True)
        row.prop(self, "projection", expand=True)
        row = col.row(align=True)
        row.prop(self, "invert_projection", toggle=True)
        row.prop(self, "use_ray_cast", toggle=True)

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "active_as_first")
        row.prop(self, "shape_rotation")

        col = layout.column(align=True)
        row = col.row()
        row.label("Fill Type")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.prop(self, "fill_flatten")
        col.prop(self, "fill_type", text="")

        col = layout.column(align=True)
        col.label("Factor")
        col.prop(self, "factor", text="", slider=True)

        col = layout.column(align=True)
        col.label("Offset")
        col.prop(self, "offset", text="")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.label("Shift")
        row.label("Rotation")
        row.label("Span")
        row = col.row(align=True)
        row.prop(self, "shift", text="")
        row.prop(self, "rotation", text="")
        row.prop(self, "span", text="")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.label("Inset")
        row.label("Outset")
        row.separator()
        #row.label("Relax")
        row = col.row(align=True)
        row.prop(self, "inset", text="")
        row.prop(self, "outset", text="")
        row.separator()
        #row.prop(self, "relax", text="")

        col = layout.column(align=True)
        col.label("Extrude")
        col.prop(self, "extrude", text="")


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
