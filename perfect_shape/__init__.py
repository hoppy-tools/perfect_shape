bl_info = {
    "name": "Perfect Shape",
    "author": "Dawid Czech",
    "version": (2, 0),
    "blender": (2, 80, 0),
    "category": "Mesh"
}

from bpy import utils

submodules = ['previews', 'properties', 'operators', 'user_interface']

register, unregister = utils.register_submodule_factory(__name__, submodules)
