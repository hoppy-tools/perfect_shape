from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_vector_3d, location_3d_to_region_2d
import math
import numpy

import bmesh


suzanne = [[-0.0, 0.709], [0.326, 0.669], [0.574, 0.444], [0.591, 0.236],
           [0.737, 0.343], [0.889, 0.366], [0.973, 0.231], [0.923, 0.039],
           [0.748, -0.073], [0.427, -0.09], [0.225, -0.315], [0.236, -0.681],
           [-0.0, -0.709], [-0.236, -0.681], [-0.225, -0.315], [-0.428, -0.09],
           [-0.748, -0.073], [-0.923, 0.039], [-0.973, 0.231], [-0.889, 0.366],
           [-0.737, 0.343], [-0.591, 0.236], [-0.574, 0.444], [-0.326, 0.669]]


class Shape:
    __slots__ = ("span", "span_cuts", "shift", "rotation", "is_generated", "points_distribution",
                 "points_distribution_smooth", "bmesh", "bmesh_original", "target_points_count")

    def __init__(self, points, points_original, span, span_cuts, shift, rotation, is_generated=True,
                 target_points_count=0, points_distribution="SEQUENCE", points_distribution_smooth=False):
        self.span = span
        self.span_cuts = span_cuts
        self.shift = shift
        self.rotation = rotation
        self.is_generated = is_generated

        self.points_distribution = points_distribution
        self.points_distribution_smooth = points_distribution_smooth

        self.bmesh = self.create_bmesh(points)
        self.bmesh_original = self.create_bmesh_original(points_original)
        self.target_points_count = target_points_count

        self.apply_span()
        #self.apply_subdivide()

    def __del__(self):
        self.bmesh.free()
        self.bmesh_original.free()
        self.clear_cache()

    def create_bmesh(self, points):
        _bmesh = bmesh.new()
        for p in points:
            _bmesh.verts.new((*p, 0.0))

        _bmesh.faces.new(_bmesh.verts)
        _bmesh.faces.ensure_lookup_table()
        return _bmesh

    def create_bmesh_original(self, points_original):
        _bmesh = bmesh.new()
        for p in points_original:
            _bmesh.verts.new((*p, 0.0))
        return _bmesh

    def apply_subdivide(self):
        points_count = self.get_points_count()
        if self.target_points_count > points_count:
            extra_points = self.target_points_count - points_count
            full_cuts, cuts = divmod(extra_points, points_count)
            if full_cuts:
                bmesh.ops.subdivide_edges(self.bmesh, edges=self.bmesh.edges, cuts=full_cuts)
            if cuts:
                self.bmesh.faces[0].loops.index_update()
                bm_set_index_by_loops(self.bmesh.faces[0].loops, 'edge')
                self.bmesh.edges.sort()
                if self.points_distribution == "EVEN":
                    mask = even_elements_mask(len(self.bmesh.edges), len(self.bmesh.edges)-cuts)
                    edges = numpy.compress(mask, self.bmesh.edges, axis=0)
                else:
                    edges = self.bmesh.edges[:cuts]
                for edge in edges:
                    bmesh.ops.subdivide_edges(self.bmesh, edges=[edge], cuts=1)

        if self.points_distribution_smooth:
            bmesh.ops.smooth_vert(self.bmesh, verts=self.bmesh.verts,
                                  factor=0.5, use_axis_x=True, use_axis_y=True)

        self.bmesh.faces.ensure_lookup_table()
        self.bmesh.faces[0].loops.index_update()
        self.clear_cache()

    def apply_rotation(self):
        bmesh.ops.rotate(
            self.bmesh,
            verts=self.bmesh.verts,
            cent=(0.0, 0.0, 0.0),
            matrix=Matrix.Rotation(-self.rotation, 3, 'Z'))

        bmesh.ops.rotate(
            self.bmesh_original,
            verts=self.bmesh_original.verts,
            cent=(0.0, 0.0, 0.0),
            matrix=Matrix.Rotation(-self.rotation, 3, 'Z'))

    def get_points(self):
        return [v.co.xy for v in self.bmesh.verts]

    def get_points_original(self):
        return [v.co.xy for v in self.bmesh_original.verts]

    def get_points_count(self):
        return len(self.bmesh.verts)

    def clear_cache(self):
        pass

    def sort_vets_by_loop(self):
        self.bmesh.faces.ensure_lookup_table()
        loops = self.bmesh.faces[0].loops
        loops.index_update()
        for idx, loop in enumerate(loops):
            loop.vert.index = idx
        self.bmesh.verts.sort()

    def apply_span(self):
        if self.span < 0:
            if self.is_generated:
                edges = self.bmesh.edges[:]
                edges_count = len(edges)
                cuts, rest = divmod(len(self.get_points_original()), edges_count)
                for e in edges:
                    x, rest = (1, rest-1) if rest else (0, rest)
                    bmesh.ops.subdivide_edges(self.bmesh, edges=[e], cuts=cuts-1+x, quad_corner_type="FAN")
                self.sort_vets_by_loop()
            else:
                verts = self.bmesh.verts[:]
                dissolved = 0
                for i in range(abs(self.span)):
                    if len(verts) > 3:
                        v = verts.pop()
                        bmesh.ops.dissolve_verts(self.bmesh, verts=[v])
                        dissolved += 1
                    else:
                        self.bmesh.faces.ensure_lookup_table()
                        self.bmesh.faces[0].loops.index_update()
                        verts = self.bmesh.faces[0].verts[:]
                if dissolved:
                    pass

        elif self.span > 0:
            if self.is_generated:
                verts_to_dissolve = self.bmesh.verts[-self.span:]
                bmesh.ops.dissolve_verts(self.bmesh, verts=verts_to_dissolve)
                if self.span_cuts:
                    self.bmesh.edges.ensure_lookup_table()
                    bmesh.ops.subdivide_edges(self.bmesh, edges=[self.bmesh.edges[-1]], cuts=self.span_cuts)
                    self.sort_vets_by_loop()
            # not self.is_generated:
            # final_span = self.span
            #
            # self.bmesh.faces.ensure_lookup_table()
            # self.bmesh.faces[0].loops.index_update()
            # # bmesh.ops.subdivide_edges(self.bmesh,
            # #
            # #                           edges=[l.edge for l in self.bmesh.faces[0].loops[:final_span]],
            # #                           cuts=1)
            # self.bmesh.faces.ensure_lookup_table()


        self.bmesh.faces.ensure_lookup_table()
        self.clear_cache()

    def apply_shift(self, points, points_count=None):
        if points_count is None:
            points_count = len(points)
        return points[self.shift % points_count:] + points[:self.shift % points_count]

    def apply_distribution(self):
        if self.target_points_count:
            if self.points_distribution == "SEQUENCE":
                if self.points_count_original > self.target_points_count:
                    self.points = self.points[:self.target_points_count]
            elif self.points_distribution == "EVEN":
                if self.points_count_original > self.target_points_count:
                    mask = even_elements_mask(self.points_count_original,
                                              self.points_count_original - self.target_points_count)
                    self.points = numpy.compress(mask, self.points, axis=0)

    @staticmethod
    def _get_final_points_count_n_span(points_count, span, span_cuts, min_points, max_points, target_points_count=0):
        if span_cuts == -1:
            span_cuts = span
        if span > 0:
            final_span_cuts = min(span, span_cuts)
        else:
            final_span_cuts = 0

        final_span = span
        if final_span_cuts:
            final_span = max(1, final_span)

        if target_points_count:
            final_span += points_count - target_points_count
        if span < 0:
            final_span = min(abs(span), points_count - min_points)
            final_span *= -1

        if target_points_count:
            final_points_count = max(points_count - target_points_count, min_points)
        else:
            final_points_count = max(points_count + final_span - final_span_cuts, min_points)

        original_points_count = points_count
        if max_points:
            original_points_count = min(points_count, max_points)
            final_points_count = min(final_points_count, max_points)
            final_span = min(final_span, max_points - final_points_count)
        return original_points_count, final_points_count, final_span, final_span_cuts


    @classmethod
    def Circle(cls, points_count, span, span_cuts, shift, rotation, max_points, **extra_params):
        original_points_count, points_count, span, span_cuts = cls._get_final_points_count_n_span(points_count, span,
                                                                                                  span_cuts,
                                                                                                  3, max_points)
        points = list(circle_generator(points_count))
        original_points = list(circle_generator(original_points_count))

        return cls(points, original_points, span, span_cuts, shift, rotation)

    @classmethod
    def Quadrangle(cls, points_count, span, span_cuts, shift, rotation, max_points, *,
                   ratio=(1, 1), **extra_params):
        original_points_count, points_count, span, span_cuts = cls._get_final_points_count_n_span(points_count, span,
                                                                                                  span_cuts,
                                                                                                  3, max_points)
        points = list(quadrangle_generator(points_count, ratio))
        original_points = list(quadrangle_generator(original_points_count, ratio))

        return cls(points, original_points, span, span_cuts, shift, rotation)

    @classmethod
    def Object(cls, points_count, span, span_cuts, shift, rotation, max_points, *,
               points_distribution="SEQUENCE", points_distribution_smooth=False, **extra_params):
        original_points_count, final_points_count, final_span, span_cuts = cls._get_final_points_count_n_span(points_count, span, span_cuts,
                                                                                                   3, max_points,
                                                                                                   points_count)
        return cls(suzanne, suzanne, span, span_cuts, shift, rotation, is_generated=False, target_points_count=points_count,
                   points_distribution=points_distribution, points_distribution_smooth=points_distribution_smooth)


