import bpy
import math
import bmesh
from bpy.utils.toolsystem import ToolDef
from .utils import get_icon
from gpu_extras.presets import draw_circle_2d
from bpy.types import GizmoGroup
from mathutils import Matrix, Vector
from perfect_shape.helpers import ShapeHelper


class PerfectShapeUI:
    def draw(self, context):
        layout = self.layout

        split = layout.split()
        col = split.column()
        col.template_icon_view(self, "shape", show_labels=True, scale=13.2, scale_popup=6.0)
        col.prop(self, 'influence', expand=True)
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


class PerfectShapeWidget(GizmoGroup):
    bl_idname = "perfect_shape.widget"
    bl_label = "Perfect Shape Transform Widget"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D'}

    @staticmethod
    def get_operator(context):
        from perfect_shape.operators import PERFECT_SHAPE_OT_perfect_shape
        wm = context.window_manager
        op = wm.operators[-1] if wm.operators else None
        if isinstance(op, PERFECT_SHAPE_OT_perfect_shape):
            return op
        return None

    @staticmethod
    def get_theme(context):
        return context.preferences.themes[0]

    @staticmethod
    def get_user_interface_color(context, key):
        theme = PerfectShapeWidget.get_theme(context)
        return getattr(theme.user_interface, key)

    @staticmethod
    def get_matrix_basis(context):
        return ShapeHelper.get_object_shape_projection_matrix().normalized()

    @classmethod
    def poll(cls, context):
        if ShapeHelper.get_points_count() < 3:
            return False
        return cls.get_operator(context) is not None and context.scene.perfect_shape_tool_settings.action == "TRANSFORM"

    def setup(self, context):
        def rotation_get():
            op = PerfectShapeWidget.get_operator(context)
            return op.rotation

        def rotation_set(value):
            op = PerfectShapeWidget.get_operator(context)
            op.rotation = value
            op.execute(context)

        def shift_get():
            op = PerfectShapeWidget.get_operator(context)
            step = ((math.pi / 2) / (ShapeHelper.get_points_count() - 1))
            value = op.shift * step
            return value

        def shift_set(value):
            op = PerfectShapeWidget.get_operator(context)
            step = ((math.pi / 2) / (ShapeHelper.get_points_count()-1))
            op.shift = value // step
            op.execute(context)

        def span_get():
            op = PerfectShapeWidget.get_operator(context)
            return math.radians(op.span*6)

        def span_set(value):
            op = PerfectShapeWidget.get_operator(context)
            op.span = math.degrees(value/6)
            op.execute(context)

        def move_get():
            return 0.0

        def move_set(value):
            pass

        mpr = self.gizmos.new("GIZMO_GT_arrow_3d")
        mpr.target_set_operator("perfect_shape.widget_extrude")
        mpr.use_draw_value = False
        mpr.draw_style = "BOX"
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'gizmo_primary')
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha = 0.9
        mpr.alpha_highlight = 1.0
        mpr.select_bias = True
        self.extrude_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_primitive_3d")
        mpr.target_set_operator("perfect_shape.widget_scale")
        mpr.use_draw_value = False
        mpr.use_draw_offset_scale = True
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'axis_z')
        mpr.matrix_offset = Matrix.Translation(Vector((0.0, -9.8, 0.0)))
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha = 1.0
        mpr.alpha_highlight = 1.0
        mpr.scale_basis = 0.1
        mpr.select_bias = True
        self.scale_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_arrow_3d")
        mpr.target_set_operator("perfect_shape.widget_move")
        mpr.use_draw_value = False
        mpr.target_set_handler("offset", get=move_get, set=move_set)
        mpr.length = 0.0
        mpr.use_draw_offset_scale = True
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'axis_y')
        mpr.matrix_offset = Matrix.Translation(Vector((0.0, 0.0, 1.08)))
        mpr.alpha = 1.0
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha_highlight = 1.0
        self.move_y_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_arrow_3d")
        mpr.target_set_operator("perfect_shape.widget_move")
        mpr.use_draw_value = False
        mpr.target_set_handler("offset", get=move_get, set=move_set)
        mpr.length = 0.0
        mpr.use_draw_offset_scale = True
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'axis_x')
        mpr.matrix_offset = Matrix.Translation(Vector((0.0, 0.0, 1.08)))
        mpr.alpha = 1.0
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha_highlight = 1.0
        self.move_x_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_dial_3d")
        mpr.use_draw_value = True
        mpr.draw_options = {'ANGLE_VALUE'}
        mpr.target_set_operator("perfect_shape.widget_rotation")
        mpr.target_set_handler("offset", get=rotation_get, set=rotation_set)
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'axis_z')
        mpr.alpha = 0.9
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha_highlight = 1.0
        mpr.select_bias = True
        mpr.scale_basis = 0.6
        self.rotation_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_dial_3d")
        mpr.draw_options = {'FILL'}
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'axis_z')
        mpr.color.s = 0.5
        mpr.color_highlight = mpr.color
        mpr.alpha = 1.0
        mpr.alpha_highlight = 1.0
        mpr.scale_basis = 0.6
        self.rotation_bg_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_dial_3d")
        mpr.use_draw_value = True
        mpr.draw_options = {"ANGLE_VALUE"}
        mpr.target_set_operator("perfect_shape.widget_shift")
        mpr.target_set_handler("offset", get=shift_get, set=shift_set)
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'gizmo_a')
        mpr.alpha = 0.9
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha_highlight = 1.0
        mpr.arc_partial_angle = math.pi
        self.shift_widget = mpr

        mpr = self.gizmos.new("GIZMO_GT_dial_3d")
        mpr.use_draw_modal = True
        mpr.target_set_operator("perfect_shape.widget_span")
        mpr.target_set_handler("offset", get=span_get, set=span_set)
        mpr.line_width = 3
        mpr.color = PerfectShapeWidget.get_user_interface_color(context, 'gizmo_primary')
        mpr.alpha = 0.9
        mpr.color_highlight = 1.0, 1.0, 1.0
        mpr.alpha_highlight = 1.0
        mpr.scale_basis = 1.4
        mpr.wrap_angle = True
        self.span_widget = mpr

    def refresh(self, context):
        matrix = PerfectShapeWidget.get_matrix_basis(context)
        for widget in ['extrude', 'rotation', 'rotation_bg', 'shift', 'span', 'scale']:
            mpr = getattr(self, widget + "_widget")
            mpr.matrix_basis = matrix
        self.move_y_widget.matrix_basis = matrix @ Matrix.Rotation(math.radians(-90), 4, 'X')
        self.move_x_widget.matrix_basis = matrix @ Matrix.Rotation(math.radians(90), 4, 'Y')


