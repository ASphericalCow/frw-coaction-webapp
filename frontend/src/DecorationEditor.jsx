/**
 * Reads the graph structure (vertices + edges) and lets the user click edges
 * to cycle through decoration types: oriented_fwd → oriented_rev → pinched → broken → oriented_fwd.
 *
 * Props:
 *   graph:              { vertices: [int], edges: [[u,v]] }
 *   decoration:         { [edgeKey]: "oriented_fwd"|"oriented_rev"|"pinched"|"broken" }
 *   onDecorationChange: (newDecoration) => void
 *   isAcyclic:          bool | null  (null = not yet validated)
 *   label:              string
 */
import { edgeKey } from "./graphUtils";

const W = 330;
const H = 220;
const R = 13;

const CYCLE = ["oriented_fwd", "oriented_rev", "pinched", "broken"];

function Arrow({ pu, pv, color }) {
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / len, uy = dy / len;
  const pnx = -uy, pny = ux;
  // Line shortened at both ends to clear vertex circles
  const x1 = pu.x + ux * R, y1 = pu.y + uy * R;
  const x2 = pv.x - ux * R, y2 = pv.y - uy * R;
  // Arrowhead tip at 60% along the edge
  const mx = pu.x + dx * 0.6, my = pu.y + dy * 0.6;
  const hsize = 10;
  const basex = mx - ux * hsize, basey = my - uy * hsize;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={3} />
      <polygon
        points={`${mx},${my} ${basex + pnx * hsize},${basey + pny * hsize} ${basex - pnx * hsize},${basey - pny * hsize}`}
        fill={color}
      />
    </g>
  );
}

function EdgeShape({ type, pu, pv, onClick }) {
  const dx = pv.x - pu.x, dy = pv.y - pu.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len, ny = dx / len;

  // Invisible wide hit area
  const hitLine = (
    <line
      x1={pu.x} y1={pu.y} x2={pv.x} y2={pv.y}
      stroke="transparent" strokeWidth={18}
      style={{ cursor: "pointer" }}
      onClick={onClick}
    />
  );

  if (type === "oriented_fwd") {
    return (
      <g>
        <Arrow pu={pu} pv={pv} color="#334155" />
        {hitLine}
      </g>
    );
  }

  if (type === "oriented_rev") {
    return (
      <g>
        <Arrow pu={pv} pv={pu} color="#334155" />
        {hitLine}
      </g>
    );
  }

  if (type === "pinched") {
    const off = 3;
    return (
      <g>
        <line x1={pu.x + nx * off} y1={pu.y + ny * off}
              x2={pv.x + nx * off} y2={pv.y + ny * off}
              stroke="#334155" strokeWidth={3} />
        <line x1={pu.x - nx * off} y1={pu.y - ny * off}
              x2={pv.x - nx * off} y2={pv.y - ny * off}
              stroke="#334155" strokeWidth={3} />
        {hitLine}
      </g>
    );
  }

  if (type === "broken") {
    return (
      <g>
        <line x1={pu.x} y1={pu.y} x2={pv.x} y2={pv.y}
              stroke="#94a3b8" strokeWidth={3} strokeDasharray="4 3" />
        {hitLine}
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

  function cycleEdge(u, v) {
    const key = edgeKey(u, v);
    const current = decoration[key] || "oriented_fwd";
    const next = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
    onDecorationChange({ ...decoration, [key]: next });
  }

  const acyclicBadge = isAcyclic === null ? null
    : isAcyclic
      ? <span className="badge badge-ok">✓ acyclic</span>
      : <span className="badge badge-err">✗ not acyclic</span>;

  return (
    <div className="dec-editor">
      <div className="dec-editor-header">
        <span className="dec-label">{label}</span>
        {acyclicBadge}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ aspectRatio: `${W}/${H}` }} className="graph-mini-editor">
        {!blank && graph.edges.map(([u, v]) => {
          const pu = pos[u], pv = pos[v];
          if (!pu || !pv) return null;
          const key = edgeKey(u, v);
          const type = decoration[key] || "oriented_fwd";
          return (
            <EdgeShape
              key={key}
              type={type}
              pu={pu}
              pv={pv}
              onClick={() => cycleEdge(u, v)}
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