def circle_generator(verts_count):
    for i in range(verts_count):
        theta = (2.0 * math.pi * i / verts_count) + math.pi / 2
        yield (-math.cos(theta), math.sin(theta))


def quadrangle_generator(verts_count, ratio):
    verts_count_odd = verts_count - verts_count % 2
    max_segments = verts_count_odd // 2 - 1

    x = verts_count_odd / 2 / sum(ratio)

    segments_a = max(1, min(round(ratio[0] * x), max_segments))
    max_segments = max_segments - segments_a + 1
    segments_b = max(1, min(round(ratio[1] * x), max_segments))
    segments = [segments_a, segments_b, segments_a, segments_b]

    free_points = verts_count - sum(segments)
    if free_points > 0:
        if verts_count % 2 == 0:
            if ratio[0] > ratio[1]:
                segments[0] += free_points // 2
                segments[2] += free_points // 2
            else:
                segments[1] += free_points // 2
                segments[3] += free_points // 2
        else:
            i = 0
            while sum(segments) < verts_count:
                segments[i % len(segments)] += 1
                i += 1

    sizes = (1.6, 1.6)
    coords = (-1, 1, 1, -1)

    for side, count in enumerate(segments):
        odd_side = side % 2
        segment_len = sizes[odd_side] / count
        _range = (0, count, 1) if side < 2 else (count, 0, -1)
        for i in range(*_range):
            v = [segment_len * i - sizes[odd_side] / 2, sizes[odd_side ^ 1] / 2 * coords[side]]
            yield v if odd_side else v[2::-1]


