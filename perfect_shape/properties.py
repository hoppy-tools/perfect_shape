import bpy


class PatternVert(bpy.types.PropertyGroup):
    co = bpy.props.FloatVectorProperty(precision=6)


def register():
    bpy.utils.register_class(PatternVert)
    bpy.types.Object.perfect_pattern = bpy.props.CollectionProperty(type=PatternVert)


def unregister():
    del bpy.types.Object.perfect_pattern
    bpy.utils.unregister_class(PatternVert)
