/** Shared graph utility functions. */

/** Canonical key for an undirected edge (u, v). */
export function edgeKey(u, v) {
  return [u, v].sort((a, b) => a - b).join("-");
}

/** Convert an SVG string to a data URI suitable for use as an img src. */
export function svgDataUri(svg) {
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}
