"""
Core combinatorial coaction algorithm for FRW integrals.
Mirrors graphicalCosmoCoaction.nb.

Graph representation:
  vertices: list of ints
  edges:    list of frozensets of 2 ints

Decoration types per edge:
  "oriented_fwd"  u→v  (u < v)
  "oriented_rev"  v→u
  "pinched"
  "broken"
"""

from itertools import chain, combinations, product
import networkx as nx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def powerset(iterable):
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


def frozenedge(u, v):
    return frozenset({u, v})


# ---------------------------------------------------------------------------
# Tube enumeration
# ---------------------------------------------------------------------------

def all_tubes(vertices, edges):
    """
    Returns list of (tube_verts: frozenset[int], tube_edges: frozenset[frozenset]).
    Includes singleton vertex tubes and all connected edge-subsets.
    Ordered by (size, min_vertex), matching the .nb global tube order.
    """
    tubes = []
    # 1-vertex tubes
    for v in sorted(vertices):
        tubes.append((frozenset({v}), frozenset()))

    edge_list = sorted(edges, key=sorted)
    for r in range(1, len(edge_list) + 1):
        for subset in combinations(edge_list, r):
            touched = frozenset().union(*subset)
            sg = nx.Graph()
            sg.add_nodes_from(touched)
            for e in subset:
                u, v = sorted(e)
                sg.add_edge(u, v)
            if nx.is_connected(sg):
                tubes.append((touched, frozenset(subset)))

    tubes.sort(key=lambda t: (-len(t[0]), -len(t[1]), tuple(sorted(t[0]))))
    return tubes


def precompute_boundary(tubes, all_edges):
    """
    For each tube index, precompute boundary edges:
    edges with at least one endpoint inside the tube that are NOT internal to the tube.
    These are the "crossing" edges — one endpoint in, one out, or both in but not in tube's edge set.

    Per Mathematica tubeEdges[]: Complement[graph, tube_edges] filtered by touching tube verts.
    """
    all_edges_set = frozenset(all_edges)
    boundaries = []
    for tv, te in tubes:
        bd = frozenset(
            e for e in all_edges_set
            if e not in te and e & tv
        )
        boundaries.append(bd)
    return boundaries


# ---------------------------------------------------------------------------
# Decorated graphs
# ---------------------------------------------------------------------------

DECORATED_TYPES = ("oriented_fwd", "oriented_rev", "pinched", "broken")


def all_decorations(edges):
    """Yield all 4^|E| decorations as tuples of (frozenset-edge, type)."""
    edge_list = sorted(edges, key=sorted)
    for assignment in product(DECORATED_TYPES, repeat=len(edge_list)):
        yield tuple(zip(edge_list, assignment))


