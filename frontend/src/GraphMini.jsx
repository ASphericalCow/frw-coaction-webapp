/**
 * Small read-only SVG rendering of a decorated graph with optional tube highlights.
 *
 * dec: [{edge:[u,v,k], type:"oriented_fwd"|"oriented_rev"|"pinched"|"broken"|"solid"}]
 * vertices: [1,2,3,...]
 * edges: [[u,v],...] or [[u,v,k],...]
 * tubeIndices: optional list of tube indices to highlight
 * tubes: list of {verts:[...], edges:[[u,v,k],...]}
 */
import { edgeKey, withK, parallelOffsets, edgePathD, pointOnEdge } from "./graphUtils";

function graphSize(nVerts) {
  return Math.max(150, Math.min(340, 100 + nVerts * 45));
}
function graphR(nVerts) {
  const size = graphSize(nVerts);
  const layoutR = size * 0.35;
  const minEdge = nVerts <= 1 ? size * 0.5 : 2 * layoutR * Math.sin(Math.PI / nVerts);
  return Math.max(11, Math.min(20, Math.round(minEdge * 0.18)));
}

const TUBE_STROKE_COLORS = [
  "rgba(59,130,246,0.85)",
  "rgba(16,185,129,0.85)",
  "rgba(245,158,11,0.85)",
  "rgba(236,72,153,0.85)",
  "rgba(139,92,246,0.85)",
  "rgba(239,68,68,0.85)",
];

/** Capsule (stadium) path around an edge, optionally shifted perpendicular by `off`. */
function capsulePath(pu, pv, r, vertR, off = 0) {
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const L = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / L, uy = dy / L;
  const px = -uy, py = ux;
  // shift the capsule centreline toward the bent edge (approx follows the arc)
  const su = { x: pu.x + px * off, y: pu.y + py * off };
  const sv = { x: pv.x + px * off, y: pv.y + py * off };

  const e0x = su.x - ux * vertR, e0y = su.y - uy * vertR;
  const e1x = sv.x + ux * vertR, e1y = sv.y + uy * vertR;
  const a1x = e0x + px * r, a1y = e0y + py * r;
  const a2x = e0x - px * r, a2y = e0y - py * r;
  const b1x = e1x + px * r, b1y = e1y + py * r;
  const b2x = e1x - px * r, b2y = e1y - py * r;
  return [
    `M ${a1x},${a1y}`,
    `L ${b1x},${b1y}`,
    `A ${r},${r},0,1,0,${b2x},${b2y}`,
    `L ${a2x},${a2y}`,
    `A ${r},${r},0,1,0,${a1x},${a1y}`,
    "Z",
  ].join(" ");
}

function TubeHalo({ tube, pos, colorIdx, r, vertR, edgeOff }) {
  const stroke = TUBE_STROKE_COLORS[colorIdx % TUBE_STROKE_COLORS.length];
  const verts = tube.verts;
  const edges = tube.edges;

  if (verts.length === 1) {
    const p = pos[verts[0]];
    if (!p) return null;
    return <circle cx={p.x} cy={p.y} r={r} fill="none" stroke={stroke} strokeWidth={2} />;
  }

  if (edges.length === 1) {
    const e = edges[0];
    const pu = pos[e[0]], pv = pos[e[1]];
    if (!pu || !pv) return null;
    const off = edgeOff ? (edgeOff[edgeKey(e[0], e[1], e[2] || 1)] || 0) : 0;
    return <path d={capsulePath(pu, pv, r, vertR, off * 0.5)} fill="none" stroke={stroke} strokeWidth={2} />;
  }

  const positions = verts.map((v) => pos[v]).filter(Boolean);
  if (positions.length === 0) return null;
  const cx = positions.reduce((s, p) => s + p.x, 0) / positions.length;
  const cy = positions.reduce((s, p) => s + p.y, 0) / positions.length;
  const maxDist = Math.max(...positions.map((p) => Math.hypot(p.x - cx, p.y - cy)));
  return <circle cx={cx} cy={cy} r={maxDist + r} fill="none" stroke={stroke} strokeWidth={2} />;
}