def star_generator(verts_count):
    pass


def bm_set_index_by_loops(loops, key):
    for idx, loop in enumerate(loops):
        geom = getattr(loop, key)
        geom.index = idx


def even_elements_mask(n, m):
    if m > n / 2:
        mask = numpy.zeros(n, dtype=int)
        m = n - m
        fill = True
    else:
        mask = numpy.ones(n, dtype=int)
        fill = False
    q, r = divmod(n, m)
    indices = [q*i + min(i, r) for i in range(m)]
    mask[indices] = fill
    return mask


def get_symmetry_points_weight(points):
    points_len = len(points)
    split = points_len // 2
    results = []
    for idx, point in enumerate(points):
        point_results = []
        for s in range(1, split):
            prev_idx = idx-1 % (points_len if idx-1 > 0 else -points_len)
            prev_point = points[prev_idx-1]
            next_idx = idx+1 % points_len
            next_point = points[next_idx-1]
            angle_diff = prev_point.angle(point) - next_point.angle(point)
            point_results.append(angle_diff)
        results.append((idx, sum(point_results)))
    results.sort(key=lambda i: i[1])
    return results


def get_boundary_edges(faces):
    result = []

    def get_group(face, faces):
        group = []
        for edge in face.edges:
            tree = [[], []]
            for idx, edge_face in enumerate(edge.link_faces):
                if edge_face not in group and edge_face in faces:
                    group.append(edge_face)
                    faces.remove(edge_face)
                    if faces:
                        tree[idx] = get_group(edge_face, faces)
            group.extend(tree[0])
            group.extend(tree[1])

        return group

    while len(faces) > 0:
        group = get_group(faces[0], faces)
        edges = []
        for face in group:
            for edge in face.edges:
                for edge_face in edge.link_faces:
                    if edge_face not in group:
                        edges.append(edge)
        result.append((edges, group))
    return result


