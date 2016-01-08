def find_loop(edges, vert=None):
    if vert is None:
        edge = edges[0]
        edges.remove(edge)
        success_0, is_boundary_0, verts_0, edges_0 = find_loop(edges, edge.verts[0])
        success_1, is_boundary_1, verts_1, edges_1 = find_loop(edges, edge.verts[1])
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
        success, is_boundary, verts_, edges_ = find_loop(edges, vert)
        if edge.is_boundary:
            is_boundary = True
        return success, is_boundary, [vert] + verts_, [edge] + edges_

    elif len(link_edges) > 1:
        edges.clear()
        return False, False, [], []

    return True, False, [], []


def prepare_loops(edges):
    edges = edges[:]
    loops = []

    while len(edges) > 0:
        success, is_boundary, loop_verts, loop_edges = find_loop(edges)
        if not success:
            return None
        if len(loop_verts) < 2:
            is_cyclic = False
        else:
            is_cyclic = any([v for v in loop_edges[0].verts if v in loop_edges[-1].verts])
        loops.append(((loop_verts, loop_edges), is_cyclic, is_boundary))

    return loops


def is_clockwise(forward, center, verts):
    clockwise = forward.dot((verts[0].co - center).cross(verts[1].co - center))
    if clockwise > 0:
        return True
    return False


def select_only(bm, geom, mode={"VERT"}):
    bm.select_mode = mode
    for ele in bm.verts[:] + bm.edges[:] + bm.faces[:]:
        ele.select_set(False)

    for ele in geom:
        if ele.is_valid:
            ele.select_set(True)