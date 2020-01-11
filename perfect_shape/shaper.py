from functools import lru_cache
from mathutils import Vector, Matrix
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
    def __init__(self, points, points_original, span, shift, rotation, is_generated=True,
                 target_points_count=0, points_distribution="SEQUENCE", points_distribution_smooth=False):
        self.span = span
        self.shift = shift
        self.rotation = rotation
        self.is_generated = is_generated

        self.points_distribution = points_distribution
        self.points_distribution_smooth = points_distribution_smooth

        self.bmesh = self.create_bmesh(points)
        self.bmesh_original = self.create_bmesh_original(points_original)
        self.target_points_count = target_points_count

        self.apply_span()
        self.apply_subdivide()


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

    def apply_span(self):
        if self.span < 0:
            if self.is_generated:
                edges = self.bmesh.edges[:]
                edges_count = len(edges)
                cuts, rest = divmod(len(self.get_points_original()), edges_count)
                for e in edges:
                    x, rest = (1, rest-1) if rest else (0, rest)
                    bmesh.ops.subdivide_edges(self.bmesh, edges=[e], cuts=cuts-1+x)
                self.bmesh.faces[0].loops.index_update()
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

        elif self.span > 0 and not self.is_generated:
            final_span = self.span

            self.bmesh.faces.ensure_lookup_table()
            self.bmesh.faces[0].loops.index_update()
            # bmesh.ops.subdivide_edges(self.bmesh,
            #
            #                           edges=[l.edge for l in self.bmesh.faces[0].loops[:final_span]],
            #                           cuts=1)
            self.bmesh.faces.ensure_lookup_table()
            self.bmesh.faces[0].loops.index_update()

        self.bmesh.faces.ensure_lookup_table()
        self.clear_cache()

    def apply_shift(self):
        self.points = self.points[self.shift % self.points_count:] + self.points[:self.shift % self.points_count]
        # pco = self.points_count_original
        # self.points_original = self.points_original[self.shift % pco:] + self.points_original[:self.shift % pco]

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
    def _get_final_points_span(points_count, span, min_points, max_points, target_points_count=0):
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

    def calc_best_shifts(self):
        symmetry_points_weight = get_symmetry_points_weight(self.get_points())
        return [i[0] for i in symmetry_points_weight]

    @classmethod
    def Circle(cls, points_count, span, shift, rotation, max_points=None):
        final_points_count, final_span = cls._get_final_points_span(points_count, span, 3, max_points)
        original_points = circle_generator(final_points_count if span > 0 else points_count)
        return cls(circle_generator(final_points_count), original_points, final_span, shift, rotation)

    @classmethod
    def Rectangle(cls, points_count, ratio, span, shift, rotation, max_points=None):
        final_points_count, final_span = cls._get_final_points_span(points_count, span, 4, max_points)
        original_points = list(rectangle_generator(final_points_count if span > 0 else points_count, ratio))
        return cls(rectangle_generator(final_points_count, ratio), original_points, final_span, shift, rotation)

    @classmethod
    def Object(cls, name, span, shift, rotation, max_points=None, target_points_count=None,
               points_distribution="SEQUENCE", points_distribution_smooth=False):
        points_count, span = cls._get_final_points_span(len(suzanne), span, 4, max_points, target_points_count)
        return cls(suzanne, suzanne, span, shift, rotation, is_generated=False, target_points_count=target_points_count,
                   points_distribution=points_distribution, points_distribution_smooth=points_distribution_smooth)


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
