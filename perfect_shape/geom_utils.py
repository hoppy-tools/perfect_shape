from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_vector_3d, location_3d_to_region_2d
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_point_line
from mathutils.kdtree import KDTree


def matrix_decompose_4x4(matrix):
    loc, rot, sca = matrix.decompose()
    matrix_rot = rot.to_matrix().to_4x4()
    matrix_sca = Matrix()
    matrix_sca[0][0], matrix_sca[1][1], matrix_sca[2][2] = sca
    return Matrix.Translation(loc), matrix_rot, matrix_sca


def is_clockwise(forward, center, verts):
    return forward.dot((verts[0].co - center).cross(verts[1].co - center)) > 0


def is_backface(bm_element, eye_location, mtx=None, mtx_sr=None):
    if mtx is not None and mtx_sr is not None:
        return (mtx @ bm_element.co - eye_location).dot(mtx_sr @ bm_element.normal) >= 0.0
    return (bm_element.co - eye_location).dot(bm_element.normal) >= 0.0


def points_3d_to_region_2d(points, region, rv3d):
    return [i for i in (location_3d_to_region_2d(region, rv3d, p) for p in points) if all(i)]


def points_pairs_3d_to_region_2d(points_pairs, region, rv3d):
    return [i for i in ((location_3d_to_region_2d(region, rv3d, p[0]),
                         location_3d_to_region_2d(region, rv3d, p[1])) for p in points_pairs) if all(i)]


def region_2d_to_points_3d(pos, region, rv3d):
    vec = region_2d_to_vector_3d(region, rv3d, pos)
    return region_2d_to_location_3d(region, rv3d, pos, vec)


def intersect_point_section(pt, p1, p2):
    try:
        p, distance = intersect_point_line(pt, p1, p2)
    except:
        print(pt, p1, p2)
    if min(p1[0], p2[0]) <= p[0] <= max(p1[0], p2[0]) and min(p1[1], p2[1]) <= p[1] <= max(p[1], p2[1]):
        return p, distance
    return p1 if (p1 - p).length < (p2 - p).length else p2, distance


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

