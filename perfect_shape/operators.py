import bpy
import bmesh
import mathutils
import math

from builtins import print
from mathutils import Vector, Matrix
from mathutils.geometry import box_fit_2d
from mathutils.geometry import normal as calculate_normal
from functools import reduce
from perfect_shape.utils import prepare_loops, is_clockwise, select_only
from perfect_shape.user_interface import PerfectShapeUI


class PerfectPattern(bpy.types.Operator):
    bl_idname = "mesh.perfect_pattern"
    bl_label = "Mark Perfect Pattern"

    def execute(self, context):
        object = context.object
        object.update_from_editmode()

        object_bm = bmesh.from_edit_mesh(object.data)
        selected_edges = [e for e in object_bm.edges if e.select]
        loops = prepare_loops(selected_edges[:])

        if loops is None:
            self.report({'WARNING'}, "Please select boundary loop of selected area.")
            return {'CANCELLED'}

        if len(loops) > 1:
            self.report({'WARNING'}, "Please select one loop.")
            return {'CANCELLED'}

        object.perfect_pattern.clear()
        loop_verts = loops[0][0][0]
        shape_bm = bmesh.new()
        for loop_vert in loop_verts:
            vert = object.perfect_pattern.add()
            vert.co = loop_vert.co.copy()
            shape_bm.verts.new(loop_vert.co.copy())


        forward = reduce(lambda v1, v2: v1.normal.copy() if isinstance(v1, bmesh.types.BMVert)
                         else v1.copy() + v2.normal.copy(), loop_verts).normalized()

        shape_bm.faces.new(shape_bm.verts)
        shape_bm.faces.ensure_lookup_table()
        center = shape_bm.faces[0].calc_center_median()
        matrix_rotation = forward.to_track_quat('Z', 'X').to_matrix().to_4x4()
        matrix_rotation.transpose()
        matrix = matrix_rotation * Matrix.Translation(-center)

        for pattern_vert in object.perfect_pattern:
            pattern_vert.co = matrix * Vector(pattern_vert.co)

        return {'FINISHED'}


