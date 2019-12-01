import time

import bpy

from bpy.app import timers as bpy_timers
from bpy.props import (EnumProperty, BoolProperty, IntProperty, FloatProperty, StringProperty)
from .previews import get_shape_preview_icon_id
from .helpers import ShapeHelper

previews_update_time = None
previews_update_data = None

shapes_types_dict = None


def enum_shape_types(self, context):
    return shapes_types_dict[self.shape_source]


def shape_source_update(self, context):
    self.shape = shapes_types_dict[self.shape_source][0][0]


def trigger_update_previews(self, context):
    global previews_update_time
    global previews_update_data

    def update_all_previews():
        global previews_update_time
        global previews_update_data

        if previews_update_time and time.time() - previews_update_time > 0.3:
            ShapeHelper.generate_shapes(*previews_update_data)
            previews_update_time = None
            previews_update_data = None
        else:
            bpy_timers.register(update_all_previews)

    previews_update_time = time.time()
    previews_update_data = (self.target_points_count,
                            (self.ratio_a, self.ratio_b),
                            self.span, self.shift, self.rotation, None, self.target_points_count,
                            self.points_distribution, self.points_distribution_smooth)
    update_all_previews()


def get_mesh_object_poll(self, object):
    return object.type == 'MESH'


def get_best_shift(self, context):
    if self.shift_next_better:
        self.shift = ShapeHelper.get_next_best_shift()
        self.shift_next_better = False


class ShaperProperties:
    shape_source: EnumProperty(name="Shape Source",
                               items=(("OBJECT", "Object", "Shape from object"),
                                      ("GENERIC", "Generic", "Generic Shape"),
                                      ("PATTERN", "Pattern", "Defined shape pattern")),
                               update=shape_source_update)
    shape: EnumProperty(name="Shape", items=enum_shape_types)

    factor: FloatProperty(name="Factor", min=0.0, max=1.0, default=1.0)

    points_distribution: EnumProperty(name="Points distribution", items=(("EVEN", "Evenly", "Evenly throughout the shape"),
                                                                 ("SEQUENCE", "Sequentially", "One after the other")))
    points_distribution_smooth: BoolProperty(name="Smooth", default=False)

    target: StringProperty()

    target_points_count: IntProperty()

    span: IntProperty(name="Span", update=trigger_update_previews)
    shift: IntProperty(name="Shift", update=trigger_update_previews)
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


def register():
    global shapes_types_dict
    shapes_types_dict = {
        "GENERIC": (("CIRCLE", "Circle", "Simple circle", get_shape_preview_icon_id("CIRCLE"), 0),
                    ("RECTANGLE", "Rectangle", "Simple rectangle", get_shape_preview_icon_id("RECTANGLE"), 1)),
        "OBJECT": (("OBJECT", "Object", "Custom shape from object", get_shape_preview_icon_id("OBJECT"), 0),)
    }


def unregister():
    pass
