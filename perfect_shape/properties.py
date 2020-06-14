import bpy

from bpy.props import (EnumProperty, BoolProperty, IntProperty, FloatProperty, StringProperty, FloatVectorProperty)
from .previews import get_shape_preview_icon_id
from .helpers import ShapeHelper, AppHelper
from .user_interface import perfect_shape_tool
from bl_ui.space_toolsystem_common import activate_by_id


shapes_types_dict = None


def enum_shape_types(self, context):
    if context:
        region = context.region
        if region and region.type == "HUD" and ShapeHelper._shape_key:
            items_list = []
            for items in shapes_types_dict[self.shape_source]:
                items = list(items)
                if ShapeHelper._shape_key == items[0]:
                    items[3] = get_shape_preview_icon_id("current_shape")
                items_list.append(tuple(items))
            return tuple(items_list)

    return tuple(tuple(i) for i in shapes_types_dict[self.shape_source])


def shape_source_update(self, context):
    self.shape = shapes_types_dict[self.shape_source][0][0]


def trigger_update_previews(self, context):
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


def get_mesh_object_poll(self, object):
    return object.type == 'MESH'


def get_best_shift(self, context):
    if self.shift_next_better:
        self.shift = ShapeHelper.get_next_best_shift()
        self.shift_next_better = False


def set_shift(self, value):
    self['shift'] = value % (ShapeHelper.get_final_points_cout() * (-1 if value < 0 else 1))


def get_shift(self):
    return self.get('shift', 0)


class PerfectSelectOperatorProperties:
    x: IntProperty()
    y: IntProperty()
    mode: EnumProperty(name="Mode",
                       items=(("SET", "Set", "Set a new selection", "SELECT_SET", 0),
                              ("ADD", "Extend", "Extend existing selection", "SELECT_EXTEND", 1),
                              ("SUB", "Subtract", "Subtract existing selection", "SELECT_SUBTRACT", 2)),
                       default="ADD")
    radius: IntProperty(name="Select Radius", min=5, default=25)
    wait_for_input: BoolProperty(default=True)
    align_to_normal: BoolProperty(name="Align to normal", default=False,
                                  description="Align selection area to faces normal.")
    use_set_preselect: BoolProperty(name="Preselect", default=False,
                                    description="Apply selection after button release.")


class ShaperProperties:
    shape_source: EnumProperty(name="Shape Source",
                               items=(("GENERIC", "Generic", "Generic Shape"),
                                      ("OBJECT", "Object", "Shape from object")),
                               update=shape_source_update)
    shape: EnumProperty(name="Shape", items=enum_shape_types, update=trigger_update_previews)

    influence: FloatProperty(name="Influence", default=100.0, min=0.0, max=100.0, precision=1, subtype='PERCENTAGE')

    points_distribution: EnumProperty(name="Points distribution", items=(("EVEN", "Evenly", "Evenly throughout the shape"),
                                                                 ("SEQUENCE", "Sequentially", "One after the other")))
    points_distribution_smooth: BoolProperty(name="Smooth", default=False)

    target: StringProperty()

    span: IntProperty(name="Span", update=trigger_update_previews,
                      description="Number of vertices to skip in shape mapping")
    span_cuts: IntProperty(name="Span Cuts", min=-1, default=-1, update=trigger_update_previews,
                           description="Number of split points, auto if value equals -1")
    span_cuts_auto: BoolProperty(name="Auto Cuts", description="Automatically adjust the cuts", default=False)
    shift: IntProperty(name="Shift", update=trigger_update_previews, set=set_shift, get=get_shift)
    shift_next_better: BoolProperty(name="Next better shift", description="Next better shift",
                                    default=False, update=get_best_shift)

    ratio_a: IntProperty(name="Ratio a", description="Side 'a' ratio", min=1, default=1, update=trigger_update_previews)
    ratio_b: IntProperty(name="Ratio b", description="Side 'b' ratio", min=1, default=1, update=trigger_update_previews)
    is_square: BoolProperty(name="Is square", description="Square", default=False)

    scale: FloatProperty(name="Scale", default=1.0)
    rotation: FloatProperty(name="Rotation", subtype="ANGLE", update=trigger_update_previews)

    projection: EnumProperty(name="Projection",
                             items=(("N", "N", "Normal"),
                                    ("X", "X", "X-axis"),
                                    ("Y", "Y", "Y-axis"),
                                    ("Z", "Z", "Z-axis")))
    projection_invert: BoolProperty(name="Invert", description="Invert projection axis", default=False)
    projection_onto_self: BoolProperty(name="Projection onto Self", description="Wrap surface")


def tool_actions_enum(self, context):
    items = [["NEW", "New", "Set a new selection and apply Perfect Shape"],
             ["EDIT_SELECTION", "Edit Selection", "Edit current selection and apply Perfect Shape"],
             ["TRANSFORM", "Transform", "Transform Shape"]]

    reg = context.region.type if context.region is not None else None
    if reg is not None and reg != 'TOOL_HEADER':
        for item in items:
            item[1] = "    " + item[1]
    return tuple(tuple(i) for i in items)


def tool_actions_update(self, context):
    if self.action == "TRANSFORM":
        perfect_shape_tool.keymap[0] = ""
    else:
        perfect_shape_tool.keymap[0] = "perfect_shape.select_and_shape"

    activated = activate_by_id(context, "VIEW_3D", "perfect_shape.perfect_shape_tool")
    if not activated:
        AppHelper.active_tool_on_poll = True


class PerfectShapeToolSettings(bpy.types.PropertyGroup):
    action: EnumProperty(name="Action", items=tool_actions_enum, update=tool_actions_update)
    select_radius: IntProperty(name="Select Radius", min=5, default=25)
    snap_loc: FloatVectorProperty(name="Snap Position", size=2)
    snap_enabled: BoolProperty(name="Snap Enabled", default=False)
    align_to_normal: BoolProperty(name="Align Selection to Normal", default=True)
    use_snap_perfect_select: BoolProperty(name="Perfect Select", default=True,
                                          description="Perfect Select is affected by snapping settings.")
    use_snap_edge_slide: BoolProperty(name="Slide on edge", default=True,
                                          description="Slide on edge loop")
    show_select_cursor: BoolProperty(default=True)
    use_set_preselect: BoolProperty(default=False)


def register():
    global shapes_types_dict
    shapes_types_dict = {
        "GENERIC": [["CIRCLE", "Circle", "Simple circle", get_shape_preview_icon_id("CIRCLE"), 0],
                    ["QUADRANGLE", "Quadrangle", "Simple quadrangle", get_shape_preview_icon_id("QUADRANGLE"), 1]],
        "OBJECT": [["OBJECT", "Object", "Custom shape from object", get_shape_preview_icon_id("OBJECT"), 0]]
    }

    bpy.utils.register_class(PerfectShapeToolSettings)
    bpy.types.Scene.perfect_shape_tool_settings = bpy.props.PointerProperty(type=PerfectShapeToolSettings)


def unregister():
    pass
