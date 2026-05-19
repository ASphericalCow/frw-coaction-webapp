"""
Pure-Python SVG renderer for FRW graph coaction visualizations.
No Wolfram dependency.

Tube halos are computed via shapely (union of buffered edges), giving
a smooth outline that follows the graph shape at a fixed distance,
matching Mathematica's RegionDilation approach.
"""
import math
import networkx as nx
from shapely.geometry import Point, LineString
from shapely.ops import unary_union

# Canvas configuration
CANVAS_W = 390        # viewBox width in pixels  (260 * 1.5)
CANVAS_H = 260        # viewBox height in pixels
PADDING = 35          # padding inside canvas edges
VERT_R = 9            # vertex circle radius
TUBE_STEP = 14        # extra halo radius per edge level
EDGE_W = 2.5          # edge stroke width

# Multi-tube color palette (blue, green, amber, pink, purple, red)
TUBE_COLORS = [
    "rgba(59,130,246,0.85)",
    "rgba(16,185,129,0.85)",
    "rgba(245,158,11,0.85)",
    "rgba(236,72,153,0.85)",
    "rgba(139,92,246,0.85)",
    "rgba(239,68,68,0.85)",
]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def circle_layout_norm(vertices):
    """
    Normalized [0,1] circle layout producing a true circle on the CANVAS_W × CANVAS_H canvas.
    Vertices arranged clockwise starting at the top (-π/2).
    """
    n = len(vertices)
    if n == 0:
        return {}
    if n == 1:
        return {vertices[0]: (0.5, 0.5)}
    dw = CANVAS_W - 2 * PADDING
    dh = CANVAS_H - 2 * PADDING
    r_pix = min(dw, dh) * 0.35
    result = {}
    for i, v in enumerate(sorted(vertices)):
        angle = (2 * math.pi * i) / n - math.pi / 2
        result[v] = (0.5 + (r_pix / dw) * math.cos(angle),
                     0.5 + (r_pix / dh) * math.sin(angle))
    return result


def _path_order(vertices, edges_frozensets):
    """
    If the graph is a simple path (chain), return vertices in path order.
    Otherwise return None.
    A path has n-1 edges, all degrees ≤ 2, and is connected.
    """
    n = len(vertices)
    if n <= 1:
        return list(vertices)
    if len(edges_frozensets) != n - 1:
        return None

    from collections import defaultdict
    adj = defaultdict(set)
    for e in edges_frozensets:
        u, v = tuple(sorted(e))
        adj[u].add(v)
        adj[v].add(u)

    if any(len(adj[v]) > 2 for v in vertices):
        return None  # has a branch → not a chain

    # Find an endpoint (degree 1), or any vertex if n==1
    endpoints = [v for v in vertices if len(adj[v]) == 1]
    if not endpoints:
        return None  # cycle
    start = min(endpoints)

    # Walk the path
    path = [start]
    visited = {start}
    while True:
        curr = path[-1]
        nxt = [v for v in adj[curr] if v not in visited]
        if not nxt:
            break
        path.append(nxt[0])
        visited.add(nxt[0])

    if len(path) != n:
        return None  # disconnected
    return path


def horizontal_layout_norm(vertices, edges_frozensets):
    """
    Horizontal line layout for chain (path) graphs.
    Vertices are placed left-to-right in path order, evenly spaced at y = 0.5.
    """
    order = _path_order(vertices, edges_frozensets)
    if order is None:
        order = sorted(vertices)
    n = len(order)
    result = {}
    for i, v in enumerate(order):
        result[v] = ((i + 1) / (n + 1), 0.5)
    return result


def get_coords(vertices, positions_norm=None, edges_frozensets=None):
    """
    Returns dict[int -> (px, py)] in pixel coordinates.

    Layout priority:
      1. positions_norm if provided (caller-supplied [0,1] coords)
      2. Horizontal line layout if the graph is a simple path (chain)
      3. Circle layout otherwise
    """
    if positions_norm is None:
        if edges_frozensets is not None and _path_order(vertices, edges_frozensets) is not None:
            positions_norm = horizontal_layout_norm(vertices, edges_frozensets)
        else:
            positions_norm = circle_layout_norm(vertices)
    w = CANVAS_W - 2 * PADDING
    h = CANVAS_H - 2 * PADDING
    return {
        v: (PADDING + positions_norm[v][0] * w,
            PADDING + positions_norm[v][1] * h)
        for v in vertices
        if v in positions_norm
    }


