/**
 * Small read-only SVG rendering of a decorated graph with optional tube highlights.
 *
 * dec: [{edge:[u,v], type:"oriented_fwd"|"oriented_rev"|"pinched"|"broken"|"solid"}]
 * vertices: [1,2,3,...]
 * edges: [[u,v],...]
 * tubeIndices: optional list of tube indices to highlight
 * tubes: list of {verts:[...], edges:[[u,v],...]}
 */
import { edgeKey } from "./graphUtils";

function graphSize(nVerts) {
  return Math.max(150, Math.min(340, 100 + nVerts * 45));
}
function graphR(nVerts) {
  // Radius proportional to the shortest edge in the circle layout.
  // Circle layout uses radius = SIZE × 0.35; adjacent-vertex distance = 2r·sin(π/n).
  const size = graphSize(nVerts);
  const layoutR = size * 0.35;
  const minEdge = nVerts <= 1 ? size * 0.5 : 2 * layoutR * Math.sin(Math.PI / nVerts);
  return Math.max(11, Math.min(20, Math.round(minEdge * 0.18)));
}

// Tube stroke color palette — opaque so borders are clearly visible
const TUBE_STROKE_COLORS = [
  "rgba(59,130,246,0.85)",
  "rgba(16,185,129,0.85)",
  "rgba(245,158,11,0.85)",
  "rgba(236,72,153,0.85)",
  "rgba(139,92,246,0.85)",
  "rgba(239,68,68,0.85)",
];

/**
 * Returns an SVG path string for a "stadium" (capsule) shape around the
 * edge from pu to pv with the given radius. Endpoints are extended outward
 * by vertR so vertex circles (radius vertR) sit inside the caps, not on the boundary.
 */
function capsulePath(pu, pv, r, vertR) {
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const L = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / L, uy = dy / L; // unit along edge
  const px = -uy, py = ux;       // unit perpendicular

  // Push cap centres outward by vertR so vertices are fully inside
  const e0x = pu.x - ux * vertR, e0y = pu.y - uy * vertR;
  const e1x = pv.x + ux * vertR, e1y = pv.y + uy * vertR;

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

function TubeHalo({ tube, pos, colorIdx, r, vertR }) {
  const stroke = TUBE_STROKE_COLORS[colorIdx % TUBE_STROKE_COLORS.length];
  const verts = tube.verts;
  const edges = tube.edges;

  if (verts.length === 1) {
    const p = pos[verts[0]];
    if (!p) return null;
    return <circle cx={p.x} cy={p.y} r={r} fill="none" stroke={stroke} strokeWidth={2} />;
  }

  if (edges.length === 1) {
    // Single-edge tube: draw one capsule along the edge.
    const [u, v] = edges[0];
    const pu = pos[u], pv = pos[v];
    if (!pu || !pv) return null;
    return <path d={capsulePath(pu, pv, r, vertR)} fill="none" stroke={stroke} strokeWidth={2} />;
  }

  // Multi-edge tube: draw one bounding circle enclosing all tube vertices.
  // Drawing one capsule per edge produces N overlapping shapes that look like N tubes.
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
        const key = [...edge].sort((a, b) => a - b).join("-");
        m[key] = type;
      });
    }
    return m;
  })();

  return (
    <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="graph-mini" overflow="visible">
      {/* Tube halos — sorted largest first so smaller tubes render on top.
          Radius grows with vertex count so nesting is visually obvious. */}
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
          />
        ));
      })()}

      {/* Edges */}
      {edges.map(([u, v]) => {
        const key = edgeKey(u, v);
        const type = decMap[key] || "oriented_fwd";
        const pu = pos[u], pv = pos[v];
        if (!pu || !pv) return null;

        const dx = pv.x - pu.x, dy = pv.y - pu.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const nx = -dy / len, ny = dx / len; // normal

        if (type === "pinched") {
          // Double line
          const off = 2.5;
          return (
            <g key={key}>
              <line x1={pu.x + nx * off} y1={pu.y + ny * off}
                    x2={pv.x + nx * off} y2={pv.y + ny * off}
                    stroke="#e2e8f0" strokeWidth={2.5} />
              <line x1={pu.x - nx * off} y1={pu.y - ny * off}
                    x2={pv.x - nx * off} y2={pv.y - ny * off}
                    stroke="#e2e8f0" strokeWidth={2.5} />
            </g>
          );
        }

        if (type === "broken") {
          return (
            <line key={key} x1={pu.x} y1={pu.y} x2={pv.x} y2={pv.y}
                  stroke="#94a3b8" strokeWidth={2.5} strokeDasharray="4 3" />
          );
        }

        if (type === "oriented_fwd" || type === "oriented_rev") {
          // Arrow: u→v for fwd, v→u for rev
          const [ax, ay, bx, by] = type === "oriented_fwd"
            ? [pu.x, pu.y, pv.x, pv.y]
            : [pv.x, pv.y, pu.x, pu.y];
          const ddx = bx - ax, ddy = by - ay;
          const ll = Math.sqrt(ddx * ddx + ddy * ddy) || 1;
          const ux = ddx / ll, uy = ddy / ll;
          const pnx = -uy, pny = ux;
          // Line shortened at both ends to clear vertex circles
          const x1 = ax + ux * R, y1 = ay + uy * R;
          const x2 = bx - ux * R, y2 = by - uy * R;
          // Arrowhead tip at 60% along the edge
          const mx = ax + ddx * 0.6, my = ay + ddy * 0.6;
          const hsize = Math.round(R * 0.8);
          const basex = mx - ux * hsize, basey = my - uy * hsize;
          return (
            <g key={key}>
              <line x1={x1} y1={y1} x2={x2} y2={y2}
                    stroke="#e2e8f0" strokeWidth={2.5} />
              <polygon
                points={`${mx},${my} ${basex + pnx * hsize},${basey + pny * hsize} ${basex - pnx * hsize},${basey - pny * hsize}`}
                fill="#e2e8f0"
              />
            </g>
          );
        }

        // fallback
        return (
          <line key={key} x1={pu.x} y1={pu.y} x2={pv.x} y2={pv.y}
                stroke="#e2e8f0" strokeWidth={2.5} />
        );
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
