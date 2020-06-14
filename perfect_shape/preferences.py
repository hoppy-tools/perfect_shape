import bpy
import rna_keymap_ui
from bpy.types import Operator, AddonPreferences
from bl_keymap_utils.io import keyconfig_init_from_data

keymaps = []


def register_keymaps():
    circle_select = ("perfect_shape.select_and_shape",
                     {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},
                     {"items": [
                         ("perfect_shape.select_and_shape", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {}),
                         ("perfect_shape.perfect_shape", {"type": 'RET', "value": 'PRESS'}, {})
                     ]},)

    perfect_select = ("perfect_shape.perfect_select",
                      {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},
                      {"items": [
                          ("perfect_shape.perfect_select", {"type": 'LEFTMOUSE', "value": 'PRESS'},
                           {"properties": [("wait_for_input", False), ("mode", "SET")]})
                      ]},)


    keymaps.append(perfect_select)
    keymaps.append(circle_select)

    keyconfigs = bpy.context.window_manager.keyconfigs
    kc_defaultconf = keyconfigs.default
    kc_addonconf = keyconfigs.addon

    keyconfig_init_from_data(kc_defaultconf, keymaps)
    keyconfig_init_from_data(kc_addonconf, keymaps)


def register():
    register_keymaps()


def unregister():
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)
    keymaps.clear()
