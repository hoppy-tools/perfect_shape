import atexit
from functools import reduce
from operator import add
from mathutils import Vector, Matrix
import math
import numpy

import bmesh

from .previews import PREVIEW_MAX_POINTS, render_preview

previews_shapes = {}
shape = None

suzanne = [[-0.0, 0.709], [0.326, 0.669], [0.574, 0.444], [0.591, 0.236],
           [0.737, 0.343], [0.889, 0.366], [0.973, 0.231], [0.923, 0.039],
           [0.748, -0.073], [0.427, -0.09], [0.225, -0.315], [0.236, -0.681],
           [-0.0, -0.709], [-0.236, -0.681], [-0.225, -0.315], [-0.428, -0.09],
           [-0.748, -0.073], [-0.923, 0.039], [-0.973, 0.231], [-0.889, 0.366],
           [-0.737, 0.343], [-0.591, 0.236], [-0.574, 0.444], [-0.326, 0.669]]


def generate_previews_shapes(points_count, ratio, span, shift, rotation, key=None, target_points_count=None,
                             points_distribution="SEQUENCE", points_distribution_smooth=False):
    global previews_shapes

    shapes = {"CIRCLE":     lambda: Shape.Circle(points_count, span, shift, rotation,
                                                 max_points=PREVIEW_MAX_POINTS),

              "RECTANGLE":  lambda: Shape.Rectangle(points_count, ratio, span, shift, rotation,
                                                    max_points=PREVIEW_MAX_POINTS),

              "OBJECT":     lambda: Shape.Object(points_count, span, shift, rotation,
                                                 max_points=PREVIEW_MAX_POINTS,
                                                 target_points_count=target_points_count,
                                                 points_distribution=points_distribution,
                                                 points_distribution_smooth=points_distribution_smooth)}

    if key is not None:
        previews_shapes[key] = shapes[key]()
        render_preview("shape_types", key, previews_shapes[key])
    else:
        for key, func in shapes.items():
            previews_shapes[key] = func()
            render_preview("shape_types", key, previews_shapes[key])

    if points_count + span >= PREVIEW_MAX_POINTS:
        return PREVIEW_MAX_POINTS


def circle_generator(verts_count):
    for i in range(verts_count):
        theta = (2.0 * math.pi * i / verts_count) + math.pi / 2
        yield (-math.cos(theta), math.sin(theta))


def rectangle_generator(verts_count, ratio):
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


def bm_set_index_by_loops(loops, key):
    for idx, loop in enumerate(loops):
        geom = getattr(loop, key)
        geom.index = idx


class Shape:
    def __init__(self, points, points_original, span, shift, rotation, is_generated=True,
                 target_points_count=0, points_distribution="SEQUENCE", points_distribution_smooth=False):
        self.bmesh = bmesh.new()
        self.bmesh_original = bmesh.new()

        self.points = list(points)
        self.points_count = len(self.points)
        self.points_original = list(points_original)
        self.points_count_original = len(self.points_original)

        self.target_points_count = target_points_count
        self.points_distribution = points_distribution
        self.points_distribution_smooth = points_distribution_smooth

        self.span = min(self.points_count_original-3, span)

        self.shift = shift
        self.rotation = rotation
        self.is_generated = is_generated

        self.calc_all_points()

    def init_bmesh(self):
        for p in self.points[:max(self.points_count_original-self.span, 3)]:
            self.bmesh.verts.new((*p, 0.0))
        self.bmesh.faces.new(self.bmesh.verts)
        self.bmesh.faces.ensure_lookup_table()

        if self.target_points_count > self.points_count:
            extra_points = self.target_points_count - self.points_count
            full_cuts, cuts = divmod(extra_points, self.points_count)

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

        for p in self.points_original:
            self.bmesh_original.verts.new((*p, 0.0))


    def calc_all_points(self):
        self.apply_shift()
        self.apply_distribution()

        self.init_bmesh()

        if self.span < 0:
            if self.is_generated:
                edges = self.bmesh.edges[:]
                edges_count = len(edges)
                cuts, rest = divmod(self.points_count_original, edges_count)
                for e in edges:
                    if rest:
                        x = 1
                        rest -= 1
                    else:
                        x = 0
                    bmesh.ops.subdivide_edges(self.bmesh, edges=[e], cuts=cuts-1+x)
                self.bmesh.faces[0].loops.index_update()
            else:
                verts = self.bmesh.verts[:]
                dissolved = 0
                # for i in range(abs(self.span)):
                #     if len(verts) > 3:
                #         v = verts.pop()
                #         bmesh.ops.dissolve_verts(self.bmesh, verts=[v])
                #         dissolved += 1
                #     else:
                #         self.bmesh.faces.ensure_lookup_table()
                #         self.bmesh.faces[0].loops.index_update()
                #         verts = self.bmesh.faces[0].verts[:]
                # if dissolved:
                #     mask = even_elements_mask(len(self.bmesh.edges), len(self.bmesh.edges) - dissolved)
                    #
                    # bmesh.ops.subdivide_edges(self.bmesh,
                    #                           edges=numpy.compress(mask, self.bmesh.edges, axis=0),
                    #                           cuts=1, smooth=1.0)

        elif self.span != 0 and not self.is_generated:
            final_span = self.span

            self.bmesh.faces.ensure_lookup_table()
            self.bmesh.faces[0].loops.index_update()
            # bmesh.ops.subdivide_edges(self.bmesh,
            #
            #                           edges=[l.edge for l in self.bmesh.faces[0].loops[:final_span]],
            #                           cuts=1)
            self.bmesh.faces.ensure_lookup_table()
            self.bmesh.faces[0].loops.index_update()

        bmesh.ops.rotate(
            self.bmesh,
            verts=self.bmesh.verts,
            cent=(0.0, 0.0, 0.0),
            matrix=Matrix.Rotation(self.rotation, 3, 'Z'))

        bmesh.ops.rotate(
            self.bmesh_original,
            verts=self.bmesh_original.verts,
            cent=(0.0, 0.0, 0.0),
            matrix=Matrix.Rotation(self.rotation, 3, 'Z'))

        self.bmesh.faces.ensure_lookup_table()
        self.points_original = [v.co.xy for v in self.bmesh_original.verts]
        self.points = [l.vert.co.xy for l in self.bmesh.faces[0].loops]
        self.points_count = len(self.points)

    def apply_shift(self):
        self.points = self.points[self.shift % self.points_count:] + self.points[:self.shift % self.points_count]
        pco = self.points_count_original
        self.points_original = self.points_original[self.shift % pco:] + self.points_original[:self.shift % pco]

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



    @classmethod
    def __get_final_points_span(cls, points_count, span, min_points, max_points, target_points_count=0):
        if target_points_count:
            final_points_count = max(points_count - target_points_count, min_points)
        else:
            final_points_count = max(points_count + span, min_points)

        final_span = span
        if target_points_count:
            final_span += points_count - target_points_count
        if span < 0:
            final_span = min(abs(span), points_count - min_points)
            final_span *= -1

        if max_points:
            final_points_count = min(final_points_count, max_points)
            final_span = min(final_span, max_points - points_count)
        return final_points_count, final_span

    @classmethod
    def Circle(cls, points_count, span, shift, rotation, max_points=None):
        final_points_count, final_span = cls.__get_final_points_span(points_count, span, 3, max_points)
        original_points = circle_generator(final_points_count if span > 0 else points_count)
        return cls(circle_generator(final_points_count), original_points, final_span, shift, rotation)

    @classmethod
    def Rectangle(cls, points_count, ratio, span, shift, rotation, max_points=None):
        final_points_count, final_span = cls.__get_final_points_span(points_count, span, 4, max_points)
        original_points = list(rectangle_generator(final_points_count if span > 0 else points_count, ratio))
        return cls(rectangle_generator(final_points_count, ratio), original_points, final_span, shift, rotation)

    @classmethod
    def Object(cls, name, span, shift, rotation, max_points=None, target_points_count=None,
               points_distribution="SEQUENCE", points_distribution_smooth=False):
        #points_count, span = cls.__get_final_points_span(len(suzanne), span, 4, max_points, target_points_count)
        return cls(suzanne, suzanne, span, shift, rotation, is_generated=False, target_points_count=target_points_count,
                   points_distribution=points_distribution, points_distribution_smooth=points_distribution_smooth)


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


