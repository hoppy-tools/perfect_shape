import bpy
import os


_icon_cache = {}


def get_icon(icon_name):
    if icon_name is not None:
        icon_value = _icon_cache.get(icon_name)
        if icon_value is None:
            dirname = bpy.utils.system_resource('DATAFILES', "icons")
            filename = os.path.join(dirname, icon_name + ".dat")
            icon_value = bpy.app.icons.new_triangles_from_file(filename)
            _icon_cache[icon_name] = icon_value
        return icon_value
    else:
        return 0