# ---------------------------------------------------------------------------
# Tube halo geometry (shapely-based)
# ---------------------------------------------------------------------------

def _geom_to_svg_path(geom):
    """Convert a shapely Polygon or MultiPolygon exterior to an SVG path string."""
    if geom is None or geom.is_empty:
        return ""

    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    parts = []
    for poly in polys:
        coords = list(poly.exterior.coords)
        if not coords:
            continue
        d = f"M {coords[0][0]:.2f},{coords[0][1]:.2f}"
        for x, y in coords[1:]:
            d += f" L {x:.2f},{y:.2f}"
        d += " Z"
        # Include holes (rare for tube shapes but handle correctly)
        for ring in poly.interiors:
            rc = list(ring.coords)
            if rc:
                d += f" M {rc[0][0]:.2f},{rc[0][1]:.2f}"
                for x, y in rc[1:]:
                    d += f" L {x:.2f},{y:.2f}"
                d += " Z"
        parts.append(d)
    return " ".join(parts)


def _tube_halo_svg(tube, coords, r, stroke, sw=2):
    """
    Return SVG element string for one tube halo outline.
    Uses shapely to compute the union of buffered edges so the halo
    follows the graph shape at a fixed distance — matching Mathematica's
    RegionDilation approach.

    tube: {"verts": [int,...], "edges": [[u,v],...]}
    """
    verts = tube["verts"]
    edges = tube["edges"]

    # Build shapely geometry: buffer each edge (and each isolated vertex)
    shapes = []
    covered_verts = set()
    for edge in edges:
        u, v = edge
        pu, pv = coords.get(u), coords.get(v)
        if pu and pv:
            shapes.append(LineString([pu, pv]).buffer(r, cap_style=1, join_style=1, resolution=12))
            covered_verts.add(u)
            covered_verts.add(v)

    # Add circles for any vertices not already covered by an edge buffer
    for v in verts:
        if v not in covered_verts:
            p = coords.get(v)
            if p:
                shapes.append(Point(p).buffer(r, resolution=16))

    if not shapes:
        return ""

    merged = unary_union(shapes)
    d = _geom_to_svg_path(merged)
    if not d:
        return ""
    return f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" fill-rule="evenodd"/>'


# ---------------------------------------------------------------------------
# Edge decoration rendering
# ---------------------------------------------------------------------------

