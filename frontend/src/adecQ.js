/**
 * Client-side acyclicity check for decorated graphs.
 * Mirrors the Python adec_q function.
 *
 * vertices: [int]
 * edges:    [[u,v], ...]
 * decoration: { "u-v": "oriented_fwd"|"oriented_rev"|"pinched"|"broken" }
 */
import { edgeKey, withK } from "./graphUtils";

export function adecQ(vertices, edges, decoration) {
  if (vertices.length === 0) return true;

  // Union-Find for pinched edges
  const parent = {};
  vertices.forEach((v) => { parent[v] = v; });

  function find(x) {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  }

  function union(a, b) {
    const ra = find(a), rb = find(b);
    if (ra !== rb) parent[ra < rb ? rb : ra] = ra < rb ? ra : rb;
  }

  withK(edges).forEach(([u, v, k]) => {
    const key = edgeKey(u, v, k);
    if ((decoration[key] || "oriented_fwd") === "pinched") {
      union(u, v);
    }
  });

  // Build adjacency for cycle detection using Kahn's algorithm
  const nodeMap = {};
  vertices.forEach((v) => { nodeMap[v] = find(v); });

  // Collect contracted nodes and directed edges
  const nodes = new Set(Object.values(nodeMap));
  const inDegree = {};
  const adj = {};
  nodes.forEach((n) => { inDegree[n] = 0; adj[n] = []; });

  for (const [u, v, k] of withK(edges)) {
    const key = edgeKey(u, v, k);
    const type = decoration[key] || "oriented_fwd";
    if (type !== "oriented_fwd" && type !== "oriented_rev") continue;
    const cu = nodeMap[u], cv = nodeMap[v];
    if (cu === cv) return false; // self-loop after contraction
    const [src, dst] = type === "oriented_fwd" ? [cu, cv] : [cv, cu];
    adj[src].push(dst);
    inDegree[dst]++;
  }

  // Kahn's algorithm
  const queue = [];
  nodes.forEach((n) => { if (inDegree[n] === 0) queue.push(n); });
  let visited = 0;
  while (queue.length > 0) {
    const n = queue.shift();
    visited++;
    for (const nb of adj[n]) {
      inDegree[nb]--;
      if (inDegree[nb] === 0) queue.push(nb);
    }
  }
  return visited === nodes.size;
}
