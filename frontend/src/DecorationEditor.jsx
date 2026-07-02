/**
 * Reads the graph structure (vertices + edges) and lets the user click edges
 * to cycle through decoration types: oriented_fwd → oriented_rev → pinched → broken → oriented_fwd.
 * Parallel edges are drawn as separate offset arcs, each independently clickable.
 *
 * Props:
 *   graph:              { vertices: [int], edges: [[u,v]] }
 *   decoration:         { [edgeKey]: "oriented_fwd"|"oriented_rev"|"pinched"|"broken" }
 *   onDecorationChange: (newDecoration) => void
 *   isAcyclic:          bool | null  (null = not yet validated)
 *   label:              string
 */
import { edgeKey, withK, parallelOffsets, edgePathD, pointOnEdge } from "./graphUtils";

const W = 330;
const H = 220;
const R = 13;

const CYCLE = ["oriented_fwd", "oriented_rev", "pinched", "broken"];

function Arrow({ pu, pv, off, color, dir }) {
  const d = edgePathD(pu, pv, off);
  const pt = pointOnEdge(pu, pv, off, 0.5);
  let tx = pt.tx, ty = pt.ty;
  if (dir === "rev") { tx = -tx; ty = -ty; }
  const pnx = -ty, pny = tx;
  const hsize = 10;
  const tip = { x: pt.x + tx * hsize * 0.5, y: pt.y + ty * hsize * 0.5 };
  const bx = pt.x - tx * hsize * 0.5, by = pt.y - ty * hsize * 0.5;
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={3} />
      <polygon
        points={`${tip.x},${tip.y} ${bx + pnx * hsize * 0.6},${by + pny * hsize * 0.6} ${bx - pnx * hsize * 0.6},${by - pny * hsize * 0.6}`}
        fill={color}
      />
    </g>
  );
}

function EdgeShape({ type, pu, pv, off, onClick }) {
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len, ny = dx / len;
  const d = edgePathD(pu, pv, off);

  const hit = (
    <path d={d} fill="none" stroke="transparent" strokeWidth={18}
          style={{ cursor: "pointer" }} onClick={onClick} />
  );

  if (type === "oriented_fwd") {
    return (<g><Arrow pu={pu} pv={pv} off={off} color="#334155" dir="fwd" />{hit}</g>);
  }
  if (type === "oriented_rev") {
    return (<g><Arrow pu={pu} pv={pv} off={off} color="#334155" dir="rev" />{hit}</g>);
  }
  if (type === "pinched") {
    const o = 3;
    const d1 = edgePathD({ x: pu.x + nx * o, y: pu.y + ny * o }, { x: pv.x + nx * o, y: pv.y + ny * o }, off);
    const d2 = edgePathD({ x: pu.x - nx * o, y: pu.y - ny * o }, { x: pv.x - nx * o, y: pv.y - ny * o }, off);
    return (
      <g>
        <path d={d1} fill="none" stroke="#334155" strokeWidth={3} />
        <path d={d2} fill="none" stroke="#334155" strokeWidth={3} />
        {hit}
      </g>
    );
  }
  if (type === "broken") {
    return (
      <g>
        <path d={d} fill="none" stroke="#94a3b8" strokeWidth={3} strokeDasharray="4 3" />
        {hit}
      </g>
    );
  }
  return null;
}

export default function DecorationEditor({ graph, decoration, onDecorationChange, isAcyclic, label, positions, blank, toggleLabel, toggleValue, onToggleChange }) {
  // Scale normalized [0,1] positions to this canvas
  const pos = {};
  graph.vertices.forEach((v) => {
    const p = positions?.[v];
    if (p) pos[v] = { x: p.x * W, y: p.y * H };
  });

  function cycleEdge(u, v, k) {
    const key = edgeKey(u, v, k);
    const current = decoration[key] || "oriented_fwd";
    const next = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
    onDecorationChange({ ...decoration, [key]: next });
  }

  const acyclicBadge = isAcyclic === null ? null
    : isAcyclic
      ? <span className="badge badge-ok">✓ acyclic</span>
      : <span className="badge badge-err">✗ not acyclic</span>;

  const offs = parallelOffsets(graph.edges);

  return (
    <div className="dec-editor">
      <div className="dec-editor-header">
        <span className="dec-label">{label}</span>
        {acyclicBadge}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ aspectRatio: `${W}/${H}` }} className="graph-mini-editor">
        {!blank && withK(graph.edges).map(([u, v, k], i) => {
          const pu = pos[u], pv = pos[v];
          if (!pu || !pv) return null;
          const key = edgeKey(u, v, k);
          const type = decoration[key] || "oriented_fwd";
          return (
            <EdgeShape
              key={key + "#" + i}
              type={type}
              pu={pu}
              pv={pv}
              off={offs[i]}
              onClick={() => cycleEdge(u, v, k)}
            />
          );
        })}
        {!blank && graph.vertices.map((id) => {
          const p = pos[id];
          if (!p) return null;
          return (
            <g key={id}>
              <circle cx={p.x} cy={p.y} r={R} fill="#1e293b" stroke="#64748b" strokeWidth={1.5} />
              <text
                x={p.x} y={p.y}
                textAnchor="middle" dominantBaseline="central"
                fill="white" fontSize={11} fontWeight="bold"
                style={{ userSelect: "none", pointerEvents: "none" }}
              >
                {id}
              </text>
            </g>
          );
        })}
      </svg>
      {toggleLabel && (
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={toggleValue}
            onChange={(e) => onToggleChange(e.target.checked)}
          />
          {toggleLabel}
        </label>
      )}
      <div className="hint"><span>Click edge to cycle type</span></div>
      <div className="dec-legend">
        <span>→, ← oriented</span>
        <span>= pinched</span>
        <span>- - broken</span>
      </div>
    </div>
  );
}