def _edge_svg(pu, pv, dec_type, vert_r=VERT_R, edge_w=EDGE_W, color="#334155"):
    """Return SVG string for one decorated edge, using the given stroke color."""
    dx = pv[0] - pu[0]
    dy = pv[1] - pu[1]
    L = math.sqrt(dx * dx + dy * dy) or 1.0
    ux, uy = dx / L, dy / L
    nx_, ny_ = -uy, ux  # perpendicular

    if dec_type == "pinched":
        off = 3.0
        return (
            f'<line x1="{pu[0] + nx_*off:.2f}" y1="{pu[1] + ny_*off:.2f}" '
            f'x2="{pv[0] + nx_*off:.2f}" y2="{pv[1] + ny_*off:.2f}" '
            f'stroke="{color}" stroke-width="{edge_w}"/>'
            f'<line x1="{pu[0] - nx_*off:.2f}" y1="{pu[1] - ny_*off:.2f}" '
            f'x2="{pv[0] - nx_*off:.2f}" y2="{pv[1] - ny_*off:.2f}" '
            f'stroke="{color}" stroke-width="{edge_w}"/>'
        )

    if dec_type == "broken":
        return (f'<line x1="{pu[0]:.2f}" y1="{pu[1]:.2f}" '
                f'x2="{pv[0]:.2f}" y2="{pv[1]:.2f}" '
                f'stroke="{color}" stroke-width="{edge_w}" stroke-dasharray="4 3"/>')

    if dec_type in ("oriented_fwd", "oriented_rev"):
        ax, ay = (pu[0], pu[1]) if dec_type == "oriented_fwd" else (pv[0], pv[1])
        bx, by = (pv[0], pv[1]) if dec_type == "oriented_fwd" else (pu[0], pu[1])
        ddx, ddy = bx - ax, by - ay
        ll = math.sqrt(ddx * ddx + ddy * ddy) or 1.0
        ux, uy = ddx / ll, ddy / ll
        pnx, pny = -uy, ux  # perpendicular
        # Line shortened at both ends to clear vertex circles
        x1 = ax + ux * vert_r
        y1 = ay + uy * vert_r
        x2 = bx - ux * vert_r
        y2 = by - uy * vert_r
        # Arrowhead tip at 60% along the edge
        mx = ax + ddx * 0.6
        my = ay + ddy * 0.6
        hsize = max(7, round(vert_r * 0.9))
        hx = mx - ux * hsize
        hy = my - uy * hsize
        pts = (f"{mx:.2f},{my:.2f} "
               f"{hx + pnx*hsize:.2f},{hy + pny*hsize:.2f} "
               f"{hx - pnx*hsize:.2f},{hy - pny*hsize:.2f}")
        return (f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="{edge_w}"/>'
                f'<polygon points="{pts}" fill="{color}"/>')

    # Default solid
    return (f'<line x1="{pu[0]:.2f}" y1="{pu[1]:.2f}" '
            f'x2="{pv[0]:.2f}" y2="{pv[1]:.2f}" '
            f'stroke="{color}" stroke-width="{edge_w}"/>')


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_period_svg(vertices, edges_raw, dec_list, tubes, tube_indices, coords):
    """
    Generate an SVG string visualizing one FRW period (cut tubing).

    vertices     : list[int]
    edges_raw    : list[[u, v]]  (sorted pairs)
    dec_list     : list[{"edge": [u,v], "type": str}]
    tubes        : list[{"verts": [int,...], "edges": [[u,v],...]}]
    tube_indices : list[int]  indices into `tubes` for the halos to draw
    coords       : dict[int -> (px, py)]  pixel coordinates
    """
    # Compute minimum edge length in pixels so tube radii stay below it.
    edge_lengths = [
        math.hypot(coords[u][0] - coords[v][0], coords[u][1] - coords[v][1])
        for u, v in edges_raw
        if u in coords and v in coords
    ]
    min_edge_px = min(edge_lengths) if edge_lengths else (CANVAS_W - 2 * PADDING)
    # Scale TUBE_STEP down so the largest tube halo radius < min_edge_px.
    max_tube_edges = max((len(tubes[ti]["edges"]) for ti in tube_indices), default=0)
    raw_max_r = VERT_R + (max_tube_edges + 1) * TUBE_STEP
    target_max_r = min_edge_px * 0.42          # halo sits within 42 % of shortest edge
    if raw_max_r > target_max_r and max_tube_edges >= 0:
        tube_step = max(3, (target_max_r - VERT_R) / (max_tube_edges + 1))
    else:
        tube_step = TUBE_STEP

    # Crop viewBox to graph content + max tube halo radius as margin.
    vcoords = [coords[v] for v in vertices if v in coords]
    margin = VERT_R + (max_tube_edges + 1) * tube_step + 4  # +4 for stroke
    if vcoords:
        vb_x1 = max(0, min(x for x, y in vcoords) - margin)
        vb_y1 = max(0, min(y for x, y in vcoords) - margin)
        vb_x2 = min(CANVAS_W, max(x for x, y in vcoords) + margin)
        vb_y2 = min(CANVAS_H, max(y for x, y in vcoords) + margin)
        vb_w, vb_h = vb_x2 - vb_x1, vb_y2 - vb_y1
    else:
        vb_x1, vb_y1, vb_w, vb_h = 0, 0, CANVAS_W, CANVAS_H

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb_x1:.2f} {vb_y1:.2f} {vb_w:.2f} {vb_h:.2f}" '
        f'width="{vb_w:.2f}" height="{vb_h:.2f}">',
        f'<rect x="{vb_x1:.2f}" y="{vb_y1:.2f}" width="{vb_w:.2f}" height="{vb_h:.2f}" fill="white"/>',
    ]

    # Build decoration lookup
    dec_map = {}
    for d in dec_list:
        dec_map[frozenset(d["edge"])] = d["type"]

    # Sort tube indices largest-first so bigger halos render behind smaller ones
    sorted_ti = sorted(
        tube_indices,
        key=lambda i: (len(tubes[i]["verts"]), len(tubes[i]["edges"])),
        reverse=True,
    )

    # Draw tube halos
    for idx, ti in enumerate(sorted_ti):
        tube = tubes[ti]
        n_e = len(tube["edges"])
        r = VERT_R + (n_e + 1) * tube_step
        stroke = TUBE_COLORS[ti % len(TUBE_COLORS)]
        parts.append(_tube_halo_svg(tube, coords, r, stroke))

    # Draw edges
    for edge in edges_raw:
        u, v = edge
        pu = coords.get(u)
        pv = coords.get(v)
        if not pu or not pv:
            continue
        dec_type = dec_map.get(frozenset(edge), "oriented_fwd")
        parts.append(_edge_svg(pu, pv, dec_type))

    # Draw vertices (circles + labels)
    font_size = max(8, round(VERT_R * 0.9))
    for v in vertices:
        p = coords.get(v)
        if not p:
            continue
        parts.append(
            f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="{VERT_R}" '
            f'fill="#1e293b" stroke="#64748b" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'fill="white" font-size="{font_size}" font-weight="bold" '
            f'font-family="system-ui,sans-serif">{v}</text>'
        )

    parts.append('</svg>')
    return '\n'.join(p for p in parts if p)