def get_loop(edges, vert=None):
    if vert is None:
        edge = edges[0]
        edges.remove(edge)
        success_0, is_boundary_0, verts_0, edges_0 = get_loop(edges, edge.verts[0])
        success_1, is_boundary_1, verts_1, edges_1 = get_loop(edges, edge.verts[1])
        if len(verts_0) > 0:
            edges_0.reverse()
            verts_0.reverse()
            verts_0 = verts_0 + [v for v in edge.verts if v not in verts_0]
        if len(verts_1) > 0:
            if len(verts_0) == 0:
                verts_1 = verts_1 + [v for v in edge.verts if v not in verts_1]
        is_boundary = is_boundary_0 and is_boundary_1
        success = success_0 and success_1
        if edge.is_boundary:
            is_boundary = True
        return success, is_boundary, verts_0 + verts_1, edges_0 + [edge] + edges_1

    link_edges = [e for e in vert.link_edges if e in edges]

    if len(link_edges) == 1:
        edge = link_edges[0]
        vert, = set(edge.verts) - {vert}
        edges.remove(edge)
        success, is_boundary, verts_, edges_ = get_loop(edges, vert)
        if edge.is_boundary:
            is_boundary = True
        return success, is_boundary, [vert] + verts_, [edge] + edges_

    elif len(link_edges) > 1:
        for edge in link_edges:
            edges.remove(edge)
        return False, False, [], []

    return True, False, [], []


def get_loops(edges, faces=None):
    edges = edges[:]
    loops = []

    if faces:
        for group in get_boundary_edges(faces[:]):
            success, is_boundary, loop_verts, loop_edges = get_loop(group[0])
            is_cyclic = any((v for v in loop_edges[0].verts if v in loop_edges[-1].verts))
            loops.append(((loop_verts, loop_edges, group[1]), is_cyclic, is_boundary))

        for face in faces:
            for face_edge in face.edges:
                if face_edge.select and face_edge in edges:
                    edges.remove(face_edge)

    while len(edges) > 0:
        success, is_boundary, loop_verts, loop_edges = get_loop(edges)
        if success:
            if len(loop_verts) < 2:
                is_cyclic = False
            else:
                is_cyclic = any((v for v in loop_edges[0].verts if v in loop_edges[-1].verts))
            loops.append(((loop_verts, loop_edges, []), is_cyclic, is_boundary))

    return loops


def is_clockwise(forward, center, verts):
    return forward.dot((verts[0].co - center).cross(verts[1].co - center)) > 0


def is_backface(bm_element, eye_location):
    return (bm_element.co - eye_location).dot(bm_element.normal) >= 0.0


def matrix_decompose_4x4(matrix):
    loc, rot, sca = matrix.decompose()
    matrix_rot = rot.to_matrix().to_4x4()
    matrix_sca = Matrix()
    matrix_sca[0][0], matrix_sca[1][1], matrix_sca[2][2] = sca
    return Matrix.Translation(loc), matrix_rot, matrix_sca


def points_3d_to_region_2d(points, region, rv3d):
    return [location_3d_to_region_2d(region, rv3d, p) for p in points]


def create_kdtree(points):
    kd = KDTree(len(points))
    kd_insert_func = kd.insert
    v_len = len(points[0])
    if v_len == 2:
        def kd_insert(co, idx): kd_insert_func((*co, 0.0), idx)
    else:
        kd_insert = kd_insert_func

    for i, v in enumerate(points):
        kd_insert(v, i)
    kd.balance()
    return kd
