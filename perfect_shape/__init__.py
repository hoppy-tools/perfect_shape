bl_info = {
    "name": "Perfect Shape",
    "author": "Dawid Czech",
    "version": (1, 1),
    "blender": (2, 76, 0),
    "wiki_url": "http://hophead.ninja/product/perfect_shape",
    "category": "Mesh"
}

import bpy
from perfect_shape import properties
from perfect_shape import operators
from perfect_shape import user_interface


def register():
    properties.register()
    operators.register()
    user_interface.register()


def unregister():
    user_interface.unregister()
    operators.unregister()
    properties.unregister()

if __name__ == "__main__":
    register()