def render_letter_svg(vertices, edges_raw, region_verts, coords, dec_list=None):
    """
    SVG for a dP/discP symbol letter.

    The full decorated graph is drawn (with arrows, double lines, dashes) so
    that edge orientations are visible. Region vertices are highlighted orange;
    edges within the region are drawn in orange; all other edges are drawn in a
    faded style that still shows their decoration type.

    region_verts : collection of vertex ids that form the region.
    dec_list     : list of {"edge": [u,v], "type": str} — the decoration to render.
                   If None, all edges are drawn as plain lines.
    """
    region_set = frozenset(region_verts)
    region_edges = {frozenset(e) for e in edges_raw if frozenset(e).issubset(region_set)}

    dec_map = {}
    if dec_list:
        for d in dec_list:
            dec_map[frozenset(d["edge"])] = d["type"]

    # Crop viewBox tightly to graph content. Margin = vertex radius + arrowhead clearance.
    letter_margin = VERT_R + 12
    vcoords = [coords[v] for v in vertices if v in coords]
    if vcoords:
        xs = [x for x, y in vcoords]
        ys = [y for x, y in vcoords]
        vb_x1 = min(xs) - letter_margin
        vb_y1 = min(ys) - letter_margin
        vb_x2 = max(xs) + letter_margin
        vb_y2 = max(ys) + letter_margin
        vb_w = vb_x2 - vb_x1
        vb_h = vb_y2 - vb_y1
    else:
        vb_x1, vb_y1, vb_w, vb_h = 0, 0, CANVAS_W, CANVAS_H

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb_x1:.2f} {vb_y1:.2f} {vb_w:.2f} {vb_h:.2f}" '
        f'width="{vb_w:.2f}" height="{vb_h:.2f}">',
        f'<rect x="{vb_x1:.2f}" y="{vb_y1:.2f}" width="{vb_w:.2f}" height="{vb_h:.2f}" fill="white"/>',
    ]

    for edge in edges_raw:
        u, v = edge
        pu = coords.get(u)
        pv = coords.get(v)
        if not pu or not pv:
            continue
        dec_type = dec_map.get(frozenset(edge), "oriented_fwd")
        if frozenset(edge) in region_edges:
            # Region edge: full decoration in orange, slightly thicker
            parts.append(_edge_svg(pu, pv, dec_type, edge_w=EDGE_W + 1, color="#ea580c"))
        else:
            # Non-region edge: full decoration in faded slate blue
            parts.append(_edge_svg(pu, pv, dec_type, edge_w=EDGE_W, color="#94a3b8"))

    font_size = max(8, round(VERT_R * 0.9))
    for v in vertices:
        p = coords.get(v)
        if not p:
            continue
        if v in region_set:
            fill = "#ea580c"
            stroke = "#9a3412"
            text_fill = "white"
        else:
            fill = "#94a3b8"
            stroke = "#64748b"
            text_fill = "white"
        parts.append(
            f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="{VERT_R}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'fill="{text_fill}" font-size="{font_size}" font-weight="bold" '
            f'font-family="system-ui,sans-serif">{v}</text>'
        )

    parts.append('</svg>')
    return '\n'.join(p for p in parts if p)