export default function GraphMini({ dec, vertices, edges, tubeIndices, tubes, positions }) {
  const SIZE = graphSize(vertices.length);
  const R = graphR(vertices.length);
  const fontSize = Math.max(7, Math.round(R * 0.75));

  const pos = {};
  vertices.forEach((v) => {
    const p = positions?.[v];
    if (p) pos[v] = { x: p.x * SIZE, y: p.y * SIZE };
  });

  const decMap = (() => {
    const m = {};
    if (dec) {
      dec.forEach(({ edge, type }) => {
        m[edgeKey(edge[0], edge[1], edge[2] || 1)] = type;
      });
    }
    return m;
  })();

  const offs = parallelOffsets(edges);
  // map edgeKey -> offset (for tube halos)
  const edgeOff = {};
  withK(edges).forEach(([u, v, k], i) => { edgeOff[edgeKey(u, v, k)] = offs[i]; });

  return (
    <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="graph-mini" overflow="visible">
      {tubeIndices && tubes && (() => {
        const sorted = [...tubeIndices].sort(
          (a, b) => tubes[b].verts.length - tubes[a].verts.length
        );
        return sorted.map((ti, i) => (
          <TubeHalo
            key={ti}
            tube={tubes[ti]}
            pos={pos}
            colorIdx={tubeIndices.indexOf(ti)}
            r={R + 4 + tubes[ti].verts.length * 5}
            vertR={R}
            edgeOff={edgeOff}
          />
        ));
      })()}

      {/* Edges (parallel edges bent into distinct arcs) */}
      {withK(edges).map(([u, v, k], i) => {
        const key = edgeKey(u, v, k);
        const type = decMap[key] || "oriented_fwd";
        const pu = pos[u], pv = pos[v];
        if (!pu || !pv) return null;
        const off = offs[i];
        const d = edgePathD(pu, pv, off);
        const dx = pv.x - pu.x, dy = pv.y - pu.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const nx = -dy / len, ny = dx / len;

        if (type === "pinched") {
          const o = 2.5;
          const d1 = edgePathD({ x: pu.x + nx * o, y: pu.y + ny * o }, { x: pv.x + nx * o, y: pv.y + ny * o }, off);
          const d2 = edgePathD({ x: pu.x - nx * o, y: pu.y - ny * o }, { x: pv.x - nx * o, y: pv.y - ny * o }, off);
          return (
            <g key={key + "#" + i}>
              <path d={d1} fill="none" stroke="#e2e8f0" strokeWidth={2.5} />
              <path d={d2} fill="none" stroke="#e2e8f0" strokeWidth={2.5} />
            </g>
          );
        }

        if (type === "broken") {
          return <path key={key + "#" + i} d={d} fill="none" stroke="#94a3b8" strokeWidth={2.5} strokeDasharray="4 3" />;
        }

        if (type === "oriented_fwd" || type === "oriented_rev") {
          const pt = pointOnEdge(pu, pv, off, 0.5);
          let tx = pt.tx, ty = pt.ty;
          if (type === "oriented_rev") { tx = -tx; ty = -ty; }
          const pnx = -ty, pny = tx;
          const hsize = Math.round(R * 0.8);
          const tip = { x: pt.x + tx * hsize * 0.5, y: pt.y + ty * hsize * 0.5 };
          const bx = pt.x - tx * hsize * 0.5, by = pt.y - ty * hsize * 0.5;
          return (
            <g key={key + "#" + i}>
              <path d={d} fill="none" stroke="#e2e8f0" strokeWidth={2.5} />
              <polygon
                points={`${tip.x},${tip.y} ${bx + pnx * hsize},${by + pny * hsize} ${bx - pnx * hsize},${by - pny * hsize}`}
                fill="#e2e8f0"
              />
            </g>
          );
        }

        return <path key={key + "#" + i} d={d} fill="none" stroke="#e2e8f0" strokeWidth={2.5} />;
      })}

      {/* Vertices */}
      {vertices.map((id) => {
        const p = pos[id];
        if (!p) return null;
        return (
          <g key={id}>
            <circle cx={p.x} cy={p.y} r={R} fill="#334155" stroke="#64748b" strokeWidth={1} />
            <text
              x={p.x} y={p.y}
              textAnchor="middle" dominantBaseline="central"
              fill="white" fontSize={fontSize} fontWeight="bold"
              style={{ userSelect: "none" }}
            >
              {id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