def get_parallel_edges(edges, verts, perpendicular=False):
    """
    Return parallel (or perpendicular) edges from given sorted edges and vertices
    :param edges: Sorted edges
    :param verts: Sorted vertices
    :param perpendicular: If True return perpendicular edges
    :return: tuple of loop edges, first smaller, second bigger
    """
    sides = ([], [])
    side_verts = []
    sides_faces = []
    len_a = 0
    len_b = 0

    parallels = []
    lost = []

    for vert in verts:
        for face in vert.link_faces:
            if face in sides_faces:
                continue
            sides_faces.append(face)
            for edge in face.edges:
                if edge not in parallels:
                    parallels.append(edge)
                    test = len([v for v in edge.verts if v not in verts])
                    if test == 2:
                        if not sides[0] or any((v for v in edge.verts if v in side_verts)):
                            sides[0].append(edge)
                            side_verts.extend(edge.verts[:])
                            len_a += edge.calc_length()
                        else:
                            lost.append(edge)
    processed = []
    while True:
        counter = 0
        for edge in lost:
            if edge not in processed and any((v for v in edge.verts if v in side_verts)):
                sides[0].append(edge)
                side_verts.extend(edge.verts[:])
                len_a += edge.calc_length()
                counter += 1
                processed.append(edge)
        if counter == 0:
            break

    for edge in lost:
        if edge not in processed:
            sides[1].append(edge)
            len_b += edge.calc_length()

    return sides if len_a <= len_b else (sides[1], sides[0])


def get_inner_faces(edges, verts, limit_edges):
    """
    Return inner faces from loop
    :param edges: Sorted edges
    :param verts: Sorted vertices
    :return: Inner loop-faces
    """
    def search_faces(faces, limit_edges, processed=None):
        if processed is None:
            processed = []
        result = []
        for face in faces:
            for edge in face.edges:
                if edge not in limit_edges:
                    for search_face in edge.link_faces:
                        if search_face not in processed and search_face not in result:
                            result.append(search_face)
        if result:
            processed.extend(result)
        else:
            return []

        return search_faces(result, limit_edges, processed)

    parallels = get_parallel_edges(edges, verts)
    inner_faces = []

    parallel_verts = []
    for e in parallels[1]:
        parallel_verts.extend(e.verts[:])

    for edge in edges:
        if edge in limit_edges:
            continue
        for face in edge.link_faces:
            if face not in inner_faces and not any((v for v in face.verts if v in parallel_verts)):
                inner_faces.append(face)

    if not parallels[0]:
        return inner_faces

    return inner_faces + search_faces([f for f in reduce(add,
                                                         [v.link_faces[:] for v in
                                                          reduce(add, [e.verts[:] for e in parallels[0]])])
                                       if f not in inner_faces], limit_edges, inner_faces)


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


def remove_shapes():
    global previews_shapes
    global shape
    previews_shapes = None
    shape = None

atexit.register(remove_shapes)

