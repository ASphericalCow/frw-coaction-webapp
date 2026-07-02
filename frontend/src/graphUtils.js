/** Shared graph utility functions. */

/**
 * Canonical key for an (undirected) edge (u, v) with parallel index k.
 * Backward-compatible: k = 1 (a non-parallel edge) yields the old "lo-hi" key,
 * so existing single-edge decorations keep working.  Parallel edges get
 * "lo-hi-k" (k = 2, 3, ...).
 */
export function edgeKey(u, v, k = 1) {
  const [lo, hi] = [u, v].slice().sort((a, b) => a - b);
  return k > 1 ? `${lo}-${hi}-${k}` : `${lo}-${hi}`;
}

/**
 * Attach a parallel index k to each edge, assigned by order of appearance
 * within the same vertex pair.  Returns [[u, v, k], ...] aligned to `edges`.
 * Matches build_edges() on the backend.
 */
export function withK(edges) {
  const counts = {};
  return edges.map(([u, v]) => {
    const key = [u, v].slice().sort((a, b) => a - b).join("-");
    counts[key] = (counts[key] || 0) + 1;
    return [u, v, counts[key]];
  });
}

/**
 * Perpendicular bend (px) for each edge (aligned to `edges`) so parallel edges
 * separate into distinct arcs.  A lone edge gets 0 (straight line).
 */
export function parallelOffsets(edges, bend = 14) {
  const wk = withK(edges);
  const total = {};
  wk.forEach(([u, v]) => {
    const key = [u, v].slice().sort((a, b) => a - b).join("-");
    total[key] = (total[key] || 0) + 1;
  });
  return wk.map(([u, v, k]) => {
    const key = [u, v].slice().sort((a, b) => a - b).join("-");
    const m = total[key];
    return m <= 1 ? 0 : (k - 1 - (m - 1) / 2) * bend;
  });
}

/** SVG path 'd' for a (possibly bent) edge from pu to pv with perpendicular offset. */
export function edgePathD(pu, pv, off = 0) {
  if (!off || Math.abs(off) < 1e-6) return `M ${pu.x} ${pu.y} L ${pv.x} ${pv.y}`;
  const mx = (pu.x + pv.x) / 2, my = (pu.y + pv.y) / 2;
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L;
  const cx = mx + nx * off * 2, cy = my + ny * off * 2;
  return `M ${pu.x} ${pu.y} Q ${cx} ${cy} ${pv.x} ${pv.y}`;
}

/** Point + unit tangent at parameter t along the (bent) edge path. */
export function pointOnEdge(pu, pv, off, t) {
  if (!off || Math.abs(off) < 1e-6) {
    const dx = pv.x - pu.x, dy = pv.y - pu.y, L = Math.hypot(dx, dy) || 1;
    return { x: pu.x + dx * t, y: pu.y + dy * t, tx: dx / L, ty: dy / L };
  }
  const mx = (pu.x + pv.x) / 2, my = (pu.y + pv.y) / 2;
  const dx = pv.x - pu.x, dy = pv.y - pu.y, L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L;
  const cx = mx + nx * off * 2, cy = my + ny * off * 2;
  const x = (1 - t) ** 2 * pu.x + 2 * (1 - t) * t * cx + t ** 2 * pv.x;
  const y = (1 - t) ** 2 * pu.y + 2 * (1 - t) * t * cy + t ** 2 * pv.y;
  let tx = 2 * (1 - t) * (cx - pu.x) + 2 * t * (pv.x - cx);
  let ty = 2 * (1 - t) * (cy - pu.y) + 2 * t * (pv.y - cy);
  const TL = Math.hypot(tx, ty) || 1;
  return { x, y, tx: tx / TL, ty: ty / TL };
}

/** Convert an SVG string to a data URI suitable for use as an img src. */
export function svgDataUri(svg) {
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}
