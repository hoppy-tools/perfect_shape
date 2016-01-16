import bpy
import bmesh
from bpy.app.handlers import persistent
from perfect_shape.utils import get_icon, preview_collections, prepare_loops


def enum_shape_types(self, context):
    pcoll = preview_collections["shape_types"]
    shapes = [("CIRCLE", "Circle", "", get_icon("circle"), 0),
              ("RECTANGLE", "Rectangle", "", get_icon("rectangle"), 1),
              ("OBJECT", "Object", "", get_icon("object"), 2)]

    if len(context.object.perfect_pattern.vertices) > 0:
        shapes.append(("PATTERN", "Perfect Pattern", "", get_icon("pattern"), 3))
    return shapes


def object_update(self, context):
    if self.target in bpy.data.objects:
        object = bpy.data.objects[self.target]
        wm = context.window_manager

        shape = wm.perfect_shape.shape
        shape.vertices.clear()
        shape.faces.clear()

        shape_bm = bmesh.new()
        shape_bm.from_object(object, context.scene)
        loops = prepare_loops(shape_bm.edges[:])
        if loops and len(loops) == 1:
            for vert in loops[0][0][0]:
                item = shape.vertices.add()
                item.co = vert.co
            shape_bm.clear()
            for vert in shape.vertices:
                shape_bm.verts.new(vert.co)
            shape_bm.faces.new(shape_bm.verts)
            #bmesh.ops.contextual_create(shape_bm, geom=shape_bm.verts)
            bmesh.ops.triangulate(shape_bm, faces=shape_bm.faces)
            for face in shape_bm.faces:
                item = shape.faces.add()
                item.indices = [v.index for v in face.verts]
            del shape_bm


class PerfectShape:
    bl_idname = "mesh.perfect_shape"
    bl_label = "To Perfect Shape"
    bl_options = {"REGISTER", "UNDO"}

    mode = bpy.props.EnumProperty(name="Mode",
                                  items=[("RESHAPE", "Reshape", "", "", 1),
                                         ("INDENT", "Indent", "", "", 2)],
                                  default="RESHAPE")

    shape = bpy.props.EnumProperty(name="A perfect", items=enum_shape_types)
    fill_type = bpy.props.EnumProperty(name="Fill Type",
                                       items=[("ORIGINAL", "Original", "", "", 1),
                                              ("COLLAPSE", "Collapse", "", "", 2),
                                              ("HOLE", "Hole", "", "", 3),
                                              ("NGON", "Ngon", "", "", 4)],
                                       default="ORIGINAL")

    projection = bpy.props.EnumProperty(name="Projection",
                                        items=[("NORMAL", "Normal", "", "", 1),
                                               ("X", "X", "", "", 2),
                                               ("Y", "Y", "", "", 3),
                                               ("Z", "Z", "", "", 4)],
                                        default="NORMAL")

    invert_projection = bpy.props.BoolProperty(name="Invert Direction", default=False)
    use_ray_cast = bpy.props.BoolProperty(name="Wrap to surface", default=False)
    fill_flatten = bpy.props.BoolProperty(name="Flatten", default=False)

    active_as_first = bpy.props.BoolProperty(name="Active as First", default=False)
    shape_rotation = bpy.props.BoolProperty(name="Shape Rotation", default=False)

    ratio_a = bpy.props.IntProperty(name="Ratio a", min=1, default=1)
    ratio_b = bpy.props.IntProperty(name="Ratio b", min=1, default=1)
    is_square = bpy.props.BoolProperty(name="Square", default=False)

    target = bpy.props.StringProperty(name="Object", update=object_update)
    factor = bpy.props.IntProperty(name="Factor", min=0, max=100, default=100, subtype="PERCENTAGE")
    inset = bpy.props.FloatProperty(name="Inset", min=0.0, default=0)
    outset = bpy.props.FloatProperty(name="Outset", min=0.0, default=0)
    shift = bpy.props.IntProperty(name="Shift")
    rotation = bpy.props.FloatProperty(name="Rotation", subtype="ANGLE", default=0)
    offset = bpy.props.FloatProperty(name="Offset")
    span = bpy.props.IntProperty(name="Span", min=0)
    extrude = bpy.props.FloatProperty(name="Extrude", default=0)


class Vert(bpy.types.PropertyGroup):
    co = bpy.props.FloatVectorProperty(precision=6)


class Face(bpy.types.PropertyGroup):
    indices = bpy.props.IntVectorProperty()


class PerfectPattern(bpy.types.PropertyGroup):
    vertices = bpy.props.CollectionProperty(type=Vert)
    faces = bpy.props.CollectionProperty(type=Face)


class PerfectShapeProperties(bpy.types.PropertyGroup):
    objects = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    preview_verts_count = bpy.props.IntProperty(min=4, default=4)
    shape = bpy.props.PointerProperty(type=PerfectPattern)


@persistent
def handler(scene):
    if bpy.data.objects.is_updated:
        ps = bpy.context.window_manager.perfect_shape
        ps.objects.clear()
        for object in bpy.data.objects:
            if object.type == "MESH":
                item = ps.objects.add()
                item.name = object.name


def register():
    bpy.utils.register_class(Vert)
    bpy.utils.register_class(Face)
    bpy.utils.register_class(PerfectPattern)
    bpy.utils.register_class(PerfectShapeProperties)
    bpy.types.Object.perfect_pattern = bpy.props.PointerProperty(type=PerfectPattern)
    bpy.types.WindowManager.perfect_shape = bpy.props.PointerProperty(type=PerfectShapeProperties)
    bpy.app.handlers.scene_update_pre.append(handler)


def unregister():
    del bpy.types.Object.perfect_pattern
    del bpy.types.WindowManager.perfect_shape
    bpy.utils.unregister_class(Vert)
    bpy.utils.unregister_class(Face)
    bpy.utils.unregister_class(PerfectPattern)
    bpy.utils.unregister_class(PerfectShapeProperties)
    bpy.app.handlers.scene_update_pre.remove(handler)