class PerfectShape(bpy.types.Operator, PerfectShapeUI):
    bl_idname = "mesh.perfect_shape"
    bl_label = "To Perfect Shape"
    bl_options = {"REGISTER", "UNDO"}

    shape_types = [("PATTERN", "Perfect Pattern", "", "MESH_DATA", 1),
                   ("OBJECT", "Object", "", "MESH_CUBE", 2),
                   ("RECTANGLE", "Rectangle", "", "MESH_PLANE", 3),
                   ("CIRCLE", "Circle", "", "MESH_CIRCLE", 4)]

    fill_types = [("ORIGINAL", "Original", "", "", 1),
                  ("COLLAPSE", "Collapse", "", "", 2),
                  ("HOLE", "Hole", "", "", 3),
                  ("NGON", "Ngon", "", "", 4)]

    projection_types = [("NORMAL", "Normal", "", "", 1),
                        ("X", "X", "", "", 2),
                        ("Y", "Y", "", "", 3),
                        ("Z", "Z", "", "", 4)]

    shape = bpy.props.EnumProperty(name="A perfect", items=shape_types, default="CIRCLE")
    projection = bpy.props.EnumProperty(name="Projection", items=projection_types, default="NORMAL")
    invert_projection = bpy.props.BoolProperty(name="Invert Direction", default=False)
    use_ray_cast = bpy.props.BoolProperty(name="Wrap to surface", default=True)
    fill_type = bpy.props.EnumProperty(name="Fill Type", items=fill_types, default="ORIGINAL")
    fill_flatten = bpy.props.BoolProperty(name="Flatten", default=False)

    active_as_first = bpy.props.BoolProperty(name="Active as First", default=False)
    shape_rotation = bpy.props.BoolProperty(name="Shape Rotation", default=False)

    ratio_a = bpy.props.IntProperty(name="Ratio a", min=1, default=1)
    ratio_b = bpy.props.IntProperty(name="Ratio b", min=1, default=1)
    is_square = bpy.props.BoolProperty(name="Square", default=False)

    target = bpy.props.StringProperty(name="Object")
    factor = bpy.props.FloatProperty(name="Factor", min=0.0, max=1.0, default=1.0)
    inset = bpy.props.FloatProperty(name="Inset", min=0.0, default=0)
    outset = bpy.props.FloatProperty(name="Outset", min=0.0, default=0)
    shift = bpy.props.IntProperty(name="Shift")
    rotation = bpy.props.FloatProperty(name="Rotation", subtype="ANGLE", default=0)
    offset = bpy.props.FloatProperty(name="Offset")
    span = bpy.props.IntProperty(name="Span", min=0)
    extrude = bpy.props.FloatProperty(name="Extrude", default=0)
    relax = bpy.props.IntProperty(name="Relax", min=0, max=4)

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH" and context.object is not None

    def check(self, context):
        return True



    def execute(self, context):
        object = context.object
        object.update_from_editmode()

        object_bm = bmesh.from_edit_mesh(object.data)

        selected_edges = [e for e in object_bm.edges if e.select]
        selected_verts = [v for v in object_bm.verts if v.select]
        selected_verts_fin = []

        if len(selected_edges) == 0:
            self.report({'WARNING'}, "Please select edges.")
            return {'CANCELLED'}

        loops = prepare_loops(selected_edges[:])

        if loops is None:
            self.report({'WARNING'}, "Please select boundary loop(s) of selected area(s).")
            return {'CANCELLED'}

        object_bvh = mathutils.bvhtree.BVHTree.FromObject(object, context.scene, deform=False)

        for (loop_verts, loop_edges), is_loop_cyclic, is_loop_boundary in loops:
            if len(loop_edges) < 3:
                continue
            loop_verts_len = len(loop_verts)
            if self.projection == "NORMAL":
                if is_loop_boundary:
                    forward = calculate_normal([v.co for v in loop_verts])
                else:
                    forward = reduce(
                        lambda v1, v2: v1.normal.copy() if isinstance(v1, bmesh.types.BMVert)
                        else v1.copy() + v2.normal.copy(), loop_verts).normalized()
            else:
                forward = Vector([v == self.projection for v in ["X", "Y", "Z"]])

            if self.invert_projection:
                forward.negate()

            shape_bm = bmesh.new()

            if context.space_data.pivot_point == "CURSOR":
                center = object.matrix_world.copy() * context.scene.cursor_location.copy()
            else:
                for loop_vert in loop_verts:
                    shape_bm.verts.new(loop_vert.co.copy())
                shape_bm.faces.new(shape_bm.verts)
                shape_bm.faces.ensure_lookup_table()
                if context.space_data.pivot_point == 'BOUNDING_BOX_CENTER':
                    center = shape_bm.faces[0].calc_center_bounds()
                else:
                    center = shape_bm.faces[0].calc_center_median()

                shape_bm.clear()

            matrix_rotation = forward.to_track_quat('Z', 'X').to_matrix().to_4x4()
            matrix_translation = Matrix.Translation(center)

            shape_bm = bmesh.new()
            shape_verts = None
            if self.shape == "CIRCLE":
                diameter = sum([e.calc_length() for e in loop_edges]) / (2*math.pi)
                diameter += self.offset
                shape_segments = loop_verts_len + self.span
                shape_verts = bmesh.ops.create_circle(shape_bm, segments=shape_segments,
                                                      diameter=diameter, matrix=matrix_translation*matrix_rotation)
                shape_verts = shape_verts["verts"]
            elif self.shape == "RECTANGLE":
                if loop_verts_len % 2 > 0:
                    self.report({'WARNING'}, "An odd number of edges.")
                    del shape_bm
                    return {'FINISHED'}
                size = sum([e.calc_length() for e in loop_edges])

                size_a = (size / 2) / (self.ratio_a + self.ratio_b) * self.ratio_a
                size_b = (size / 2) / (self.ratio_a + self.ratio_b) * self.ratio_b
                seg_a = (loop_verts_len / 2) / (self.ratio_a + self.ratio_b) * self.ratio_a
                seg_b = int((loop_verts_len / 2) / (self.ratio_a + self.ratio_b) * self.ratio_b)
                if seg_a % 1 > 0:
                    self.report({'WARNING'}, "Incorrect sides ratio.")
                    seg_a += 1
                    seg_b += 2
                seg_a = int(seg_a)
                if self.is_square:
                    size_a = (size_a + size_b) / 2
                    size_b = size_a
                seg_len_a = size_a / seg_a
                seg_len_b = size_b / seg_b

                for i in range(seg_a):
                    shape_bm.verts.new(Vector((size_b/2*-1, seg_len_a*i-(size_a/2), 0)))
                for i in range(seg_b):
                    shape_bm.verts.new(Vector((seg_len_b*i-(size_b/2), size_a/2, 0)))
                for i in range(seg_a, 0, -1):
                    shape_bm.verts.new(Vector((size_b/2, seg_len_a*i-(size_a/2), 0)))
                for i in range(seg_b, 0, -1):
                    shape_bm.verts.new(Vector((seg_len_b*i-(size_b/2), size_a/2*-1, 0)))

                shape_verts = shape_bm.verts[:]
                bmesh.ops.scale(shape_bm, vec=Vector((1, 1, 1))*(1+self.offset), verts=shape_verts)
                bmesh.ops.transform(shape_bm, verts=shape_verts, matrix=matrix_translation*matrix_rotation)
            elif self.shape == "PATTERN":
                if len(object.perfect_pattern) == 0:
                    self.report({'WARNING'}, "Empty Pattern Data.")
                    del shape_bm
                    return {'FINISHED'}
                if len(object.perfect_pattern) != len(loop_verts):
                    self.report({'WARNING'}, "Pattern and loop vertices count must be the same.")
                    del shape_bm
                    return {'FINISHED'}
                for pattern_vert in object.perfect_pattern:
                    shape_bm.verts.new(Vector(pattern_vert.co))
                shape_verts = shape_bm.verts[:]
                bmesh.ops.scale(shape_bm, vec=Vector((1, 1, 1))*(1+self.offset), verts=shape_verts)
                bmesh.ops.transform(shape_bm, verts=shape_verts, matrix=matrix_translation*matrix_rotation)
            elif self.shape == "OBJECT":
                if self.target in bpy.data.objects:
                    shape_object = bpy.data.objects[self.target]
                    shape_bm.from_object(shape_object, context.scene)
                    loops = prepare_loops(shape_bm.edges[:])
                    if loops is None or len(loops) > 1:
                        self.report({'WARNING'}, "Wrong mesh data.")
                        del shape_bm
                        return {'FINISHED'}

                    shape_verts = shape_bm.verts[:]
                    bmesh.ops.scale(shape_bm, vec=Vector((1, 1, 1))*(1+self.offset), verts=shape_verts)
                    bmesh.ops.transform(shape_bm, verts=shape_verts, matrix=matrix_translation*matrix_rotation)

            if shape_verts is not None and len(shape_verts) > 0:
                if not is_clockwise(forward, center, loop_verts):
                    loop_verts.reverse()
                    loop_edges.reverse()
                if not is_clockwise(forward, center, shape_verts):
                    shape_verts.reverse()

                loop_angle = box_fit_2d([(matrix_rotation.transposed() * v.co).to_2d() for v in loop_verts])
                shape_angle = box_fit_2d([(matrix_rotation.transposed() * v.co).to_2d() for v in shape_verts])

                if abs(abs(loop_angle) - abs(shape_angle)) <= 0.01:
                    loop_angle = 0
                correct_angle = loop_angle + self.rotation

                if self.shape_rotation:
                    correct_angle -= shape_angle

                if correct_angle != 0 and not self.active_as_first:
                    bmesh.ops.rotate(shape_bm, verts=shape_verts, cent=center,
                                     matrix=Matrix.Rotation(-correct_angle, 3, forward))

                active = object_bm.select_history.active
                if self.active_as_first and isinstance(active, bmesh.types.BMVert) and active in loop_verts:
                    shift = loop_verts.index(active)
                else:
                    kd_tree = mathutils.kdtree.KDTree(len(loop_verts))
                    for idx, loop_vert in enumerate(loop_verts):
                        kd_tree.insert(loop_vert.co, idx)
                    kd_tree.balance()
                    shape_first_idx = kd_tree.find(shape_verts[0].co)[1]
                    shift = shape_first_idx + self.shift
                if shift != 0:
                    loop_verts = loop_verts[shift % len(loop_verts):] + loop_verts[:shift % len(loop_verts)]

                if not is_loop_boundary and self.use_ray_cast:
                    for shape_vert in shape_verts:
                        co = shape_vert.co
                        ray_cast_data = object_bvh.ray_cast(co, forward)
                        if ray_cast_data[0] is None:
                            ray_cast_data = object_bvh.ray_cast(co, -forward)
                        if ray_cast_data[0] is not None:
                            shape_vert.co = ray_cast_data[0]

                for idx, vert in enumerate(loop_verts):
                    vert.co = vert.co.lerp(shape_verts[idx].co, self.factor)

                if not is_loop_boundary and is_loop_cyclic:
                    object_bm.select_flush_mode()
                    select_only(object_bm, loop_edges, {"EDGE"})
                    bpy.ops.mesh.loop_to_region()  # Ugly.
                    inset_faces = [f for f in object_bm.faces[:] if f.select]

                    if self.fill_type != "ORIGINAL":
                        smooth = inset_faces[0].smooth
                        bmesh.ops.delete(object_bm, geom=inset_faces, context=5)

                        inset_faces = []
                        center_vert = object_bm.verts.new(center)
                        if self.use_ray_cast:
                            ray_cast_data = object_bvh.ray_cast(center_vert.co, forward)
                            if ray_cast_data[0] is None:
                                ray_cast_data = object_bvh.ray_cast(center_vert.co, -forward)
                            if ray_cast_data[0] is not None:
                                center_vert.co = ray_cast_data[0]
                        for idx, vert in enumerate(loop_verts):
                            new_face = object_bm.faces.new((center_vert, vert, loop_verts[(idx+1) % loop_verts_len]))
                            new_face.smooth = smooth
                            inset_faces.append(new_face)
                        bmesh.ops.recalc_face_normals(object_bm, faces=inset_faces)

                    selected_co = []
                    for vert in selected_verts:
                        if vert.is_valid:
                            selected_co.append(vert.co.copy())

                    outset_region_faces = []
                    if self.outset > 0.0:
                        outset_region_faces = bmesh.ops.inset_region(object_bm, faces=inset_faces,
                                                                     thickness=self.outset, use_even_offset=True,
                                                                     use_interpolate=True, use_outset=True)
                        outset_region_faces = outset_region_faces["faces"]

                    inset_region_faces = []
                    if self.inset > 0.0:
                        inset_region_faces = bmesh.ops.inset_region(object_bm, faces=inset_faces, thickness=self.inset,
                                                                    use_even_offset=True, use_interpolate=True)
                        inset_region_faces = inset_region_faces["faces"]

                    new_selected_verts = []

                    for face in set(inset_region_faces+inset_faces):
                        for vert in face.verts:
                            if vert.co in selected_co:
                                new_selected_verts.append(vert)
                                selected_co.remove(vert.co)

                    selected_verts_fin.append(new_selected_verts)
                    select_only(object_bm, new_selected_verts, {"EDGE"})

                    if self.fill_type == "HOLE":
                        bmesh.ops.delete(object_bm, geom=inset_faces, context=5)
                        inset_faces = []
                    elif self.fill_type == "NGON":
                        inset_faces = [bmesh.utils.face_join(inset_faces)]

                    if self.fill_flatten and self.extrude == 0:
                        verts = list(set(reduce(lambda v1, v2: list(v1) + list(v2),
                                                [v.verts for v in inset_region_faces + inset_faces])))
                        matrix = Matrix.Translation(-center)
                        bmesh.ops.rotate(object_bm, cent=center, matrix=matrix_rotation.transposed(), verts=verts)
                        bmesh.ops.scale(object_bm, vec=Vector((1, 1, +0)), space=matrix, verts=verts)
                        bmesh.ops.rotate(object_bm, cent=center, matrix=matrix_rotation, verts=verts)

                    bmesh.ops.recalc_face_normals(object_bm, faces=outset_region_faces+inset_region_faces+inset_faces)
                    if self.extrude != 0:
                        extrude_geom = bmesh.ops.extrude_face_region(object_bm, geom=inset_region_faces+inset_faces)
                        verts = [v for v in extrude_geom['geom'] if isinstance(v, bmesh.types.BMVert)]

                        if self.fill_flatten:
                            matrix = Matrix.Translation(-center)
                            bmesh.ops.rotate(object_bm, cent=center, matrix=matrix_rotation.transposed(), verts=verts)
                            bmesh.ops.scale(object_bm, vec=Vector((1.0, 1.0, 0.001)), space=matrix, verts=verts)
                            bmesh.ops.rotate(object_bm, cent=center, matrix=matrix_rotation, verts=verts)
                        bmesh.ops.delete(object_bm, geom=inset_region_faces+inset_faces, context=5)
                        bmesh.ops.translate(object_bm,
                                            verts=verts,
                                            vec=forward * self.extrude)
            del shape_bm
        if selected_verts_fin:
            select_only(object_bm, reduce(lambda x, y: x + y, selected_verts_fin), {"EDGE"})
        object_bm.select_flush(True)
        del object_bvh
        bmesh.update_edit_mesh(object.data)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        ret = self.execute(context)
        if ret == {'FINISHED'}:
            wm.invoke_props_popup(self, event)
        return ret


def register():
    bpy.utils.register_class(PerfectShape)
    bpy.utils.register_class(PerfectPattern)

def unregister():
    bpy.utils.unregister_class(PerfectPattern)
    bpy.utils.unregister_class(PerfectShape)