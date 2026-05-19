/**
 * SVG-based interactive graph structure editor (vertices + undirected edges).
 * Click empty canvas → add vertex.
 * Click vertex, then another vertex → add edge.
 * Right-click vertex or edge → delete.
 * Drag vertex → reposition.
 */
import { useState, useRef, useCallback } from "react";
import { edgeKey } from "./graphUtils";

const R = 16;
const W = 330;
const H = 220;


export default function GraphEditor({ graph, onChange, positions, onPositionsChange }) {
  const [selected, setSelected] = useState(null);
  const [dragging, setDragging] = useState(null);
  const svgRef = useRef(null);

  // Convert normalized [0,1] positions to pixel positions for this canvas
  const pixPos = {};
  graph.vertices.forEach((v) => {
    const p = positions[v];
    if (p) pixPos[v] = { x: p.x * W, y: p.y * H };
  });

  const svgPoint = useCallback((e) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }, []);

  function nextVertexId() {
    return graph.vertices.length === 0 ? 1 : Math.max(...graph.vertices) + 1;
  }

  function handleSvgClick(e) {
    if (e.target !== svgRef.current) return;
    if (e.button !== 0) return;
    const pt = svgPoint(e);
    const id = nextVertexId();
    onPositionsChange({ ...positions, [id]: { x: pt.x / W, y: pt.y / H } });
    setSelected(null);
    onChange({ vertices: [...graph.vertices, id], edges: graph.edges });
  }

  function handleVertexClick(e, id) {
    e.stopPropagation();
    if (e.button !== 0) return;
    if (selected === null) {
      setSelected(id);
    } else if (selected === id) {
      setSelected(null);
    } else {
      const key = edgeKey(selected, id);
      const exists = graph.edges.some((ed) => edgeKey(ed[0], ed[1]) === key);
      if (!exists) {
        onChange({ vertices: graph.vertices, edges: [...graph.edges, [selected, id]] });
      }
      setSelected(null);
    }
  }

  function handleVertexRightClick(e, id) {
    e.preventDefault();
    e.stopPropagation();
    const newPos = { ...positions };
    delete newPos[id];
    onPositionsChange(newPos);
    setSelected(null);
    onChange({
      vertices: graph.vertices.filter((v) => v !== id),
      edges: graph.edges.filter((ed) => ed[0] !== id && ed[1] !== id),
    });
  }

  function handleEdgeRightClick(e, u, v) {
    e.preventDefault();
    e.stopPropagation();
    const key = edgeKey(u, v);
    onChange({
      vertices: graph.vertices,
      edges: graph.edges.filter((ed) => edgeKey(ed[0], ed[1]) !== key),
    });
  }

  function handleVertexMouseDown(e, id) {
    if (e.button !== 0) return;
    e.stopPropagation();
    const pt = svgPoint(e);
    const px = pixPos[id];
    if (!px) return;
    setDragging({ id, ox: pt.x - px.x, oy: pt.y - px.y });
  }

  function handleMouseMove(e) {
    if (!dragging) return;
    const pt = svgPoint(e);
    const x = Math.max(R, Math.min(W - R, pt.x - dragging.ox));
    const y = Math.max(R, Math.min(H - R, pt.y - dragging.oy));
    onPositionsChange({ ...positions, [dragging.id]: { x: x / W, y: y / H } });
  }

  function handleMouseUp() {
    setDragging(null);
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      style={{ aspectRatio: `${W}/${H}` }}
      className="graph-editor"
      onClick={handleSvgClick}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onContextMenu={(e) => e.preventDefault()}
    >
      {graph.edges.map(([u, v]) => {
        const pu = pixPos[u];
        const pv = pixPos[v];
        if (!pu || !pv) return null;
        return (
          <line
            key={edgeKey(u, v)}
            x1={pu.x} y1={pu.y}
            x2={pv.x} y2={pv.y}
            stroke="#475569"
            strokeWidth={3}
            strokeLinecap="round"
            style={{ cursor: "pointer" }}
            onContextMenu={(e) => handleEdgeRightClick(e, u, v)}
          />
        );
      })}

      {graph.vertices.map((id) => {
        const p = pixPos[id];
        if (!p) return null;
        const isSel = selected === id;
        return (
          <g
            key={id}
            style={{ cursor: dragging?.id === id ? "grabbing" : "grab" }}
            onClick={(e) => handleVertexClick(e, id)}
            onContextMenu={(e) => handleVertexRightClick(e, id)}
            onMouseDown={(e) => handleVertexMouseDown(e, id)}
          >
            <circle
              cx={p.x} cy={p.y} r={R}
              fill={isSel ? "#3b82f6" : "#1e293b"}
              stroke={isSel ? "#93c5fd" : "#64748b"}
              strokeWidth={2}
            />
            <text
              x={p.x} y={p.y}
              textAnchor="middle" dominantBaseline="central"
              fill="white" fontSize={13} fontWeight="bold"
              style={{ userSelect: "none", pointerEvents: "none" }}
            >
              {id}
            </text>
          </g>
        );
      })}

      {selected !== null && pixPos[selected] && (
        <circle
          cx={pixPos[selected].x}
          cy={pixPos[selected].y}
          r={R + 5}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
          strokeDasharray="4 3"
          style={{ pointerEvents: "none" }}
        />
      )}
    </svg>
  );
}
