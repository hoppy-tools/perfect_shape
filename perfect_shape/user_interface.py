import bpy
from bpy.utils.toolsystem import ToolDef
from .utils import get_icon


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


@ToolDef.from_fn
def perfect_shape_tool():
    def draw_settings(context, layout, tool):
        def _get_icon(value):
            icon = "ops.generic.select_circle"
            if value == "TRANSFORM":
                icon = "ops.transform.transform"
            return get_icon(icon)

        reg = context.region.type
        is_not_header = reg != 'TOOL_HEADER'
        show_edit_props = context.window_manager.operators and \
            context.window_manager.operators[-1].bl_idname == "PERFECT_SHAPE_OT_perfect_shape"
        props = tool.operator_properties("perfect_shape.perfect_shape")
        tool_settings = context.scene.perfect_shape_tool_settings

        if show_edit_props:
            row = layout.row(align=True)
            if is_not_header:
                row.scale_y = 1.8
            row.prop(tool_settings, "action", text="" if is_not_header else None,
                     icon_value=_get_icon(tool_settings.action) if is_not_header else 0)

        if tool_settings.action == "NEW":
            layout.prop(props, "shape_source")
            layout.template_icon_view(props, "shape", show_labels=True, scale=8, scale_popup=6.0)

    return dict(
        idname="perfect_shape.perfect_shape_tool",
        label="Perfect Shape",
        description=(
            "Extrude shape"
        ),
        icon="ops.generic.select_circle",
        keymap="perfect_shape.select_and_shape",
        draw_settings=draw_settings,
    )


def get_tool_list(space_type, context_mode):
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    cls = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
    return cls._tools[context_mode]


def register_tool():
    tools = get_tool_list('VIEW_3D', 'EDIT_MESH')
    for index, tool in enumerate(tools, 1):
        if isinstance(tool, ToolDef) and tool.label == "Perfect Shape":
            break
    tools[:index] += None, perfect_shape_tool
    del tools


def unregister_tool():
    tools = get_tool_list('VIEW_3D', 'EDIT_MESH')
    index = tools.index(perfect_shape_tool) - 1
    tools.pop(index)
    tools.remove(perfect_shape_tool)
    del tools
    del index


def perfect_shape_menu(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("mesh.perfect_shape")


def register():
    bpy.types.VIEW3D_MT_edit_mesh_edges.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(perfect_shape_menu)
    register_tool()


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(perfect_shape_menu)
    unregister_tool()