def adec_q(dec, vertices):
    """
    Check acyclicity: after contracting pinched edges, oriented edges form a DAG
    and no oriented edge becomes a self-loop.
    """
    parent = {v: v for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for edge, typ in dec:
        if typ == "pinched":
            u, v = sorted(edge)
            union(u, v)

    node_map = {v: find(v) for v in vertices}

    for edge, typ in dec:
        if typ in ("oriented_fwd", "oriented_rev"):
            u, v = sorted(edge)
            if node_map[u] == node_map[v]:
                return False

    dg = nx.DiGraph()
    dg.add_nodes_from(set(node_map.values()))
    for edge, typ in dec:
        u, v = sorted(edge)
        cu, cv = node_map[u], node_map[v]
        if typ == "oriented_fwd":
            dg.add_edge(cu, cv)
        elif typ == "oriented_rev":
            dg.add_edge(cv, cu)

    return nx.is_directed_acyclic_graph(dg)


# ---------------------------------------------------------------------------
# Tube–decoration compatibility
# ---------------------------------------------------------------------------

def adec_tube_compatible(dec_sets, tube_idx, tubes, boundaries):
    """
    Checks if a tube is compatible with a decoration.

    Rules (from Mathematica aDecTubeCompatibility):
      1. No broken edge is internal to the tube (te).
      2. No pinched edge crosses the tube boundary (bd) — i.e., a pinched edge
         must not have one endpoint inside and one outside the tube.
      3. No oriented boundary edge points its sink into the tube.

    dec_sets: precomputed dict with keys 'broken', 'pinched', 'oriented'
    tube_idx: index into tubes list
    """
    tv, te = tubes[tube_idx]
    bd = boundaries[tube_idx]

    broken_edges = dec_sets["broken"]
    pinched_edges = dec_sets["pinched"]
    oriented = dec_sets["oriented"]

    # Rule 1: no broken edge inside tube
    if te & broken_edges:
        return False

    # Rule 2: no pinched edge crosses the tube boundary
    if bd & pinched_edges:
        return False

    # Rule 3: no oriented boundary edge has its sink inside the tube
    for e, typ in oriented:
        if e in bd:
            u, v = sorted(e)
            sink = v if typ == "oriented_fwd" else u
            if sink in tv:
                return False

    return True


def dec_to_sets(dec):
    """Precompute frozen sets of edges by type for fast lookup."""
    broken = frozenset(e for e, t in dec if t == "broken")
    pinched = frozenset(e for e, t in dec if t == "pinched")
    oriented = [(e, t) for e, t in dec if t in ("oriented_fwd", "oriented_rev")]
    return {"broken": broken, "pinched": pinched, "oriented": oriented}


def compute_adec_tubes(dec_sets, tubes, boundaries):
    """Return frozenset of tube indices compatible with this decoration."""
    return frozenset(
        i for i in range(len(tubes))
        if adec_tube_compatible(dec_sets, i, tubes, boundaries)
    )


# ---------------------------------------------------------------------------
# Region list and intersection number
# ---------------------------------------------------------------------------

def region_list(dec, vertices):
    """Groups of vertices connected by pinched edges, plus singletons."""
    pinched_edges = [e for e, t in dec if t == "pinched"]
    if not pinched_edges:
        return [frozenset({v}) for v in vertices]

    ug = nx.Graph()
    ug.add_nodes_from(vertices)
    for e in pinched_edges:
        u, v = sorted(e)
        ug.add_edge(u, v)

    pinched_nodes = frozenset(n for e in pinched_edges for n in e)
    groups = [frozenset(c) for c in nx.connected_components(ug.subgraph(pinched_nodes))]
    for v in vertices:
        if v not in pinched_nodes:
            groups.append(frozenset({v}))
    return groups


def int_num_symbolic(dec, vertices):
    """
    Returns the α-factor part of 1/intNum(f,f) as a list of fraction dicts.

    The full intersection number is:
      intNum(f,f) = |ncct(f)| · Π_R (Σ_{v∈R} α_v) / (Π_{v∈R} α_v)
    so:
      1/intNum(f,f) = (1/|ncct(f)|) · Π_R (Π_{v∈R} α_v) / (Σ_{v∈R} α_v)

    This function returns only the α-factor part:
      Π_R (Π_{v∈R} α_v) / (Σ_{v∈R} α_v)
    as a list of {"num": [v1,...,vk], "den": [v1,...,vk]} for each
    multi-vertex pinched component R.  The 1/|ncct(f)| denominator is
    passed separately as "ncct_count" in the coefficient dict.
    Singleton components contribute 1 and are omitted.
    """
    groups = region_list(dec, vertices)
    factors = []
    for group in groups:
        n_pinched = sum(1 for e, t in dec if t == "pinched" and e <= group)
        if n_pinched > 0 and len(group) > 1:
            verts = sorted(group)
            factors.append({"num": verts, "den": verts})
    return factors


# ---------------------------------------------------------------------------
# Cut-tubing sign
# ---------------------------------------------------------------------------

def _global_tube_order(tubes):
    """Map tube_idx → sort position matching the display ordering:
    largest tubes first (-len), most edges first (-len_edges), then sorted vertices.
    """
    order = sorted(
        range(len(tubes)),
        key=lambda i: (-len(tubes[i][0]), -len(tubes[i][1]), tuple(sorted(tubes[i][0])))
    )
    return {tube_idx: pos for pos, tube_idx in enumerate(order)}


def _smallest_tube_for_vertex(v, cut_tubing, tubes):
    """Index (in tubes[]) of the smallest tube in cut_tubing that contains v."""
    containing = [(i, len(tubes[i][0])) for i in cut_tubing if v in tubes[i][0]]
    min_size = min(s for _, s in containing)
    return next(i for i, s in containing if s == min_size)


def angle_map(vertex, cut_tubing, tubes):
    """
    angleMap[v, cutTubing]: global tube index of the smallest tube in
    cut_tubing that contains vertex v.

    tubes : list of (frozenset(verts), frozenset(edges)) in global index order.
    cut_tubing : list of int (indices into tubes).
    """
    return _smallest_tube_for_vertex(vertex, cut_tubing, tubes)


def _permutation_sign(perm):
    """Sign of permutation given as perm[i] = target position of i-th element."""
    n = len(perm)
    seen = [False] * n
    sign = 1
    for i in range(n):
        if not seen[i]:
            j, cycle_len = i, 0
            while not seen[j]:
                seen[j] = True
                j = perm[j]
                cycle_len += 1
            if cycle_len % 2 == 0:
                sign *= -1
    return sign


def cut_tubing_sign(cut_tubing, dec, vertices, tubes):
    """
    Sign for a single cut tubing of a decorated graph (dec on vertices).

    Mirrors Wolfram periodSVGsViaP sign formula:
      cgSgn = Signature[angleMap_seq] / Signature[sortTubes[angleMap_seq]]
    where angleMap_seq[i] = index of smallest tube in cut_tubing containing
    the min vertex of region i (regions sorted by min vertex).

    The ratio equals the permutation sign of going from angleMap_seq to the
    globally-sorted tube order.
    """
    global_order = _global_tube_order(tubes)
    regions = region_list(dec, vertices)
    region_min = sorted(min(reg) for reg in regions)

    angle_map_seq = [_smallest_tube_for_vertex(v, cut_tubing, tubes) for v in region_min]
    sorted_seq = sorted(angle_map_seq, key=lambda i: global_order[i])

    pos_in_sorted = {v: k for k, v in enumerate(sorted_seq)}
    perm = [pos_in_sorted[v] for v in angle_map_seq]

    return _permutation_sign(perm)


# ---------------------------------------------------------------------------
# Pinch variants
# ---------------------------------------------------------------------------

def pinch_list(dec):
    """All variants of dec obtained by pinching any subset of oriented edges."""
    oriented_idx = [i for i, (e, t) in enumerate(dec) if t in ("oriented_fwd", "oriented_rev")]
    variants = set()
    for subset in powerset(oriented_idx):
        new_dec = list(dec)
        for i in subset:
            e, _ = new_dec[i]
            new_dec[i] = (e, "pinched")
        variants.add(tuple(sorted(new_dec, key=lambda x: (sorted(x[0]), x[1]))))
    return list(variants)


# ---------------------------------------------------------------------------
# Crossed tubes check
# ---------------------------------------------------------------------------

def tubes_cross(i, j, tubes, boundaries):
    """
    Two tubes cross iff a boundary edge of one is an internal edge of the other,
    and neither tube is contained in the other.

    Containment: singleton tb (te=∅) is contained in ta iff tb's vertex ∈ ta's vertices;
    non-singleton tb is contained in ta iff tb's edge-set ⊆ ta's edge-set.

    Mirrors Mathematica crossedQ / containedQ.
    """
    tv1, te1 = tubes[i]
    tv2, te2 = tubes[j]
    bd1 = boundaries[i]
    bd2 = boundaries[j]

    # Boundary-interior overlap: a boundary edge of one must be an internal edge of the other
    if not (bd1 & te2 or bd2 & te1):
        return False

    # Check containment: is tb contained in ta?
    def contained_q(ta_tv, ta_te, tb_tv, tb_te):
        if not tb_te:          # singleton vertex tube
            return tb_tv <= ta_tv
        return tb_te <= ta_te  # edge-set containment for non-singletons

    return not (contained_q(tv1, te1, tv2, te2) or contained_q(tv2, te2, tv1, te1))


def noncrossed_subsets(compatible_indices, n_regions, tubes, boundaries):
    """Return all size-n_regions subsets of compatible_indices with no crossing pairs."""
    result = []
    for subset in combinations(sorted(compatible_indices), n_regions):
        crossed = any(
            tubes_cross(subset[a], subset[b], tubes, boundaries)
            for a in range(len(subset))
            for b in range(a + 1, len(subset))
        )
        if not crossed:
            result.append(list(subset))
    return result


# ---------------------------------------------------------------------------
# Parse decoration input
# ---------------------------------------------------------------------------

def parse_dec_input(dec_input, edges):
    """
    Convert list of {"edge": [u,v], "type": ...} dicts to a normalized
    canonical decoration tuple suitable as a dict key.

    Edges not present in dec_input default to "oriented_fwd".
    """
    dec_dict = {}
    for item in dec_input:
        fe = frozenset(item["edge"])
        dec_dict[fe] = item["type"]

    edge_list = sorted(edges, key=sorted)
    result = []
    for fe in edge_list:
        t = dec_dict.get(fe, "oriented_fwd")
        result.append((fe, t))
    return tuple(sorted(result, key=lambda x: (sorted(x[0]), x[1])))


# ---------------------------------------------------------------------------
# Main coaction: ΔP(g, h)
# ---------------------------------------------------------------------------

def compute_dp(vertices, edges, g_dec_input, h_dec_input):
    """
    Compute ΔP(g,h) = Σ_f (1/intNum(f)) P(g,f) ⊗ P(f,h)

    where f ranges over acyclic pinch-variants of h.

    P(g,f) ≠ 0  iff  tubes(g) ⊆ tubes(f)
    P(f,h) ≠ 0  iff  tubes(f) ⊆ tubes(h)

    Left tensor entry  P(g,f): shows f's decoration with g's noncrossed cut tubes.
    Right tensor entry P(f,h): shows h's decoration with f's noncrossed cut tubes.

    Coefficient: 1/intNum(f) = Π_{pinched components R} (Π_{v∈R} α_v)/(Σ_{v∈R} α_v)
    """
    edges = [frozenset(e) for e in edges]
    vertices = list(vertices)

    g_dec = parse_dec_input(g_dec_input, edges)
    h_dec = parse_dec_input(h_dec_input, edges)

    if not adec_q(g_dec, vertices):
        raise ValueError("Contour decoration γ is not acyclic")
    if not adec_q(h_dec, vertices):
        raise ValueError("Form decoration φ is not acyclic")

    tubes = all_tubes(vertices, edges)
    boundaries = precompute_boundary(tubes, edges)

    # Build all acyclic decorated graphs and precompute their tube sets
    adec_set = set()
    adec_tube_sets = {}
    adec_ncct = {}

    for dec in all_decorations(edges):
        if adec_q(dec, vertices):
            adec_set.add(dec)
            ds = dec_to_sets(dec)
            adec_tube_sets[dec] = compute_adec_tubes(ds, tubes, boundaries)

    for dec in adec_set:
        n_reg = len(region_list(dec, vertices))
        compat = adec_tube_sets[dec]
        adec_ncct[dec] = noncrossed_subsets(compat, n_reg, tubes, boundaries)

    if g_dec not in adec_set:
        raise ValueError("Contour γ is not an acyclic decorated graph")
    if h_dec not in adec_set:
        raise ValueError("Form φ is not an acyclic decorated graph")

    g_tubes = adec_tube_sets[g_dec]
    g_ncct = adec_ncct[g_dec]
    h_tubes = adec_tube_sets[h_dec]

    # Signs for g's cut tubings (same for every term since g is fixed)
    g_signs = [cut_tubing_sign(ct, g_dec, vertices, tubes) for ct in g_ncct]

    # Pinch variants of h that are acyclic
    pinches = [p for p in pinch_list(list(h_dec)) if p in adec_set]

    terms = []
    for f_dec in pinches:
        f_tubes = adec_tube_sets[f_dec]

        # P(g,f) ≠ 0 iff g_tubes ⊆ f_tubes
        if not g_tubes <= f_tubes:
            continue

        # P(f,h) ≠ 0 iff f_tubes ⊆ h_tubes
        if not f_tubes <= h_tubes:
            continue

        f_ncct = adec_ncct[f_dec]
        if not f_ncct:
            continue

        coeff_factors = int_num_symbolic(list(f_dec), vertices)
        f_signs = [cut_tubing_sign(ct, f_dec, vertices, tubes) for ct in f_ncct]

        terms.append({
            "coefficient": {"factors": coeff_factors, "ncct_count": len(f_ncct)},
            "left_dec": dec_to_json(f_dec),
            "left_tube_sets": g_ncct,
            "left_signs": g_signs,
            "right_dec": dec_to_json(h_dec),
            "right_tube_sets": f_ncct,
            "right_signs": f_signs,
        })

    tubes_json = [
        {"verts": sorted(tv), "edges": [sorted(te) for te in tes]}
        for tv, tes in tubes
    ]

    return {
        "vertices": vertices,
        "edges": [sorted(e) for e in edges],
        "tubes": tubes_json,
        "g_dec": dec_to_json(g_dec),
        "h_dec": dec_to_json(h_dec),
        "h_ncct_count": len(adec_ncct[h_dec]),
        "adec_count": len(adec_set),
        "terms": terms,
    }


def compute_tubings(vertices, edges, dec_input):
    """
    Compute all cut tubings for a single acyclic decorated graph g.

    A cut tubing is a maximal (size = n_regions) noncrossing set of compatible tubes,
    as defined in Box 2.3 of the paper.

    Returns dict with vertices, edges, tubes, dec, cut_tubings, n_regions.
    """
    edges = [frozenset(e) for e in edges]
    vertices = list(vertices)

    dec = parse_dec_input(dec_input, edges)

    if not adec_q(dec, vertices):
        raise ValueError("Decoration is not an acyclic decorated graph")

    tubes = all_tubes(vertices, edges)
    boundaries = precompute_boundary(tubes, edges)

    ds = dec_to_sets(dec)
    compat = compute_adec_tubes(ds, tubes, boundaries)
    n_reg = len(region_list(dec, vertices))
    ncct = noncrossed_subsets(compat, n_reg, tubes, boundaries)
    signs = [cut_tubing_sign(ct, dec, vertices, tubes) for ct in ncct]

    tubes_json = [
        {"verts": sorted(tv), "edges": [sorted(te) for te in tes]}
        for tv, tes in tubes
    ]

    return {
        "vertices": vertices,
        "edges": [sorted(e) for e in edges],
        "tubes": tubes_json,
        "dec": dec_to_json(dec),
        "cut_tubings": ncct,
        "cut_tubing_signs": signs,
        "n_regions": n_reg,
        "n_compatible": len(compat),
        "compatible_tube_indices": sorted(compat),
    }


def compute_dp_phys(vertices, edges, g_dec_input):
    """
    Compute ΔP(g, φ_phys) = Σ_f C_{ff}^{-1} P(g,f) ⊗ P(f, φ_phys)

    f ranges over ALL acyclic decorated graphs (not pinch variants of one h).
    P(g,f) ≠ 0 iff tubes(g) ⊆ tubes(f).
    P(f, φ_phys) is represented as cut tubings of f on the bare (undirected) graph.
    """
    edges = [frozenset(e) for e in edges]
    vertices = list(vertices)

    g_dec = parse_dec_input(g_dec_input, edges)

    if not adec_q(g_dec, vertices):
        raise ValueError("Contour decoration γ is not acyclic")

    tubes = all_tubes(vertices, edges)
    boundaries = precompute_boundary(tubes, edges)

    adec_set = set()
    adec_tube_sets = {}
    adec_ncct = {}

    for dec in all_decorations(edges):
        if adec_q(dec, vertices):
            adec_set.add(dec)
            ds = dec_to_sets(dec)
            adec_tube_sets[dec] = compute_adec_tubes(ds, tubes, boundaries)

    for dec in adec_set:
        n_reg = len(region_list(dec, vertices))
        compat = adec_tube_sets[dec]
        adec_ncct[dec] = noncrossed_subsets(compat, n_reg, tubes, boundaries)

    if g_dec not in adec_set:
        raise ValueError("Contour γ is not an acyclic decorated graph")

    g_tubes = adec_tube_sets[g_dec]
    g_ncct = adec_ncct[g_dec]
    g_signs = [cut_tubing_sign(ct, g_dec, vertices, tubes) for ct in g_ncct]

    terms = []
    for f_dec in adec_set:
        f_tubes = adec_tube_sets[f_dec]

        # P(g,f) ≠ 0 iff g_tubes ⊆ f_tubes
        if not g_tubes <= f_tubes:
            continue

        f_ncct = adec_ncct[f_dec]
        if not f_ncct:
            continue

        coeff_factors = int_num_symbolic(list(f_dec), vertices)
        f_signs = [cut_tubing_sign(ct, f_dec, vertices, tubes) for ct in f_ncct]

        terms.append({
            "coefficient": {"factors": coeff_factors, "ncct_count": len(f_ncct)},
            "left_dec": dec_to_json(f_dec),
            "left_tube_sets": g_ncct,
            "left_signs": g_signs,
            "right_dec": dec_to_json(f_dec),
            "right_tube_sets": f_ncct,
            "right_signs": f_signs,
        })

    tubes_json = [
        {"verts": sorted(tv), "edges": [sorted(te) for te in tes]}
        for tv, tes in tubes
    ]

    return {
        "vertices": vertices,
        "edges": [sorted(e) for e in edges],
        "tubes": tubes_json,
        "g_dec": dec_to_json(g_dec),
        "adec_count": len(adec_set),
        "terms": terms,
    }


def dec_to_json(dec):
    return [{"edge": sorted(e), "type": t} for e, t in dec]


def cgh(g_cut_tubings, h_cut_tubings):
    """
    Cgh[g, h]: pairs of (g_tubing, h_tubing) where g_tubing ⊆ h_tubing.

    g_cut_tubings : list of list[int]  — cut tubings for gamma (tube indices)
    h_cut_tubings : list of list[int]  — cut tubings for phi   (tube indices)

    Returns list of (g_tubing, h_tubing) tuples (each tubing as a sorted list).
    """
    pairs = []
    for g_ct in g_cut_tubings:
        g_set = frozenset(g_ct)
        for h_ct in h_cut_tubings:
            if g_set <= frozenset(h_ct):
                pairs.append((sorted(g_ct), sorted(h_ct)))
    return pairs
