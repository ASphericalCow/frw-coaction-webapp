"""
FRW Graphical Coaction — v2 backend.
Pure Python implementation: no Wolfram / Mathematica dependency.

Supported modes: dlog (default decoration)
Not supported: physical contour, physical form (require symbolic CAS)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import time
import os
from itertools import combinations

from coaction import (
    build_edges,
    Edge,
    compute_dp, compute_dp_phys, compute_tubings,
    all_decorations, adec_q,
    region_list,
    precompute_boundary,
    all_tubes,
    cgh,
    angle_map,
    cut_tubing_sign,
    _global_tube_order,
    dec_to_sets,
    compute_adec_tubes,
    noncrossed_subsets,
    int_num_symbolic,
    dec_to_json,
)
from render_svg import render_period_svg, render_letter_svg, get_coords


def _edge_json(e):
    """Return [u, v, k] for JSON / decoration input, from an Edge or a raw [u,v(,k)] list."""
    if isinstance(e, Edge):
        return e.json()
    u, v = sorted((e[0], e[1]))
    if len(e) >= 3 and e[2]:
        return [u, v, e[2]]
    return [u, v]


app = FastAPI(title="FRW Graphical Coaction v2")

# Serve built React frontend if dist/ exists next to this file.
_DIST = os.path.join(os.path.dirname(__file__), "dist")
_SERVE_FRONTEND = os.path.isdir(_DIST)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class EdgeDecoration(BaseModel):
    edge: List[int]
    type: str


class DecInput(BaseModel):
    vertices: List[int]
    edges: List[List[int]]
    dec: List[EdgeDecoration]
    h_dec: Optional[List[EdgeDecoration]] = None
    positions: Optional[Dict[int, List[float]]] = None


class CoactionInput(BaseModel):
    vertices: List[int]
    edges: List[List[int]]
    g_dec: List[EdgeDecoration]
    h_dec: List[EdgeDecoration]
    positions: Optional[Dict[int, List[float]]] = None


class GraphInput(BaseModel):
    vertices: List[int]
    edges: List[List[int]]
    positions: Optional[Dict[int, List[float]]] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_positions(positions_raw):
    """Convert {vertex: [x, y]} from request to {vertex: (x, y)} for get_coords."""
    if not positions_raw:
        return None
    return {int(v): (float(xy[0]), float(xy[1])) for v, xy in positions_raw.items()}


def _check_limits(vertices, edges):
    if len(vertices) == 0:
        raise HTTPException(status_code=400, detail="Need at least one vertex")
    if len(vertices) > 8:
        raise HTTPException(status_code=400, detail="Max 8 vertices")
    if len(edges) > 8:
        raise HTTPException(status_code=400, detail="Max 8 edges")


def _add_svgs(result, vertices, coords=None):
    """
    Augment coaction result with left_svgs / right_svgs for each term.
    left_svgs[i]  = SVG of left_dec graph + left_tube_sets[i] halos
    right_svgs[i] = SVG of right_dec graph + right_tube_sets[i] halos
    """
    tubes = result["tubes"]
    if coords is None:
        coords = get_coords(vertices, edges_frozensets=[frozenset(e[:2]) for e in result["edges"]])

    for term in result["terms"]:
        raw_left_signs  = term.get("left_signs",  [])
        raw_right_signs = term.get("right_signs", [])

        left_svgs, left_signs = [], []
        for i, tube_set in enumerate(term.get("left_tube_sets", [])):
            svg = render_period_svg(
                vertices, result["edges"], term["left_dec"], tubes, tube_set, coords
            )
            left_svgs.append(svg)
            left_signs.append(raw_left_signs[i] if i < len(raw_left_signs) else 1)

        right_svgs, right_signs = [], []
        for i, tube_set in enumerate(term.get("right_tube_sets", [])):
            svg = render_period_svg(
                vertices, result["edges"], term["right_dec"], tubes, tube_set, coords
            )
            right_svgs.append(svg)
            right_signs.append(raw_right_signs[i] if i < len(raw_right_signs) else 1)

        term["left_svgs"] = left_svgs
        term["left_signs"] = left_signs
        term["right_svgs"] = right_svgs
        term["right_signs"] = right_signs

    return result


def _dec_to_tuples(dec_list):
    """Convert JSON dec list to (frozenset, type) tuples for coaction functions."""
    return [(frozenset(d["edge"]), d["type"]) for d in dec_list]


def _dec_equal(dec_a, dec_b):
    """Order-independent comparison of two decoration lists."""
    def _key(d):
        return (frozenset(d["edge"]), d["type"])
    return frozenset(_key(d) for d in dec_a) == frozenset(_key(d) for d in dec_b)


def _new_regions(from_dec, to_dec, vertices):
    """
    Regions present in to_dec but not in from_dec.
    Used to find the two new regions that appear when going from a more-pinched
    decoration to a less-pinched one (W1MPL off-diagonal letter).
    """
    from_regs = set(region_list(_dec_to_tuples(from_dec), vertices))
    to_regs   = region_list(_dec_to_tuples(to_dec), vertices)
    return [r for r in to_regs if r not in from_regs]


# ── Letter coefficient helpers ────────────────────────────────────────────────

def _letter_for_region_latex(dec_list, reg_verts):
    """
    LaTeX string for kinematic letter T_R = Σ X_v + Σ ±Y_{i,j}.
    Mirrors Wolfram letterForRegionTex[dec, rVerts]:
      X_v for each v in R (always +, joined with +)
      boundary oriented/broken edges:
        oriented u→v with u in R, v outside:  +Y_{min,max}
        oriented u→v with v in R, u outside:  -Y_{min,max}
        broken with one endpoint in R:        +Y_{min,max} (both signs positive)
        pinched: 0
    """
    reg = frozenset(reg_verts)
    x_parts = [f"X_{{{v}}}" for v in sorted(reg)]
    y_parts = []
    for item in dec_list:
        e = item["edge"]
        u, v = e[0], e[1]            # u < v always
        kidx = e[2] if len(e) > 2 else 1
        typ  = item["type"]
        u_in, v_in = u in reg, v in reg
        if u_in == v_in or typ == "pinched":
            continue
        lo, hi = min(u, v), max(u, v)
        y = f"Y_{{{lo},{hi}}}" + (f"^{{({kidx})}}" if kidx > 1 else "")
        if typ == "broken":
            y_parts.append(f"+{y}")
        elif typ == "oriented_fwd":  # u→v
            y_parts.append(f"+{y}" if u_in else f"-{y}")
        elif typ == "oriented_rev":  # v→u
            y_parts.append(f"+{y}" if v_in else f"-{y}")
    return "+".join(x_parts) + "".join(y_parts)


def _alpha_sum_latex(verts):
    """LaTeX for α_{v1} + α_{v2} + ... (sorted by vertex id)."""
    return " + ".join(f"\\alpha_{{{v}}}" for v in sorted(verts))


def _diag_letter_coeffs(regions):
    """
    Diagonal letter coefficients: one LaTeX string per region.
    coeff_i = Σ_{v∈R_i} α_v  (mirrors Wolfram Total[α /@ regVerts])
    """
    result = []
    for reg in regions:
        verts = sorted(reg)
        if len(verts) == 1:
            result.append(f"\\alpha_{{{verts[0]}}}")
        else:
            result.append(_alpha_sum_latex(verts))
    return result


def _ratio_letter_coeff_dp(new_regs, h_ncct=1, f_ncct=1):
    """
    Off-diagonal (ratio) letter coefficient for dP:
      intNum(h,h) / intNum(f,f)

    After cancellation of common Πα factors between h's two unique regions
    and f's merged region:
      = (ncct_h / ncct_f) · Π_{R∈new_regs} f(R) / Σα_{R12}
    where f(R) = α_v for singleton R={v}, or (Σα_R) for multi-vertex R,
    and R12 = new_regs[0] ∪ new_regs[1].

    Mirrors Wolfram: Factor[intNum[h,h] / intNum[f,f]]
    """
    from math import gcd as _gcd
    R1 = frozenset(new_regs[0])
    R2 = frozenset(new_regs[1])
    R12 = R1 | R2

    def _factor(R):
        v = sorted(R)
        if len(v) == 1:
            return f"\\alpha_{{{v[0]}}}"
        return "\\left(" + _alpha_sum_latex(v) + "\\right)"

    num_parts = [_factor(R1), _factor(R2)]
    den_str = _alpha_sum_latex(sorted(R12))

    # Include ncct ratio
    g = _gcd(h_ncct, f_ncct)
    nn, nd = h_ncct // g, f_ncct // g
    if nn != 1:
        num_parts.insert(0, str(nn))
    if nd != 1:
        den_str = f"{nd} \\cdot \\left({den_str}\\right)"

    num_str = " \\cdot ".join(num_parts)
    return f"\\frac{{{num_str}}}{{{den_str}}}"


def _dp_letter_svgs(f_dec, h_dec, vertices, edges, coords, h_ncct=1, f_ncct=1):
    """
    Return (letter_type, letter_svgs, letter_coeffs, letter_latex) for one dP term.

    Mirrors Wolfram dpLetterInfo[f, h]:
      f == h  (diagonal):  type="diag",  one SVG/coeff/latex per region of h
                           coeff_i = Σ_{v∈R_i} α_v
                           latex_i = T_{R_i} kinematic letter
      W1MPL   (off-diag):  type="ratio", two SVGs for the two new regions in h vs f
                           coeff[0] = intNum(h,h)/intNum(f,f)
                           latex[0] = \\frac{T_{sink}}{T_{source}}
      else:                type="zero",  empty lists
    """
    h_regions = region_list(_dec_to_tuples(h_dec), vertices)

    if _dec_equal(f_dec, h_dec):
        svgs   = [render_letter_svg(vertices, edges, reg, coords, dec_list=h_dec)
                  for reg in h_regions]
        coeffs = _diag_letter_coeffs(h_regions)
        latex  = [_letter_for_region_latex(h_dec, reg) for reg in h_regions]
        return "diag", svgs, coeffs, latex

    f_regions = region_list(_dec_to_tuples(f_dec), vertices)
    if len(h_regions) - len(f_regions) == 1:
        new_regs = _new_regions(f_dec, h_dec, vertices)
        if len(new_regs) >= 2:
            svgs  = [render_letter_svg(vertices, edges, reg, coords, dec_list=h_dec)
                     for reg in new_regs]
            coeff = _ratio_letter_coeff_dp(new_regs[:2], h_ncct=h_ncct, f_ncct=f_ncct)
            num   = _letter_for_region_latex(h_dec, new_regs[0])
            den   = _letter_for_region_latex(h_dec, new_regs[1])
            latex = [f"\\frac{{{num}}}{{{den}}}"]
            return "ratio", svgs, [coeff], latex

    return "zero", [], [], []


def _discp_letter_svgs(g_dec, f_dec, vertices, edges, coords):
    """
    Return (letter_type, letter_svgs, letter_coeffs, letter_latex) for one discP term.

    Mirrors Wolfram discLetterInfo[g, f]:
      g == f  (diagonal):  type="diag",  one SVG/coeff/latex per region of g
                           coeff_i = Σ_{v∈R_i} α_v
                           latex_i = T_{R_i} kinematic letter
      W1MPL   (off-diag):  type="ratio", two SVGs for the two new regions in f vs g
                           coeff[0] = "1"
                           latex[0] = \\frac{T_{sink}}{T_{source}}
      else:                type="zero",  empty lists
    """
    g_regions = region_list(_dec_to_tuples(g_dec), vertices)

    if _dec_equal(g_dec, f_dec):
        svgs   = [render_letter_svg(vertices, edges, reg, coords, dec_list=g_dec)
                  for reg in g_regions]
        coeffs = _diag_letter_coeffs(g_regions)
        latex  = [_letter_for_region_latex(g_dec, reg) for reg in g_regions]
        return "diag", svgs, coeffs, latex

    f_regions = region_list(_dec_to_tuples(f_dec), vertices)
    if len(f_regions) - len(g_regions) == 1:
        new_regs = _new_regions(g_dec, f_dec, vertices)
        if len(new_regs) >= 2:
            svgs = [render_letter_svg(vertices, edges, reg, coords, dec_list=f_dec)
                    for reg in new_regs]
            num  = _letter_for_region_latex(f_dec, new_regs[0])
            den  = _letter_for_region_latex(f_dec, new_regs[1])
            latex = [f"\\frac{{{num}}}{{{den}}}"]
            return "ratio", svgs, ["1"], latex

    return "zero", [], [], []


# ── Period debug helpers ──────────────────────────────────────────────────────

def _tube_poly_lin(tube_idx, tubes_fs, boundaries):
    """
    Tube polynomial τ_t = Σ_{v∈t} (X_v + x_v) + Σ_{e∈boundary(t)} Y_e as a linear-combo dict.
    Keys: ('X', v), ('x', v), or ('Y', lo, hi)  →  integer coefficient.
    tubes_fs: list of (frozenset_verts, frozenset_edges) tuples.
    """
    tv, _ = tubes_fs[tube_idx]
    bd = boundaries[tube_idx]
    lin = {}
    for v in tv:
        lin[('X', v)] = lin.get(('X', v), 0) + 1
        lin[('x', v)] = lin.get(('x', v), 0) + 1
    for e in bd:
        lo, hi = sorted(e)
        k = getattr(e, 'k', 1)
        # v3: an excluded edge with BOTH endpoints inside the tube (a loop /
        # parallel edge) contributes 2Y — the cosmological-polytope facet doubling.
        mult = len(e & tv)
        key = ('Y', lo, hi, k)
        lin[key] = lin.get(key, 0) + mult
    return lin


def _lin_to_terms(lin):
    """
    Convert a lin-combo dict to a sorted list of {"var": "X"|"x"|"Y", "idx": [...], "coeff": int}.
    Ordered: for each vertex (X_v, x_v) in vertex order, then Y terms sorted by (lo, hi).
    Zero-coefficient entries are dropped.
    """
    terms = []
    for key, coeff in lin.items():
        if coeff == 0:
            continue
        if key[0] in ('X', 'x'):
            terms.append({"var": key[0], "idx": [key[1]], "coeff": coeff})
        else:
            terms.append({"var": "Y", "idx": [key[1], key[2]], "coeff": coeff,
                          "k": key[3] if len(key) > 3 else 1})
    # Sort: X/x before Y; within X/x group by (vertex, var) so X_v, x_v appear together
    def _sort_key(t):
        if t["var"] in ("X", "x"):
            return (0, t["idx"][0], t["var"], 0)
        return (1, t["idx"][0], t["idx"][1], t.get("k", 1))
    terms.sort(key=_sort_key)
    return terms


def _compute_cut_values(cut_tubing, tubes_fs, boundaries, g_regions=None):
    """
    Solve τ_t = 0 for each tube t (processed in ascending size order).
    Solves for x_{min(R)} where R is the gamma-region containing the first
    unresolved vertex of t.  cut_tubings that don't span all regions leave
    the corresponding x variables free (absent from the returned dict).

    g_regions : list of frozensets of vertices (regions of gamma).
                If None, every vertex is its own singleton region.
    Returns dict { region_min_vertex : lin_combo_dict }.
    """
    # Build vertex → region-min map
    vert_to_rmin = {}
    if g_regions:
        for R in g_regions:
            rmin = min(R)
            for v in R:
                vert_to_rmin[v] = rmin
    # Fallback: singletons for any vertex not covered
    for tv, _ in tubes_fs:
        for v in tv:
            if v not in vert_to_rmin:
                vert_to_rmin[v] = v

    sorted_ct = sorted(cut_tubing, key=lambda i: (len(tubes_fs[i][0]), min(tubes_fs[i][0])))
    computed = {}  # region_min → lin_combo_dict
    for tube_idx in sorted_ct:
        tv, _ = tubes_fs[tube_idx]
        tau = _tube_poly_lin(tube_idx, tubes_fs, boundaries)

        # Which region representative does this tube solve for?
        solve_for = None
        for v in sorted(tv):
            rmin = vert_to_rmin[v]
            if rmin not in computed:
                solve_for = rmin
                break
        if solve_for is None:
            continue

        # Start from -tau
        x_new = {}
        for k, c in tau.items():
            x_new[k] = x_new.get(k, 0) - c

        # Remove x_{solve_for} self-reference (moved to LHS)
        x_new.pop(('x', solve_for), None)

        # Substitute already-solved region representatives: pop the x_w term
        # from x_new and add coeff * computed[rmin_w] in its place.
        seen_regions = set()
        for w in sorted(tv):
            rmin_w = vert_to_rmin[w]
            if rmin_w in computed and rmin_w not in seen_regions:
                seen_regions.add(rmin_w)
                coeff = x_new.pop(('x', rmin_w), 0)
                if coeff != 0:
                    for k, c in computed[rmin_w].items():
                        x_new[k] = x_new.get(k, 0) + coeff * c

        computed[solve_for] = {k: c for k, c in x_new.items() if c != 0}
    return computed


def _twist_latex(vertices, computed):
    """
    Twist factor for one cut tubing.

    vFixed    = keys(computed)  — region-min vertices whose x value was solved
    vFixedBar = vertices \\ vFixed — x variables left free

    twist = ∏_{v ∈ vFixed}    (solved value of x_v)^{α_v}
          · ∏_{v ∈ vFixedBar}  x_v^{α_v}
    """
    parts = []
    for v in sorted(vertices):
        alpha = f"\\alpha_{{{v}}}"
        if v in computed:
            val = _lincombo_latex(computed[v])
            parts.append(f"\\left({val}\\right)^{{{alpha}}}")
        else:
            parts.append(f"x_{{{v}}}^{{{alpha}}}")
    return "\\,".join(parts) if parts else "1"


def _lincombo_latex(lin):
    """
    Format { ('X',v): coeff, ('Y',lo,hi): coeff } as a LaTeX string.
    """
    # Order: (X_v, x_v) pairs by vertex, then Y terms
    xy_terms = sorted(
        [(k, c) for k, c in lin.items() if k[0] in ('X', 'x')],
        key=lambda kc: (kc[0][1], kc[0][0])   # sort by vertex, then 'X' before 'x'
    )
    y_terms = sorted([(k, c) for k, c in lin.items() if k[0] == 'Y'], key=lambda kc: kc[0][1:])
    parts = []
    for (k, c) in xy_terms + y_terms:
        if c == 0:
            continue
        if k[0] == 'X':
            var = f"X_{{{k[1]}}}"
        elif k[0] == 'x':
            var = f"x_{{{k[1]}}}"
        else:
            var = f"Y_{{{k[1]},{k[2]}}}"
            if len(k) > 3 and k[3] > 1:   # v3: distinguish parallel edges
                var += f"^{{({k[3]})}}"
        if c == 1:
            parts.append(f"+{var}")
        elif c == -1:
            parts.append(f"-{var}")
        elif c > 0:
            parts.append(f"+{c}\\,{var}")
        else:
            parts.append(f"{c}\\,{var}")
    if not parts:
        return "0"
    s = "".join(parts)
    return s[1:] if s.startswith("+") else s


def _list_signature(seq):
    """(-1)^(number of inversions) treating elements as integers."""
    inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])
    return 1 if inv % 2 == 0 else -1


def _tube_poly_on_cut(tube_idx, tubes_fs, boundaries, x_vals):
    """
    τ_{tube_idx} with each x_v replaced by its cut value from x_vals.
    Returns a linear-combo dict with only X and Y terms remaining.
    """
    lin = _tube_poly_lin(tube_idx, tubes_fs, boundaries)
    result = {}
    for k, c in lin.items():
        if k[0] == "x" and k[1] in x_vals:
            for kk, cc in x_vals[k[1]].items():
                result[kk] = result.get(kk, 0) + c * cc
        else:
            result[k] = result.get(k, 0) + c
    return {k: v for k, v in result.items() if v != 0}


def _integration_region(vertices, computed):
    """
    Returns a list of LaTeX inequality strings defining the integration region.

    - Empty list means no contour (all x_i fixed).
    - For each v in vFixedBar (not solved): "x_{v} \\leq 0".
    - For each v in vFixed whose solved expression still contains a free x_w:
      "(solved_latex) \\leq 0".
    """
    free_verts = set(vertices) - set(computed.keys())
    if not free_verts:
        return []  # all x_i fixed — no integration contour

    constraints = []
    for v in sorted(free_verts):
        constraints.append(f"x_{{{v}}} \\leq 0")

    for v in sorted(computed.keys()):
        expr = computed[v]
        if any(k[0] == "x" and k[1] in free_verts for k in expr):
            val_latex = _lincombo_latex(expr)
            constraints.append(f"\\left({val_latex}\\right) \\leq 0")

    return constraints


def _period_integral_tex(g_dec_list, h_dec_list, vertices, edges_raw, tubes_fs, boundaries):
    """
    Build the full period integral LaTeX string for P(γ_g, φ_h).
    Returns None if h has no cut tubings (P=0).
    g_dec_list / h_dec_list: list of {"edge": ..., "type": ...} dicts.
    """
    g_dec_tuples = _dec_to_tuples(g_dec_list)
    h_dec_tuples = _dec_to_tuples(h_dec_list)
    try:
        g_cut_tubings = compute_tubings(vertices, edges_raw, g_dec_list)["cut_tubings"]
        h_cut_tubings = compute_tubings(vertices, edges_raw, h_dec_list)["cut_tubings"]
    except ValueError:
        return None
    if not h_cut_tubings:
        return None

    g_regions_fs = region_list(g_dec_tuples, vertices)
    h_regions_fs = region_list(h_dec_tuples, vertices)

    raw_pairs = cgh(g_cut_tubings, h_cut_tubings)
    cgh_data = []
    for g_ct, h_ct in raw_pairs:
        g_sign = cut_tubing_sign(g_ct, g_dec_tuples, vertices, tubes_fs)
        h_sign = cut_tubing_sign(h_ct, h_dec_tuples, vertices, tubes_fs)
        cg_set = frozenset(g_ct)
        ch_minus_cg = [t for t in h_ct if t not in cg_set]
        concat = list(g_ct) + ch_minus_cg
        form_sign = _list_signature(concat) * _list_signature(list(h_ct))
        total_sign = g_sign * h_sign * form_sign

        x_vals_cut = _compute_cut_values(g_ct, tubes_fs, boundaries, g_regions_fs)
        form_dlogs = [
            _lincombo_latex(_tube_poly_on_cut(t, tubes_fs, boundaries, x_vals_cut))
            for t in ch_minus_cg
        ]
        R2 = sorted([R for R in h_regions_fs if len(R) > 1], key=min)
        form_part2 = []
        for R in R2:
            min_r = min(R)
            x_min = _lincombo_latex(x_vals_cut[min_r]) if min_r in x_vals_cut else f"x_{{{min_r}}}"
            for v in sorted(R):
                if v == min_r:
                    continue
                x_v = _lincombo_latex(x_vals_cut[v]) if v in x_vals_cut else f"x_{{{v}}}"
                form_part2.append((x_v, x_min))
        cgh_data.append((total_sign, form_dlogs, form_part2))

    # twist + region from first g-tubing
    xv0 = _compute_cut_values(g_cut_tubings[0], tubes_fs, boundaries, g_regions_fs)
    twist = _twist_latex(vertices, xv0)
    region = _integration_region(vertices, xv0)

    # assemble LaTeX
    term_strs = []
    for total_sign, dlogs, part2 in cgh_data:
        sign_str = "+" if total_sign > 0 else "-"
        wedges = (
            [f"\\mathrm{{dlog}}\\!\\left({p}\\right)" for p in dlogs] +
            [f"\\mathrm{{dlog}}\\!\\left(\\frac{{{n}}}{{{d}}}\\right)" for n, d in part2]
        )
        form_inner = " \\wedge ".join(wedges) if wedges else "1"
        term_strs.append(f"{sign_str}{form_inner}")
    sum_tex = "".join(term_strs) if term_strs else "0"
    integrand = f"{twist} \\cdot \\left[{sum_tex}\\right]"
    if not region:
        # Fully localized: if all form terms are constant (no dlog wedges), extract
        # the numeric coefficient and place it in front of the twist factor.
        all_const = all(not dlogs and not part2 for _, dlogs, part2 in cgh_data)
        if all_const:
            coeff = sum(sign for sign, _, _ in cgh_data)
            if coeff == 0:
                return "0"
            elif coeff == 1:
                return twist
            elif coeff == -1:
                return f"-{twist}"
            else:
                return f"{coeff} \\cdot {twist}"
        return integrand
    gamma_def = "\\Delta_{\\mathfrak{g}} = \\left\\{" + ",\\,".join(region) + "\\right\\}"
    return f"\\underset{{\\scriptstyle {gamma_def}}}{{\\int_{{\\Delta_{{\\mathfrak{{g}}}}}} {integrand}}}"


def _tubes_and_boundaries(result, vertices, edges_raw):
    """Extract tubes_fs and boundaries from a compute_tubings/compute_dp result."""
    edges_fs = build_edges(edges_raw)
    tubes_fs = [
        (frozenset(t["verts"]), frozenset(build_edges(t["edges"])))
        for t in result["tubes"]
    ]
    boundaries = precompute_boundary(tubes_fs, edges_fs)
    return tubes_fs, boundaries


def _phi_form_latex(h_dec_list, vertices, edges_raw, tubes_fs, boundaries):
    """
    LaTeX for the form φ(h) associated with one acyclic minor h:

      φ(h) = Σ_{c: cut tubings of h} sign(c)
               ∧_{i∈c} dlog(t_i)
               ∧_{r∈R2} ∧_{v∈r\\min(r)} dlog(x_v / x_min(r))

    Returns the bare sum string (no integral, no twist).
    Returns None if h has no cut tubings.
    """
    h_dec_tuples = _dec_to_tuples(h_dec_list)
    try:
        h_cut_tubings = compute_tubings(vertices, edges_raw, h_dec_list)["cut_tubings"]
    except ValueError:
        return None
    if not h_cut_tubings:
        return None

    h_regions_fs = region_list(h_dec_tuples, vertices)
    R2 = sorted([R for R in h_regions_fs if len(R) > 1], key=min)
    gorder = _global_tube_order(tubes_fs)

    part2_wedges = []
    for R in R2:
        min_r = min(R)
        for v in sorted(R):
            if v == min_r:
                continue
            part2_wedges.append(
                f"\\mathrm{{dlog}}\\!\\left(\\frac{{x_{{{v}}}}}{{x_{{{min_r}}}}}\\right)"
            )

    term_strs = []
    for c in h_cut_tubings:
        sign = cut_tubing_sign(c, h_dec_tuples, vertices, tubes_fs)
        sign_str = "+" if sign > 0 else "-"
        c_sorted = sorted(c, key=lambda i: gorder.get(i, i))
        part1_wedges = [
            f"\\mathrm{{dlog}}\\!\\left({_lincombo_latex(_tube_poly_lin(i, tubes_fs, boundaries))}\\right)"
            for i in c_sorted
        ]
        wedges = part1_wedges + part2_wedges
        form_inner = " \\wedge ".join(wedges) if wedges else "1"
        term_strs.append(f"{sign_str}{form_inner}")

    return "".join(term_strs) if term_strs else "0"


def _period_pphys_integral_tex(h_dec_list, vertices, edges_raw, tubes_fs, boundaries):
    """
    LaTeX for P(γ_phys, φ_h):

      ∫_{ℝⁿ₊} ∏_v x_v^{α_v} · [ Σ_{c: φ-cut-tubings} sign(c) · form(c) ]

    sign(c) = cut_tubing_sign(c, h_dec, vertices, tubes_fs)
    form(c) = ∧_{i∈c, global order} dlog(τ_i)  ∧  ∧_{r∈R2, v∈r\\min(r)} dlog(x_v/x_{min(r)})

    No cg-cut substitution — all x_v are free (γ_phys imposes no cut conditions).
    """
    h_dec_tuples = _dec_to_tuples(h_dec_list)
    try:
        h_cut_tubings = compute_tubings(vertices, edges_raw, h_dec_list)["cut_tubings"]
    except ValueError:
        return None
    if not h_cut_tubings:
        return None

    h_regions_fs = region_list(h_dec_tuples, vertices)
    R2 = sorted([R for R in h_regions_fs if len(R) > 1], key=min)
    gorder = _global_tube_order(tubes_fs)

    # Twist: ∏_v x_v^{α_v} (all free)
    twist = _twist_latex(vertices, {})

    # Part 2 wedges are the same for all cut tubings (no substitution, x free)
    part2_wedges = []
    for R in R2:
        min_r = min(R)
        for v in sorted(R):
            if v == min_r:
                continue
            part2_wedges.append(
                f"\\mathrm{{dlog}}\\!\\left(\\frac{{x_{{{v}}}}}{{x_{{{min_r}}}}}\\right)"
            )

    term_strs = []
    for c in h_cut_tubings:
        sign = cut_tubing_sign(c, h_dec_tuples, vertices, tubes_fs)
        sign_str = "+" if sign > 0 else "-"
        # Sort c in global tube order before building dlog wedge
        c_sorted = sorted(c, key=lambda i: gorder.get(i, i))
        part1_wedges = [
            f"\\mathrm{{dlog}}\\!\\left({_lincombo_latex(_tube_poly_lin(i, tubes_fs, boundaries))}\\right)"
            for i in c_sorted
        ]
        wedges = part1_wedges + part2_wedges
        form_inner = " \\wedge ".join(wedges) if wedges else "1"
        term_strs.append(f"{sign_str}{form_inner}")

    sum_tex = "".join(term_strs) if term_strs else "0"
    n = len(vertices)
    return f"\\int_{{\\mathbb{{R}}^{{{n}}}_+}} {twist} \\cdot \\left[{sum_tex}\\right]"


def _period_gphys_integral_tex(f_dec_list, vertices, tubes_fs, boundaries, f_cut_tubings, f_signs):
    """
    LaTeX for P(γ_f, φ_phys):

      ∫_Γ [Σ_i sign_i · Res_{t_j} ∘ ... [twist · φ_phys]]

    Mirrors buildPgPhysIntegralTex in the frontend (App.jsx).
    The contour Γ is defined by f's first cut tubing; the twist ∏_v x_v^{α_v}
    is left unsubstituted — the Res operations implicitly impose the constraints.
    """
    if not f_cut_tubings:
        return None

    f_dec_tuples = _dec_to_tuples(f_dec_list)
    f_regions_fs = region_list(f_dec_tuples, vertices)

    # Contour from first cut tubing
    x_vals0 = _compute_cut_values(f_cut_tubings[0], tubes_fs, boundaries, f_regions_fs)
    region = _integration_region(vertices, x_vals0)

    # Twist: ∏_v x_v^{α_v} (unsubstituted — same as frontend)
    twist_tex = "\\,".join(f"x_{{{v}}}^{{\\alpha_{{{v}}}}}" for v in sorted(vertices))

    def res_chain_tex(cut_tubing):
        # Sort by global tube index ascending (t1 < ... < tn), write Res_{tn} ∘ ... ∘ Res_{t1}
        sorted_ct = sorted(cut_tubing, reverse=True)
        return " \\circ ".join(f"\\mathrm{{Res}}_{{t_{{{j+1}}}}}" for j in sorted_ct)

    inner_terms = []
    for i, (ct, sign) in enumerate(zip(f_cut_tubings, f_signs)):
        sign_str = "-" if sign < 0 else ("+" if i > 0 else "")
        res_tex = res_chain_tex(ct)
        inner_terms.append(
            f"{sign_str}{res_tex}\\!\\left[{twist_tex}\\,\\varphi_{{\\mathrm{{phys}}}}\\right]"
        )

    inner_tex = "".join(inner_terms) or "0"
    # _integration_region returns [] when all x_i are fixed (fully localised):
    # the residues alone determine the value — no integral remains.
    # A non-empty list means some x_i are free and must be integrated over.
    if not region:
        return f"\\left[{inner_tex}\\right]"
    gamma_def = "\\Delta_{\\mathfrak{g}} = \\left\\{" + ",\\,".join(region) + "\\right\\}"
    return f"\\underset{{\\scriptstyle {gamma_def}}}{{\\int_{{\\Delta_{{\\mathfrak{{g}}}}}} \\left[{inner_tex}\\right]}}"


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/period_pphys")
def period_pphys(inp: DecInput):
    """
    P(γ_phys, φ): graphical representation is the φ acyclic minor with no tube halos.
    Returns a single SVG of the φ-decorated graph.
    """
    _check_limits(inp.vertices, inp.edges)
    h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec] if inp.h_dec else []
    try:
        h_result = compute_tubings(inp.vertices, inp.edges, h_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    coords = get_coords(
        inp.vertices,
        positions_norm=_parse_positions(inp.positions),
        edges_frozensets=[frozenset(e[:2]) for e in inp.edges],
    )
    tubes_fs, boundaries = _tubes_and_boundaries(h_result, inp.vertices, inp.edges)
    svg = render_period_svg(inp.vertices, h_result["edges"], h_dec, h_result["tubes"], [], coords)
    tex = _period_pphys_integral_tex(h_dec, inp.vertices, inp.edges, tubes_fs, boundaries)
    return {"svg": svg, "latex": [tex] if tex else []}

@app.get("/health")
def health():
    return {"status": "ok", "wolfram": False}


@app.post("/tubings")
def tubings(inp: DecInput):
    _check_limits(inp.vertices, inp.edges)
    dec = [{"edge": d.edge, "type": d.type} for d in inp.dec]
    h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec] if inp.h_dec else None

    try:
        result = compute_tubings(inp.vertices, inp.edges, dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check P(γ,φ) = 0 when φ given: requires γ_tubes ⊆ φ_tubes.
    # Skip this check when h_dec is all "solid" (physical form mode —
    # φ_phys is a sum over all decorations, not a single acyclic minor).
    render_dec = h_dec if h_dec else dec
    h_dec_is_solid = h_dec and all(d["type"] == "solid" for d in h_dec)
    if h_dec and not h_dec_is_solid:
        try:
            h_result = compute_tubings(inp.vertices, inp.edges, h_dec)
            g_compat = frozenset(result.get("compatible_tube_indices", []))
            h_compat = frozenset(h_result.get("compatible_tube_indices", []))
            if not g_compat <= h_compat:
                result["period_svgs"] = []
                result["period_signs"] = []
                result["period_latex"] = []
                return result
        except ValueError:
            result["period_svgs"] = []
            result["period_signs"] = []
            result["period_latex"] = []
            return result

    coords = get_coords(inp.vertices, positions_norm=_parse_positions(inp.positions), edges_frozensets=[frozenset(e[:2]) for e in inp.edges])
    tubes = result["tubes"]

    result["period_svgs"] = [
        render_period_svg(inp.vertices, result["edges"], render_dec, tubes, ts, coords)
        for ts in result["cut_tubings"]
    ]
    result["period_signs"] = result.get("cut_tubing_signs", [1] * len(result["period_svgs"]))

    # Compute period integral LaTeX — single implementation in backend, shared by all callers
    period_latex_str = None
    try:
        tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, inp.edges)
        if h_dec and not h_dec_is_solid:
            period_latex_str = _period_integral_tex(
                dec, h_dec, inp.vertices, inp.edges, tubes_fs, boundaries
            )
        elif h_dec_is_solid:
            f_signs = result.get("cut_tubing_signs", [1] * len(result["cut_tubings"]))
            period_latex_str = _period_gphys_integral_tex(
                dec, inp.vertices, tubes_fs, boundaries,
                result["cut_tubings"], f_signs
            )
    except Exception:
        pass
    result["period_latex"] = [period_latex_str] if period_latex_str else []

    return result


@app.post("/coaction")
def coaction(inp: CoactionInput):
    _check_limits(inp.vertices, inp.edges)
    t0 = time.time()
    g_dec = [{"edge": d.edge, "type": d.type} for d in inp.g_dec]
    h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec]

    try:
        result = compute_dp(inp.vertices, inp.edges, g_dec, h_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    coords = get_coords(inp.vertices, positions_norm=_parse_positions(inp.positions), edges_frozensets=[frozenset(e[:2]) for e in inp.edges])
    result = _add_svgs(result, inp.vertices, coords=coords)

    # Add period integral LaTeX for click-to-show in each term
    tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, inp.edges)
    _tex_cache = {}
    def _cached_period_tex(gd, hd):
        key = (tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in gd)),
               tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in hd)))
        if key not in _tex_cache:
            _tex_cache[key] = _period_integral_tex(gd, hd, inp.vertices, inp.edges, tubes_fs, boundaries)
        return _tex_cache[key]

    _pphys_tex_cache = {}
    for term in result["terms"]:
        f_dec = term["left_dec"]
        ltex = _cached_period_tex(g_dec, f_dec)
        rtex = _cached_period_tex(f_dec, h_dec)
        term["left_latex"]  = [ltex] if ltex else []
        term["right_latex"] = [rtex] if rtex else []
        # Physical contour: left period is just the f acyclic minor (no tube halos)
        term["left_phys_svg"] = render_period_svg(
            inp.vertices, result["edges"], f_dec, result["tubes"], [], coords
        )
        fkey = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in f_dec))
        if fkey not in _pphys_tex_cache:
            _pphys_tex_cache[fkey] = _period_pphys_integral_tex(
                f_dec, inp.vertices, inp.edges, tubes_fs, boundaries
            )
        ptex = _pphys_tex_cache[fkey]
        term["left_phys_latex"] = [ptex] if ptex else []

    result["elapsed_ms"] = round((time.time() - t0) * 1000)
    return result


@app.post("/coaction_phys")
def coaction_phys(inp: CoactionInput):
    """
    ΔP(γ_g, φ_phys) = Σ_f C_{ff}^{-1} P(γ_g, φ_f) ⊗ P(γ_f, φ_phys)

    f ranges over all acyclic minors with P(γ_g, φ_f) ≠ 0.
    Left  P(γ_g, φ_f): signed cut tubings of g on f-decorated graph.
    Right P(γ_f, φ_phys): signed cut tubings of f on the bare (solid) graph.
    """
    _check_limits(inp.vertices, inp.edges)
    t0 = time.time()
    g_dec = [{"edge": d.edge, "type": d.type} for d in inp.g_dec]

    try:
        result = compute_dp_phys(inp.vertices, inp.edges, g_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    coords = get_coords(
        inp.vertices,
        positions_norm=_parse_positions(inp.positions),
        edges_frozensets=[frozenset(e[:2]) for e in inp.edges],
    )
    tubes = result["tubes"]
    edges_raw = result["edges"]

    # Bare decoration — solid edges, no arrows — represents φ_phys graphically
    bare_dec = [{"edge": _edge_json(e), "type": "solid"} for e in edges_raw]

    tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, edges_raw)

    # Per-tube SVGs for PgPhysLatex Res subscripts (plain oriented_fwd decoration)
    plain_dec = [{"edge": _edge_json(e), "type": "oriented_fwd"} for e in edges_raw]
    tube_svgs = [
        render_period_svg(inp.vertices, edges_raw, plain_dec, tubes, [i], coords)
        for i in range(len(tubes))
    ]

    _left_tex_cache   = {}  # f_key → P(g,f) LaTeX string
    _right_tex_cache  = {}  # f_key → P(γ_f, φ_phys) LaTeX string
    _region_lat_cache = {}  # f_key → right_region_latex list

    for term in result["terms"]:
        f_dec_list = term["left_dec"]
        f_key = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in f_dec_list))

        # Left: cut tubings of g on f-decorated graph — P(γ_g, φ_f)
        left_svgs = [
            render_period_svg(inp.vertices, edges_raw, f_dec_list, tubes, ts, coords)
            for ts in term["left_tube_sets"]
        ]
        term["left_svgs"] = left_svgs
        term["left_signs"] = term.get("left_signs", [1] * len(left_svgs))
        if f_key not in _left_tex_cache:
            _left_tex_cache[f_key] = _period_integral_tex(
                g_dec, f_dec_list, inp.vertices, edges_raw, tubes_fs, boundaries
            )
        ltex = _left_tex_cache[f_key]
        term["left_latex"] = [ltex] if ltex else []

        # Right: cut tubings of f on bare graph — P(γ_f, φ_phys)
        right_svgs = [
            render_period_svg(inp.vertices, edges_raw, bare_dec, tubes, ts, coords)
            for ts in term["right_tube_sets"]
        ]
        term["right_svgs"] = right_svgs
        term["right_signs"] = term.get("right_signs", [1] * len(right_svgs))
        if f_key not in _right_tex_cache:
            _right_tex_cache[f_key] = _period_gphys_integral_tex(
                f_dec_list, inp.vertices, tubes_fs, boundaries,
                term["right_tube_sets"], term["right_signs"]
            )
        rtex = _right_tex_cache[f_key]
        term["right_latex"] = [rtex] if rtex else []

        # Γ contour for PgPhysLatex — from f's first cut tubing
        if f_key not in _region_lat_cache:
            f_cut_tubings = term["right_tube_sets"]
            if f_cut_tubings:
                f_regions_fs = region_list(_dec_to_tuples(f_dec_list), inp.vertices)
                x_vals0 = _compute_cut_values(
                    f_cut_tubings[0], tubes_fs, boundaries, f_regions_fs
                )
                _region_lat_cache[f_key] = _integration_region(inp.vertices, x_vals0)
            else:
                _region_lat_cache[f_key] = []
        term["right_region_latex"] = _region_lat_cache[f_key]

    result["tube_svgs"] = tube_svgs
    result["elapsed_ms"] = round((time.time() - t0) * 1000)
    return result


@app.post("/coaction_phys_phys")
def coaction_phys_phys(inp: GraphInput):
    """
    ΔP(γ_phys, φ_phys) = Σ_f C_{ff}^{-1} P(γ_phys, φ_f) ⊗ P(γ_f, φ_phys)

    f ranges over ALL acyclic minors.
    Left  P(γ_phys, φ_f): single SVG of f-decorated graph (no tube halos) + P(phys,f) latex.
    Right P(γ_f, φ_phys): signed cut tubings of f on bare graph + right_region_latex for PgPhysLatex.
    """
    _check_limits(inp.vertices, inp.edges)
    t0 = time.time()

    edges_fs = build_edges(inp.edges)
    vertices = list(inp.vertices)
    edges_json = [e.json() for e in edges_fs]

    coords = get_coords(
        inp.vertices,
        positions_norm=_parse_positions(inp.positions),
        edges_frozensets=edges_fs,
    )

    tubes_list = all_tubes(vertices, edges_fs)
    boundaries  = precompute_boundary(tubes_list, edges_fs)

    tubes_json = [
        {"verts": sorted(tv), "edges": [sorted(te) for te in tes]}
        for tv, tes in tubes_list
    ]
    # tubes_fs as list of (frozenset, frozenset) for _compute_cut_values etc.
    tubes_fs = [(frozenset(t["verts"]), frozenset(build_edges(t["edges"])))
                for t in tubes_json]

    # Per-tube SVGs for PgPhysLatex Res subscripts
    plain_dec = [{"edge": _edge_json(e), "type": "oriented_fwd"} for e in edges_fs]
    tube_svgs = [
        render_period_svg(vertices, edges_json, plain_dec, tubes_json, [i], coords)
        for i in range(len(tubes_json))
    ]

    bare_dec = [{"edge": _edge_json(e), "type": "solid"} for e in edges_fs]

    # Enumerate all acyclic minors
    adec_tube_map = {}
    adec_ncct_map = {}
    for dec in all_decorations(edges_fs):
        if adec_q(dec, vertices):
            ds = dec_to_sets(dec)
            compat = compute_adec_tubes(ds, tubes_list, boundaries)
            adec_tube_map[dec] = compat
    for dec, compat in adec_tube_map.items():
        n_reg = len(region_list(dec, vertices))
        adec_ncct_map[dec] = noncrossed_subsets(compat, n_reg, tubes_list, boundaries)

    _region_lat_cache = {}

    terms = []
    for f_dec_raw, f_ncct in adec_ncct_map.items():
        if not f_ncct:
            continue

        f_dec_list = dec_to_json(f_dec_raw)
        f_key = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in f_dec_list))
        f_signs = [cut_tubing_sign(ct, f_dec_raw, vertices, tubes_list) for ct in f_ncct]
        coeff_factors = int_num_symbolic(list(f_dec_raw), vertices)

        # Left: P(γ_phys, φ_f) — bare f-decorated graph, no tube halos
        left_svg = render_period_svg(vertices, edges_json, f_dec_list, tubes_json, [], coords)
        left_tex = _period_pphys_integral_tex(f_dec_list, vertices, edges_json, tubes_fs, boundaries)

        # Right: P(γ_f, φ_phys) — cut tubings of f on bare graph
        right_svgs = [
            render_period_svg(vertices, edges_json, bare_dec, tubes_json, ts, coords)
            for ts in f_ncct
        ]

        # Γ contour for PgPhysLatex
        if f_key not in _region_lat_cache:
            f_regions_fs = region_list(list(f_dec_raw), vertices)
            x_vals0 = _compute_cut_values(f_ncct[0], tubes_fs, boundaries, f_regions_fs)
            _region_lat_cache[f_key] = _integration_region(vertices, x_vals0)

        right_tex = _period_gphys_integral_tex(
            f_dec_list, vertices, tubes_fs, boundaries, f_ncct, f_signs
        )
        terms.append({
            "coefficient":        {"factors": coeff_factors, "ncct_count": len(f_ncct)},
            "left_dec":           f_dec_list,
            "left_svgs":          [left_svg],
            "left_signs":         [1],
            "left_latex":         [left_tex] if left_tex else [],
            "right_dec":          f_dec_list,
            "right_svgs":         right_svgs,
            "right_signs":        f_signs,
            "right_tube_sets":    f_ncct,
            "right_latex":        [right_tex] if right_tex else [],
            "right_region_latex": _region_lat_cache[f_key],
        })

    return {
        "vertices":    vertices,
        "edges":       edges_json,
        "tubes":       tubes_json,
        "tube_svgs":   tube_svgs,
        "adec_count":  len(adec_tube_map),
        "terms":       terms,
        "elapsed_ms":  round((time.time() - t0) * 1000),
    }


@app.post("/differential")
def differential(inp: CoactionInput):
    """
    dP(γ, φ) = Σ_f  letter(f, φ)  ·  P(γ, f)

    Two letter cases (mirroring Wolfram dpLetterInfo[f, h]):
      Diagonal  f == φ  : one graphical letter per region of φ
      Off-diag  nReg(φ) - nReg(f) == 1 (W1MPL): ratio letter with 2 SVGs
                          for the two new regions that appear in φ but not f
    """
    _check_limits(inp.vertices, inp.edges)
    g_dec = [{"edge": d.edge, "type": d.type} for d in inp.g_dec]
    h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec]

    try:
        result = compute_dp(inp.vertices, inp.edges, g_dec, h_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    vertices = result["vertices"]
    edges    = result["edges"]
    tubes    = result["tubes"]
    coords   = get_coords(inp.vertices, positions_norm=_parse_positions(inp.positions), edges_frozensets=[frozenset(e[:2]) for e in inp.edges])

    h_ncct_count = result.get("h_ncct_count", 1)

    dp_terms = []
    for term in result["terms"]:
        f_dec_list = term["left_dec"]
        f_ncct_count = len(term["right_tube_sets"])
        letter_type, letter_svgs, letter_coeffs, letter_latex = _dp_letter_svgs(
            f_dec_list, result["h_dec"], vertices, edges, coords,
            h_ncct=h_ncct_count, f_ncct=f_ncct_count,
        )
        if letter_type == "zero":
            continue

        left_svgs = [
            render_period_svg(vertices, edges, f_dec_list, tubes, ts, coords)
            for ts in term["left_tube_sets"]
        ]
        dp_terms.append({
            "f_dec":          f_dec_list,
            "coefficient":    {"factors": []},
            "left_svgs":      left_svgs,
            "left_signs":     term.get("left_signs", [1] * len(left_svgs)),
            "left_tube_sets": term["left_tube_sets"],
            "left_latex":     [],  # filled below
            "letter_type":    letter_type,
            "letter_svgs":    letter_svgs,
            "letter_coeffs":  letter_coeffs,
            "letter_latex":   letter_latex,
        })

    # Add period integral LaTeX + physical-contour SVG (f acyclic minor, no tube halos)
    tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, inp.edges)
    _tex_cache = {}
    _phys_svg_cache = {}
    _pphys_tex_cache = {}
    for term in dp_terms:
        key = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in term["f_dec"]))
        if key not in _tex_cache:
            _tex_cache[key] = _period_integral_tex(g_dec, term["f_dec"], inp.vertices, inp.edges, tubes_fs, boundaries)
        term["left_latex"] = [_tex_cache[key]] if _tex_cache[key] else []
        if key not in _phys_svg_cache:
            _phys_svg_cache[key] = render_period_svg(vertices, edges, term["f_dec"], tubes, [], coords)
        term["left_phys_svg"] = _phys_svg_cache[key]
        if key not in _pphys_tex_cache:
            _pphys_tex_cache[key] = _period_pphys_integral_tex(
                term["f_dec"], inp.vertices, inp.edges, tubes_fs, boundaries
            )
        ptex = _pphys_tex_cache[key]
        term["left_phys_latex"] = [ptex] if ptex else []

    return {"vertices": vertices, "edges": edges, "tubes": tubes, "terms": dp_terms}


@app.post("/discp_phys")
def discp_phys(inp: CoactionInput):
    """
    discP(γ_g, φ_phys) = Σ_f C_{ff}^{-1} · Weight1Part[P(γ_g, φ_f)] · P(γ_f, φ_phys)

    f ranges over all acyclic minors where the Disc-log letter is non-zero (W1MPL condition).
    Weight1Part[P(g,f)] = _discp_letter_svgs(g, f).
    P(γ_f, φ_phys): signed cut tubings of f on the bare (solid) graph.
    Coefficient C_{ff}^{-1} = 1/intNum[f,f] from the coaction.
    """
    _check_limits(inp.vertices, inp.edges)
    t0 = time.time()
    g_dec = [{"edge": d.edge, "type": d.type} for d in inp.g_dec]

    try:
        result = compute_dp_phys(inp.vertices, inp.edges, g_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    vertices = result["vertices"]
    edges_raw = result["edges"]
    tubes = result["tubes"]

    coords = get_coords(
        inp.vertices,
        positions_norm=_parse_positions(inp.positions),
        edges_frozensets=[frozenset(e[:2]) for e in inp.edges],
    )

    bare_dec = [{"edge": _edge_json(e), "type": "solid"} for e in edges_raw]

    tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, edges_raw)

    # Per-tube SVGs for PgPhysLatex Res subscripts
    plain_dec = [{"edge": _edge_json(e), "type": "oriented_fwd"} for e in edges_raw]
    tube_svgs = [
        render_period_svg(inp.vertices, edges_raw, plain_dec, tubes, [i], coords)
        for i in range(len(tubes))
    ]

    _region_lat_cache = {}  # f_key → right_region_latex
    _right_tex_cache  = {}  # f_key → P(γ_f, φ_phys) LaTeX string

    discp_terms = []
    for term in result["terms"]:
        f_dec_list = term["left_dec"]
        letter_type, letter_svgs, letter_coeffs, letter_latex = _discp_letter_svgs(
            result["g_dec"], f_dec_list, vertices, edges_raw, coords
        )
        if letter_type == "zero":
            continue

        f_key = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in f_dec_list))

        # P(γ_f, φ_phys): cut tubings of f on the bare graph
        right_svgs = [
            render_period_svg(inp.vertices, edges_raw, bare_dec, tubes, ts, coords)
            for ts in term["right_tube_sets"]
        ]
        right_signs = term.get("right_signs", [1] * len(right_svgs))

        # Γ contour for PgPhysLatex — from f's first cut tubing
        if f_key not in _region_lat_cache:
            f_cut_tubings = term["right_tube_sets"]
            if f_cut_tubings:
                f_regions_fs = region_list(_dec_to_tuples(f_dec_list), inp.vertices)
                x_vals0 = _compute_cut_values(
                    f_cut_tubings[0], tubes_fs, boundaries, f_regions_fs
                )
                _region_lat_cache[f_key] = _integration_region(inp.vertices, x_vals0)
            else:
                _region_lat_cache[f_key] = []

        if f_key not in _right_tex_cache:
            _right_tex_cache[f_key] = _period_gphys_integral_tex(
                f_dec_list, inp.vertices, tubes_fs, boundaries,
                term["right_tube_sets"], right_signs
            )
        rtex = _right_tex_cache[f_key]

        discp_terms.append({
            "f_dec":               f_dec_list,
            "coefficient":         term["coefficient"],
            "right_svgs":          right_svgs,
            "right_signs":         right_signs,
            "right_tube_sets":     term["right_tube_sets"],
            "right_latex":         [rtex] if rtex else [],
            "right_region_latex":  _region_lat_cache[f_key],
            "letter_type":         letter_type,
            "letter_svgs":         letter_svgs,
            "letter_coeffs":       letter_coeffs,
            "letter_latex":        letter_latex,
        })

    return {
        "vertices": vertices,
        "edges": edges_raw,
        "tubes": tubes,
        "tube_svgs": tube_svgs,
        "terms": discp_terms,
        "elapsed_ms": round((time.time() - t0) * 1000),
    }


@app.post("/discontinuity")
def discontinuity(inp: CoactionInput):
    """
    discP(γ, φ) = Σ_f  Disc·log·letter(γ, f)  ·  P(f, φ)

    Letter selection: nRegions(f) - nRegions(γ) == 1
    Letter edges = edges pinched in γ but oriented in f.
    """
    _check_limits(inp.vertices, inp.edges)
    g_dec = [{"edge": d.edge, "type": d.type} for d in inp.g_dec]
    h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec]

    try:
        result = compute_dp(inp.vertices, inp.edges, g_dec, h_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    vertices = result["vertices"]
    edges    = result["edges"]
    tubes    = result["tubes"]
    coords   = get_coords(inp.vertices, positions_norm=_parse_positions(inp.positions), edges_frozensets=[frozenset(e[:2]) for e in inp.edges])

    discp_terms = []
    for term in result["terms"]:
        f_dec_list = term["left_dec"]
        letter_type, letter_svgs, letter_coeffs, letter_latex = _discp_letter_svgs(
            result["g_dec"], f_dec_list, vertices, edges, coords
        )
        if letter_type == "zero":
            continue

        right_svgs = [
            render_period_svg(vertices, edges, term["right_dec"], tubes, ts, coords)
            for ts in term["right_tube_sets"]
        ]
        discp_terms.append({
            "f_dec":           f_dec_list,
            "coefficient":     {"factors": []},
            "right_svgs":      right_svgs,
            "right_signs":     term.get("right_signs", [1] * len(right_svgs)),
            "right_tube_sets": term["right_tube_sets"],
            "right_latex":     [],  # filled below
            "letter_type":     letter_type,
            "letter_svgs":     letter_svgs,
            "letter_coeffs":   letter_coeffs,
            "letter_latex":    letter_latex,
        })

    # Add period integral LaTeX
    tubes_fs, boundaries = _tubes_and_boundaries(result, inp.vertices, inp.edges)
    _tex_cache = {}
    for term in discp_terms:
        key = tuple(sorted((tuple(sorted(d["edge"])), d["type"]) for d in term["f_dec"]))
        if key not in _tex_cache:
            _tex_cache[key] = _period_integral_tex(term["f_dec"], h_dec, inp.vertices, inp.edges, tubes_fs, boundaries)
        rtex = _tex_cache[key]
        term["right_latex"] = [rtex] if rtex else []

    return {"vertices": vertices, "edges": edges, "tubes": tubes, "terms": discp_terms}


@app.post("/phi_phys_form")
def phi_phys_form(inp: GraphInput):
    """
    φ_phys decomposition into the basis of acyclic-minor forms.

    φ_phys = Σ_{f: acyclic, no pinched edges} (-1)^(#broken edges) φ_f

    Each zonotope is a set of acyclic minors sharing the same broken-edge subset.
    Returns:
      graph_svg  : bare undirected graph SVG (left-hand side)
      terms      : list of {sign, dec, svg, n_broken, broken_edges}
      vertices, edges
    """
    _check_limits(inp.vertices, inp.edges)
    edges_fs = build_edges(inp.edges)
    coords = get_coords(
        inp.vertices,
        positions_norm=_parse_positions(inp.positions),
        edges_frozensets=edges_fs,
    )

    # Compute tube info for SVG rendering (uses oriented_fwd as neutral decoration)
    plain_dec = [{"edge": _edge_json(e), "type": "oriented_fwd"} for e in inp.edges]
    try:
        base_result = compute_tubings(inp.vertices, inp.edges, plain_dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tubes = base_result["tubes"]
    edges_raw = base_result["edges"]

    # Bare graph SVG: plain undirected solid edges, no tube halos
    bare_dec = [{"edge": _edge_json(e), "type": "solid"} for e in inp.edges]
    graph_svg = render_period_svg(inp.vertices, edges_raw, bare_dec, tubes, [], coords)

    tubes_fs, boundaries = _tubes_and_boundaries(base_result, inp.vertices, edges_raw)

    # Enumerate all acyclic minors with no pinched edges (= zonotope vertices)
    terms = []
    for dec in all_decorations(edges_fs):
        if not adec_q(dec, inp.vertices):
            continue
        if any(t == "pinched" for _, t in dec):
            continue
        n_broken = sum(1 for _, t in dec if t == "broken")
        sign = (-1) ** n_broken
        dec_list = [{"edge": _edge_json(e), "type": t} for e, t in dec]
        svg = render_period_svg(inp.vertices, edges_raw, dec_list, tubes, [], coords)
        broken_edges = [_edge_json(e) for e, t in dec if t == "broken"]
        latex = _phi_form_latex(dec_list, inp.vertices, edges_raw, tubes_fs, boundaries)
        terms.append({
            "sign": sign,
            "dec": dec_list,
            "svg": svg,
            "n_broken": n_broken,
            "broken_edges": broken_edges,
            "latex": latex or "",
        })

    return {
        "graph_svg": graph_svg,
        "terms": terms,
        "vertices": inp.vertices,
        "edges": inp.edges,
    }


@app.post("/zonotopes")
def zonotopes(inp: GraphInput):
    """
    Group acyclic decorated graphs by broken-edge configuration.
    Mirrors Wolfram frwComputeZonotopes:
      - n_zono = 2^|E|  (one zonotope per subset of edges that could be broken)
      - zono_sizes[i]   = number of acyclic decorated graphs with that broken-edge subset
    Subsets ordered largest-first (all-broken first, no-broken last).
    """
    _check_limits(inp.vertices, inp.edges)

    edges = build_edges(inp.edges)
    vertices = list(inp.vertices)

    # Collect acyclic decorated graphs, binned by their broken-edge subset
    adec_count = 0
    broken_groups: dict = {}  # broken_key -> list of pinched-edge counts
    for dec in all_decorations(edges):
        if adec_q(dec, vertices):
            adec_count += 1
            broken_key = frozenset(e for e, t in dec if t == "broken")
            pinched_count = sum(1 for e, t in dec if t == "pinched")
            broken_groups.setdefault(broken_key, []).append(pinched_count)

    # Enumerate all 2^|E| broken-edge subsets, largest first (mirrors Wolfram Reverse[Subsets[]])
    edge_list = sorted(edges, key=sorted)
    n_e = len(edge_list)
    n_v = len(vertices)
    all_broken_subs = []
    for r in range(n_e, -1, -1):
        for sub in combinations(range(n_e), r):
            all_broken_subs.append(frozenset(edge_list[i] for i in sub))

    zono_sizes = [len(broken_groups.get(s, [])) for s in all_broken_subs]

    def graph_rank(broken_sub):
        """rank(H) = |V| - c(H) where H = G \ broken_sub."""
        active_edges = [e for e in edges if e not in broken_sub]
        parent = {v: v for v in vertices}
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for e in active_edges:
            u, v = tuple(e)
            pu, pv = find(u), find(v)
            if pu != pv:
                parent[pu] = pv
        components = len({find(v) for v in vertices})
        return n_v - components

    def compute_fvec(pinched_counts, rank):
        """f-vector: exact counts for k=0..rank-1, final bin for k>=rank."""
        if not pinched_counts:
            return []
        bins = [pinched_counts.count(k) for k in range(rank)]
        top = sum(1 for c in pinched_counts if c >= rank)
        return bins + [top]

    f_vectors = [
        compute_fvec(broken_groups.get(s, []), graph_rank(s))
        for s in all_broken_subs
    ]

    # SVG for each zonotope: broken edges as "broken", all others as "pinched"
    positions_raw = _parse_positions(inp.positions)
    coords = get_coords(inp.vertices, positions_raw, frozenset(frozenset(e[:2]) for e in inp.edges))
    edges_raw = [_edge_json(e) for e in edges]
    tubes: list = []

    zono_svgs = []
    for broken_sub in all_broken_subs:
        dec_list = [
            {"edge": _edge_json(e), "type": "broken" if e in broken_sub else "pinched"}
            for e in edges
        ]
        svg = render_period_svg(inp.vertices, edges_raw, dec_list, tubes, [], coords)
        zono_svgs.append(svg)

    return {
        "n_adec": adec_count,
        "n_zono": len(all_broken_subs),
        "zono_sizes": zono_sizes,
        "f_vectors": f_vectors,
        "zono_svgs": zono_svgs,
    }


def _render_regions(vertices, edges_raw, dec_dicts, coords):
    """Return list of {verts, svg} for each region under this decoration."""
    dec_tuples = _dec_to_tuples(dec_dicts)
    regions = region_list(dec_tuples, vertices)
    out = []
    for region in sorted(regions, key=lambda r: sorted(r)):
        svg = render_letter_svg(vertices, edges_raw, list(region), coords, dec_list=dec_dicts)
        out.append({"verts": sorted(region), "svg": svg})
    return out


@app.post("/debug_period")
def debug_period(inp: DecInput):
    """
    Development endpoint: returns intermediate data for period LaTeX computation.
    Shows regions of g and h as subgraphs, tube polynomials, and cut values.
    """
    _check_limits(inp.vertices, inp.edges)
    dec = [{"edge": d.edge, "type": d.type} for d in inp.dec]

    try:
        result = compute_tubings(inp.vertices, inp.edges, dec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    edges_fs = build_edges(result["edges"])
    coords = get_coords(inp.vertices, positions_norm=_parse_positions(inp.positions), edges_frozensets=edges_fs)

    tubes_fs = [
        (frozenset(t["verts"]), frozenset(build_edges(t["edges"])))
        for t in result["tubes"]
    ]
    boundaries = precompute_boundary(tubes_fs, edges_fs)

    # Gamma regions (frozensets) — used for x-variable assignment in cut values
    g_regions_fs = region_list(_dec_to_tuples(dec), inp.vertices)

    # Regions + cut-tubing SVGs for g
    g_regions = _render_regions(inp.vertices, inp.edges, dec, coords)
    g_cut_svgs = [
        render_period_svg(inp.vertices, result["edges"], dec, result["tubes"], ts, coords)
        for ts in result["cut_tubings"]
    ]

    h_regions = None
    h_cut_svgs = None
    h_cut_tubings = None
    if inp.h_dec:
        h_dec = [{"edge": d.edge, "type": d.type} for d in inp.h_dec]
        h_regions = _render_regions(inp.vertices, inp.edges, h_dec, coords)
        try:
            h_result = compute_tubings(inp.vertices, inp.edges, h_dec)
            h_cut_tubings = h_result["cut_tubings"]
            h_cut_svgs = [
                render_period_svg(inp.vertices, h_result["edges"], h_dec, h_result["tubes"], ts, coords)
                for ts in h_cut_tubings
            ]
        except ValueError:
            h_cut_svgs = []
            h_cut_tubings = []

    # Tube picture index + global order string
    plain_dec = [{"edge": list(e), "type": "oriented_fwd"} for e in inp.edges]
    tubes_list = result["tubes"]
    tube_svgs = [
        render_period_svg(inp.vertices, result["edges"], plain_dec, tubes_list, [i], coords)
        for i in range(len(tubes_list))
    ]
    tube_order = [
        i + 1 for i in sorted(
            range(len(tubes_list)),
            key=lambda i: (
                -len(tubes_list[i]["verts"]),
                -len(tubes_list[i]["edges"]),
                tuple(sorted(tubes_list[i]["verts"])),
            )
        )
    ]

    # Tube polynomials for all tubes (as LaTeX strings)
    tube_polys = {}
    for i, t in enumerate(result["tubes"]):
        lin = _tube_poly_lin(i, tubes_fs, boundaries)
        tube_polys[str(i)] = {
            "verts": t["verts"],
            "edges": t["edges"],
            "poly_latex": _lincombo_latex(lin),
            "poly_terms": _lin_to_terms(lin),
        }

    # Per-cut-tubing: tube polynomial values, cut values x[v]
    cut_data = []
    for ct in result["cut_tubings"]:
        x_vals = _compute_cut_values(ct, tubes_fs, boundaries, g_regions_fs)
        cut_data.append({
            "cut_tubing": ct,
            "tubes_in_cut": [tube_polys[str(i)] for i in ct],
            "x_values": {
                str(v): _lincombo_latex(lin)
                for v, lin in sorted(x_vals.items())
            },
            "twist_latex": _twist_latex(result["vertices"], x_vals),
            "region_latex": _integration_region(result["vertices"], x_vals),
        })

    g_cut_tubings = result["cut_tubings"]
    g_dec_tuples = _dec_to_tuples(dec)
    h_dec_tuples = _dec_to_tuples(h_dec) if inp.h_dec else None
    h_regions_fs = region_list(h_dec_tuples, inp.vertices) if h_dec_tuples else None
    cgh_pairs = None
    if h_cut_tubings is not None:
        raw_pairs = cgh(g_cut_tubings, h_cut_tubings)
        cgh_pairs = []
        for g_ct, h_ct in raw_pairs:
            # angleMap applied to region-min vertices of g and h respectively
            g_region_min = sorted(min(R) for R in g_regions_fs)
            h_region_min = sorted(min(R) for R in h_regions_fs)
            g_am_seq = [angle_map(v, g_ct, tubes_fs) for v in g_region_min]
            h_am_seq = [angle_map(v, h_ct, tubes_fs) for v in h_region_min]

            g_sign = cut_tubing_sign(g_ct, g_dec_tuples, inp.vertices, tubes_fs)
            h_sign = cut_tubing_sign(h_ct, h_dec_tuples, inp.vertices, tubes_fs)
            combined_sign = g_sign * h_sign

            # Form — first part: sign × ∧_{i ∈ ch\cg} dlog(τ_i|_cut)
            cg_set = frozenset(g_ct)
            ch_minus_cg = [t for t in h_ct if t not in cg_set]   # order from ch
            concat = list(g_ct) + ch_minus_cg                     # cg ⊔ (ch\cg)
            form_sign = _list_signature(concat) * _list_signature(list(h_ct))

            x_vals_cut = _compute_cut_values(g_ct, tubes_fs, boundaries, g_regions_fs)
            form_dlogs = [
                {
                    "tube_idx": t,
                    "poly_latex": _lincombo_latex(
                        _tube_poly_on_cut(t, tubes_fs, boundaries, x_vals_cut)
                    ),
                }
                for t in ch_minus_cg
            ]

            # Form — second part: ∧_{r ∈ R2} ∧_{v ∈ r \ min(r)} dlog(x_v / x_{min(r)})
            # R2 = multi-vertex regions of h; all x_v evaluated on the cg-cut
            R2 = sorted([R for R in h_regions_fs if len(R) > 1], key=min)
            form_part2 = []
            for R in R2:
                min_r = min(R)
                x_min_lat = (
                    _lincombo_latex(x_vals_cut[min_r])
                    if min_r in x_vals_cut else f"x_{{{min_r}}}"
                )
                for v in sorted(R):
                    if v == min_r:
                        continue
                    x_v_lat = (
                        _lincombo_latex(x_vals_cut[v])
                        if v in x_vals_cut else f"x_{{{v}}}"
                    )
                    form_part2.append({"num_latex": x_v_lat, "den_latex": x_min_lat})

            total_sign = combined_sign * form_sign
            cgh_pairs.append({
                "g": g_ct,
                "h": h_ct,
                "g_region_min": g_region_min,
                "h_region_min": h_region_min,
                "g_am_seq": g_am_seq,
                "h_am_seq": h_am_seq,
                "g_sign": g_sign,
                "h_sign": h_sign,
                "sign": combined_sign,
                "ch_minus_cg": ch_minus_cg,
                "form_sign": form_sign,
                "total_sign": total_sign,
                "form_dlogs": form_dlogs,
                "form_part2": form_part2,
            })

    # Compute period twist and Γ once from first g-tubing; cross-check all g-tubings
    period_twist_latex = None
    period_region_latex = None
    twist_consistent = True
    region_consistent = True
    if g_cut_tubings:
        g_twist_checks = []
        g_region_checks = []
        for ct in g_cut_tubings:
            xv = _compute_cut_values(ct, tubes_fs, boundaries, g_regions_fs)
            g_twist_checks.append(_twist_latex(result["vertices"], xv))
            g_region_checks.append(tuple(_integration_region(result["vertices"], xv)))
        period_twist_latex = g_twist_checks[0]
        period_region_latex = list(g_region_checks[0])
        twist_consistent = len(set(g_twist_checks)) <= 1
        region_consistent = len(set(g_region_checks)) <= 1

    # Pre-assemble period integral LaTeX so the frontend needs no duplicate implementation
    period_integral_latex = None
    if inp.h_dec:
        try:
            period_integral_latex = _period_integral_tex(
                dec, h_dec, inp.vertices, inp.edges, tubes_fs, boundaries
            )
        except Exception:
            pass

    return {
        "vertices": result["vertices"],
        "edges": result["edges"],
        "compatible_tube_indices": result.get("compatible_tube_indices", []),
        "n_regions": result.get("n_regions"),
        "tube_svgs": tube_svgs,
        "tube_order": tube_order,
        "g_regions": g_regions,
        "g_cut_svgs": g_cut_svgs,
        "g_cut_tubings": g_cut_tubings,
        "h_regions": h_regions,
        "h_cut_svgs": h_cut_svgs,
        "h_cut_tubings": h_cut_tubings,
        "cgh_pairs": cgh_pairs,
        "tube_polys": tube_polys,
        "cut_data": cut_data,
        "period_twist_latex": period_twist_latex,
        "period_region_latex": period_region_latex,
        "twist_consistent": twist_consistent,
        "region_consistent": region_consistent,
        "period_integral_latex": period_integral_latex,
    }


# ── Static frontend (optional) ───────────────────────────────────────────────

if _SERVE_FRONTEND:
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        file_path = os.path.join(_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_DIST, "index.html"))
