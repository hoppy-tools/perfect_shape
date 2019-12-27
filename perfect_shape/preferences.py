import bpy
import rna_keymap_ui
from bpy.types import Operator, AddonPreferences
from bl_keymap_utils.io import keyconfig_init_from_data

keymaps = []


def register_keymaps():
    circle_select = ("perfect_shape.select_and_shape",
                     {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},
                     {"items": [
                         ("perfect_shape.select_and_shape", {"type": 'LEFTMOUSE', "value": 'PRESS'},
                          {"properties": [("select_method", 'CIRCLE'), ("select_mode", 'SET')]}),
                         ("perfect_shape.select_and_shape", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True},
                          {"properties": [("select_method", 'CIRCLE'), ("select_mode", 'ADD')]}),
                         ("perfect_shape.select_and_shape", {"type": 'LEFTMOUSE', "value": 'PRESS', "ctrl": True},
                          {"properties": [("select_method", 'CIRCLE'), ("select_mode", 'SUB')]}),
                     ]},)

    keyconfigs = bpy.context.window_manager.keyconfigs
    kc_defaultconf = keyconfigs.default
    kc_addonconf = keyconfigs.addon

    keyconfig_init_from_data(kc_defaultconf, [circle_select])
    keyconfig_init_from_data(kc_addonconf, [circle_select])


def register():
    register_keymaps()


def unregister():
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)
    keymaps.clear()