def tool_draw_settings(context, layout, tool):
    def _get_icon(value):
        icon = "ops.generic.select_circle"
        if value == "TRANSFORM":
            icon = "ops.transform.transform"
        return get_icon(icon)

    reg = context.region.type
    is_not_header = reg != 'TOOL_HEADER'
    props = tool.operator_properties("perfect_shape.perfect_shape")
    tool_settings = context.scene.perfect_shape_tool_settings

    row = layout.row()
    if is_not_header:
        row.scale_y = 1.8
    row.prop(tool_settings, "action", text="" if is_not_header else None,
             icon_value=_get_icon(tool_settings.action) if is_not_header else 0)
    if tool_settings.action == "NEW":
        row = layout.row()
        row.operator("perfect_shape.perfect_shape", text="From Current Selection")
        layout.prop(props, "shape_source")
        layout.template_icon_view(props, "shape", show_labels=True, scale=8, scale_popup=6.0)


def tool_draw_cursor(context, tool, xy):
    if context.scene.perfect_shape_tool_settings.action != "TRANSFORM":
        props = tool.operator_properties("view3d.select_circle")
        radius = props.radius
        draw_circle_2d(xy, (1.0,) * 4, radius, 32)


@ToolDef.from_fn
def perfect_shape_tool():
    return dict(
        idname="perfect_shape.perfect_shape_tool",
        label="Perfect Shape",
        description=(
            "Extrude shape with Perfect Shape addon"
        ),
        icon="ops.generic.select_circle",
        keymap="perfect_shape.select_and_shape",
        operator="perfect_shape.select_and_shape",
        widget="perfect_shape.widget",
        draw_settings=tool_draw_settings,
        draw_cursor=tool_draw_cursor
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
    layout.operator("perfect_shape.perfect_shape")


def register():
    bpy.types.VIEW3D_MT_edit_mesh_edges.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(perfect_shape_menu)
    bpy.utils.register_class(PerfectShapeWidget)
    register_tool()


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(perfect_shape_menu)
    bpy.types.VIEW3D_MT_edit_mesh_edges.remove(perfect_shape_menu)
    bpy.utils.unregister_class(PerfectShapeWidget)
    unregister_tool()
