import { useState, useMemo, useEffect, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import GraphEditor from "./GraphEditor";
import DecorationEditor from "./DecorationEditor";
import CoactionDisplay from "./CoactionDisplay";
import TubingsDisplay, { PhiPhysDisplay } from "./TubingsDisplay";
import AnalyticStructureDisplay from "./AnalyticStructureDisplay";
import PgPhysLatex from "./PgPhysLatex";
import { adecQ } from "./adecQ";
import { edgeKey, svgDataUri } from "./graphUtils";
import "./App.css";

/** Safe KaTeX render: returns HTML string; falls back to raw tex on error. */
function renderTex(tex, displayMode = true) {
  try { return katex.renderToString(tex, { displayMode, throwOnError: false }); }
  catch { return tex; }
}

/** P subscript: \mathcal{G} for physical contour/form, no comma needed. */
function pSub(physContour, physForm) {
  const g = physContour ? "\\mathcal{G}" : "\\mathfrak{g}";
  const h = physForm    ? "\\mathcal{G}" : "\\mathfrak{h}";
  return `${g}${h}`;
}

function SvgThumb({ svg, size = 80, label }) {
  const dataUri = svgDataUri(svg);
  return (
    <div className="debug-region-item">
      <img src={dataUri} alt={label ?? ""} style={{ width: size, height: "auto", background: "white" }} />
      {label && <span className="debug-region-verts">{label}</span>}
    </div>
  );
}

function TubePictureIndex({ tubeSvgs, tubeOrder }) {
  if (!tubeSvgs || tubeSvgs.length === 0) return null;
  return (
    <div className="debug-dec-section">
      <span className="debug-section-title">tubes</span>
      <div className="debug-region-svgs">
        {tubeSvgs.map((svg, i) => (
          <div key={i} className="debug-region-item">
            <img
              src={svgDataUri(svg)}
              alt={`tube ${i + 1}`}
              style={{ width: 80, height: "auto", background: "white" }}
            />
            <span className="debug-region-verts">{i + 1}</span>
          </div>
        ))}
      </div>
      {tubeOrder && (
        <div className="debug-tube-order-row">
          <span className="debug-section-title">order</span>
          <span className="debug-tube-order-list">{tubeOrder.join("  ")}</span>
        </div>
      )}
    </div>
  );
}

function DebugDecRow({ regions, cutSvgs, cutTubings, label }) {
  const hasRegions = regions && regions.length > 0;
  const hasCuts = cutSvgs && cutSvgs.length > 0;
  if (!hasRegions && !hasCuts) return null;
  return (
    <div className="debug-dec-block">
      <span className="debug-region-label">{label}</span>
      <div className="debug-dec-sections">
        {hasRegions && (
          <div className="debug-dec-section">
            <span className="debug-section-title">regions</span>
            <div className="debug-region-svgs">
              {regions.map((r, i) => (
                <SvgThumb key={i} svg={r.svg} label={"{" + r.verts.join(",") + "}"} />
              ))}
            </div>
          </div>
        )}
        {hasCuts && (
          <div className="debug-dec-section">
            <span className="debug-section-title">cut tubings</span>
            <div className="debug-region-svgs">
              {cutSvgs.map((svg, i) => {
                const indices = cutTubings?.[i];
                const idxLabel = indices ? "{" + indices.map((x) => x + 1).join(",") + "}" : null;
                return <SvgThumb key={i} svg={svg} size={90} label={idxLabel} />;
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function DebugDisplay({ result }) {
  if (!result) return null;
  return (
    <div className="result-section">
      <div className="coaction-header">
        <h2>Debug</h2>
      </div>
      <div className="debug-dec-block">
        <span className="debug-region-label" />
        <TubePictureIndex tubeSvgs={result.tube_svgs} tubeOrder={result.tube_order} />
      </div>
      <DebugDecRow
        regions={result.g_regions}
        cutSvgs={result.g_cut_svgs}
        cutTubings={result.g_cut_tubings}
        label="γ"
      />
      {result.compatible_tube_indices && result.tube_polys && (
        <div className="debug-dec-block">
          <span className="debug-region-label">τ</span>
          <div className="debug-dec-section">
            <span className="debug-section-title">γ tube polynomials</span>
            <div className="debug-tube-poly-list">
              {result.compatible_tube_indices.map((idx) => {
                const poly = result.tube_polys[String(idx)];
                if (!poly) return null;
                const tex = `\\tau_{${idx + 1}} = ${poly.poly_latex}`;
                return (
                  <div key={idx} className="debug-tube-poly-row">
                    <span dangerouslySetInnerHTML={{ __html: renderTex(tex, false) }} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {result.cut_data && result.cut_data.length > 0 && (
        <div className="debug-dec-block">
          <span className="debug-region-label">x</span>
          <div className="debug-dec-section">
            <span className="debug-section-title">cut values x&#x2090; = min(R)</span>
            <div className="debug-tube-poly-list">
              {result.cut_data.map((cd, ci) => {
                const idxLabel = "{" + cd.cut_tubing.map(x => x + 1).join(",") + "}";
                const entries = Object.entries(cd.x_values);
                return (
                  <div key={ci} className="debug-cutval-block">
                    <span className="debug-section-title">{idxLabel}</span>
                    {entries.length === 0
                      ? <span className="debug-cgh-zero">no x variables fixed</span>
                      : entries.map(([v, expr]) => {
                          const tex = `x_{${v}} = ${expr}`;
                          return (
                            <div key={v} className="debug-tube-poly-row">
                              <span dangerouslySetInnerHTML={{ __html: renderTex(tex, false) }} />
                            </div>
                          );
                        })
                    }
                    {cd.twist_latex && (
                      <div className="debug-tube-poly-row" dangerouslySetInnerHTML={{ __html: renderTex(cd.twist_latex) }} />
                    )}
                    {cd.region_latex != null && (
                      cd.region_latex.length === 0
                        ? <span className="debug-cgh-zero" style={{ marginTop: "0.2rem" }}>no contour (all x fixed)</span>
                        : <div className="debug-tube-poly-row" dangerouslySetInnerHTML={{ __html: renderTex(`\\Delta_{\\mathfrak{g}} = \\left\\{${cd.region_latex.join(",\\,")}\\right\\}`) }} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {result.h_regions && (
        <DebugDecRow
          regions={result.h_regions}
          cutSvgs={result.h_cut_svgs}
          cutTubings={result.h_cut_tubings}
          label="φ"
        />
      )}
      {result.cgh_pairs != null && (
        <div className="debug-dec-block">
          <span className="debug-region-label">Cgh</span>
          <div className="debug-dec-section">
            {result.cgh_pairs.length === 0 ? (
              <span className="debug-cgh-zero">P(γ,φ) = 0</span>
            ) : (
              <>
                <span className="debug-section-title">{result.cgh_pairs.length} pairs</span>
                <div className="debug-cgh-list">
                  {result.cgh_pairs.map((pair, i) => {
                    const g = pair.g ?? pair[0];
                    const h = pair.h ?? pair[1];
                    const gAmSeq = pair.g_am_seq;
                    const hAmSeq = pair.h_am_seq;
                    const gRegMin = pair.g_region_min;
                    const hRegMin = pair.h_region_min;
                    const gSign = pair.g_sign;
                    const hSign = pair.h_sign;
                    const sign = pair.sign;
                    const fmt = (seq, rmin) => rmin
                      ? rmin.map((v, j) => `v${v}→t${(seq[j] ?? 0) + 1}`).join(", ")
                      : null;
                    const signChar = s => s != null ? (s > 0 ? "+1" : "−1") : null;
                    return (
                      <div key={i} className="debug-cgh-pair" style={{ display: "flex", flexDirection: "column", gap: "0.1rem" }}>
                        <span>
                          {"{" + g.map(x => x + 1).join(",") + "}"}&thinsp;⊆&thinsp;{"{" + h.map(x => x + 1).join(",") + "}"}
                          <span style={{ marginLeft: "0.5rem", color: "#2563eb", fontWeight: 600 }}>
                            sign = {signChar(gSign)} × {signChar(hSign)} = {signChar(sign)}
                          </span>
                        </span>
                        {gAmSeq && <span style={{ color: "#94a3b8", fontSize: "0.78rem" }}>γ angleMap: [{fmt(gAmSeq, gRegMin)}]</span>}
                        {hAmSeq && <span style={{ color: "#94a3b8", fontSize: "0.78rem" }}>φ angleMap: [{fmt(hAmSeq, hRegMin)}]</span>}
                        {pair.form_dlogs != null && (() => {
                          const fs = pair.form_sign;
                          const fsStr = fs != null ? (fs > 0 ? "" : "-") : "";
                          const part1 = (pair.form_dlogs ?? []).map(
                            d => `\\mathrm{dlog}\\!\\left(${d.poly_latex}\\right)`
                          );
                          const part2 = (pair.form_part2 ?? []).map(
                            d => `\\mathrm{dlog}\\!\\left(\\frac{${d.num_latex}}{${d.den_latex}}\\right)`
                          );
                          const allTerms = [...part1, ...part2];
                          const inner = allTerms.length > 0
                            ? allTerms.join(" \\wedge ")
                            : "1";
                          const tex = `${fsStr}${inner}`;
                          return <div dangerouslySetInnerHTML={{ __html: renderTex(tex) }} />;
                        })()}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {result.period_integral_latex != null && (
        <PeriodIntegralDisplay
          integralLatex={result.period_integral_latex}
          twistConsistent={result.twist_consistent}
          regionConsistent={result.region_consistent}
        />
      )}
    </div>
  );
}


function PeriodIntegralDisplay({ integralLatex, twistConsistent, regionConsistent }) {
  const integralTex = integralLatex ?? "";

  const html = renderTex(integralTex);

  return (
    <div className="debug-dec-block">
      <span className="debug-region-label">P</span>
      <div className="debug-dec-section">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
          <span className="debug-section-title">P(γ,φ) integral</span>
          {!twistConsistent && (
            <span className="badge badge-err" title="Twist differs across γ cut-tubings">twist !</span>
          )}
          {!regionConsistent && (
            <span className="badge badge-err" title="Γ differs across γ cut-tubings">Γ !</span>
          )}
          {twistConsistent && regionConsistent && (
            <span className="badge badge-ok">consistent</span>
          )}
        </div>
        <div dangerouslySetInnerHTML={{ __html: html }} />
      </div>
    </div>
  );
}

function ZonotopesDisplay({ result }) {
  const { n_adec, n_zono, zono_sizes } = result;
  return (
    <div className="zonotopes-display">
      <span className="zono-stat">
        |aDecGraphs| = <strong>{n_adec}</strong>
      </span>
      <span className="zono-sep">·</span>
      <span className="zono-stat">
        zonotopes = <strong>{n_zono}</strong>
      </span>
      <span className="zono-sep">·</span>
      <span className="zono-stat zono-sizes">
        |zonotope vertices| = &#123;{zono_sizes.join(", ")}&#125;
      </span>
    </div>
  );
}

const COACTION_FORMULA = String.raw`\Delta P_{\mathfrak{gh}} = \sum_{\mathfrak{f}} \frac{1}{\langle \check{\varphi}_{\mathfrak{f}} \mid \varphi_{\mathfrak{f}} \rangle}\, P_{\mathfrak{gf}} \otimes P_{\mathfrak{fh}}`;
const COACTION_PHYS_CONTOUR_FORMULA = String.raw`\Delta P_{\mathcal{G}\mathfrak{h}} = \sum_{\mathfrak{f}} \frac{1}{\langle \check{\varphi}_{\mathfrak{f}} \mid \varphi_{\mathfrak{f}} \rangle}\, P_{\mathcal{G}\mathfrak{f}} \otimes P_{\mathfrak{fh}}`;
const COACTION_PHYS_FORMULA = String.raw`\Delta P_{\mathfrak{g}\mathcal{G}} = \sum_{\mathfrak{f}} \frac{1}{\langle \check{\varphi}_{\mathfrak{f}} \mid \varphi_{\mathfrak{f}} \rangle}\, P_{\mathfrak{gf}} \otimes P_{\mathfrak{f}\mathcal{G}}`;
const COACTION_PHYS_BOTH_FORMULA = String.raw`\Delta P_{\mathcal{G}\mathcal{G}} = \sum_{\mathfrak{f}} \frac{1}{\langle \check{\varphi}_{\mathfrak{f}} \mid \varphi_{\mathfrak{f}} \rangle}\, P_{\mathcal{G}\mathfrak{f}} \otimes P_{\mathfrak{f}\mathcal{G}}`;
const DP_PHYS_FORMULA = String.raw`\mathrm{d}P_{\mathfrak{g}\mathcal{G}} = \sum_{\mathfrak{f}} \omega_{\mathfrak{f}}^{\mathcal{G}}\, P_{\mathfrak{gf}}`;

function LatexFormula({ tex }) {
  const html = katex.renderToString(tex, { displayMode: true, throwOnError: false });
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

const EXAMPLES = [
  {
    name: "2-chain",
    vertices: [1, 2],
    edges: [[1, 2]],
    g_dec: { "1-2": "pinched" },
    h_dec: { "1-2": "oriented_fwd" },
  },
  {
    name: "3-chain",
    vertices: [1, 2, 3],
    edges: [[1, 2], [2, 3]],
    g_dec: { "1-2": "pinched", "2-3": "pinched" },
    h_dec: { "1-2": "oriented_fwd", "2-3": "oriented_fwd" },
  },
  {
    name: "4-chain",
    vertices: [1, 2, 3, 4],
    edges: [[1, 2], [2, 3], [3, 4]],
    g_dec: { "1-2": "pinched", "2-3": "pinched", "3-4": "pinched" },
    h_dec: { "1-2": "oriented_fwd", "2-3": "oriented_fwd", "3-4": "oriented_fwd" },
  },
  {
    name: "3-gon",
    vertices: [1, 2, 3],
    edges: [[1, 2], [2, 3], [1, 3]],
    g_dec: { "1-2": "pinched", "2-3": "pinched", "1-3": "pinched" },
    h_dec: { "1-2": "oriented_fwd", "2-3": "oriented_fwd", "1-3": "oriented_fwd" },
  },
  {
    name: "4-gon",
    vertices: [1, 2, 3, 4],
    edges: [[1, 2], [2, 3], [3, 4], [1, 4]],
    g_dec: { "1-2": "pinched", "2-3": "pinched", "3-4": "pinched", "1-4": "pinched" },
    h_dec: { "1-2": "oriented_fwd", "2-3": "oriented_fwd", "3-4": "oriented_fwd", "1-4": "oriented_fwd" },
  },
];

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

const EDITOR_W = 330, EDITOR_H = 220;

function normalizedCircleLayout(vertices) {
  const n = vertices.length;
  const cx = EDITOR_W / 2, cy = EDITOR_H / 2;
  const r = n <= 1 ? 0 : Math.min(EDITOR_W, EDITOR_H) * 0.35;
  const pos = {};
  vertices.forEach((v, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[v] = {
      x: (cx + r * Math.cos(angle)) / EDITOR_W,
      y: (cy + r * Math.sin(angle)) / EDITOR_H,
    };
  });
  return pos;
}

function pathOrder(vertices, edges) {
  const n = vertices.length;
  if (n <= 1) return [...vertices];
  if (edges.length !== n - 1) return null;
  const adj = {};
  vertices.forEach((v) => { adj[v] = []; });
  edges.forEach(([u, v]) => { adj[u].push(v); adj[v].push(u); });
  if (vertices.some((v) => adj[v].length > 2)) return null;
  const endpoints = vertices.filter((v) => adj[v].length === 1);
  if (endpoints.length === 0) return null; // cycle
  const start = Math.min(...endpoints);
  const path = [start];
  const visited = new Set([start]);
  while (true) {
    const curr = path[path.length - 1];
    const nxt = adj[curr].filter((v) => !visited.has(v));
    if (nxt.length === 0) break;
    path.push(nxt[0]);
    visited.add(nxt[0]);
  }
  return path.length === n ? path : null;
}

function normalizedHorizontalLayout(vertices, edges) {
  const order = pathOrder(vertices, edges) || [...vertices].sort((a, b) => a - b);
  const n = order.length;
  const pos = {};
  order.forEach((v, i) => {
    pos[v] = { x: (i + 1) / (n + 1), y: 0.5 };
  });
  return pos;
}

function autoLayout(vertices, edges) {
  return pathOrder(vertices, edges)
    ? normalizedHorizontalLayout(vertices, edges)
    : normalizedCircleLayout(vertices);
}

function positionsToArray(positions) {
  if (!positions) return undefined;
  const out = {};
  for (const [v, xy] of Object.entries(positions)) {
    out[v] = [xy.x, xy.y];
  }
  return out;
}


function initDec(edges) {
  const dec = {};
  edges.forEach(([u, v]) => { dec[edgeKey(u, v)] = "oriented_fwd"; });
  return dec;
}

function syncDec(dec, newEdges) {
  const next = {};
  newEdges.forEach(([u, v]) => {
    const k = edgeKey(u, v);
    next[k] = dec[k] || "oriented_fwd";
  });
  return next;
}

function decToList(dec, edges) {
  return edges.map(([u, v]) => ({
    edge: [u, v],
    type: dec[edgeKey(u, v)] || "oriented_fwd",
  }));
}

export default function App() {
  const [graph, setGraph] = useState({ vertices: [1, 2], edges: [[1, 2]] });
  const [gDec, setGDec] = useState({ "1-2": "pinched" });
  const [hDec, setHDec] = useState({ "1-2": "oriented_fwd" });
  const [positions, setPositions] = useState(() => autoLayout([1, 2], [[1, 2]]));
  const [coactionResult, setCoactionResult] = useState(null);
  const [dpResult, setDpResult] = useState(null);
  const [discpResult, setDiscpResult] = useState(null);
  const [discpPhysResult, setDiscpPhysResult] = useState(null);
  const [tubingsResult, setTubingsResult] = useState(null);
  const [zonotopesResult, setZonotopesResult] = useState(null);
  const [debugResult, setDebugResult] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  const [physContour, setPhysContour] = useState(false);
  const [pphysResult, setPphysResult] = useState(null);
  const [physicalForm, setPhysicalForm] = useState(false);
  const [phiPhysResult, setPhiPhysResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resultsStale, setResultsStale] = useState(false);
  const firstRender = useRef(true);

  const gAcyclic = useMemo(() => adecQ(graph.vertices, graph.edges, gDec), [graph, gDec]);
  const hAcyclic = useMemo(() => adecQ(graph.vertices, graph.edges, hDec), [graph, hDec]);

  // Auto-fetch zonotope info whenever graph changes
  const zotopesFetchId = useRef(0);
  useEffect(() => {
    if (graph.edges.length === 0) { setZonotopesResult(null); return; }
    const fetchId = ++zotopesFetchId.current;
    fetch(`${API}/zonotopes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vertices: graph.vertices, edges: graph.edges }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && fetchId === zotopesFetchId.current) setZonotopesResult(data); })
      .catch(() => {});
  }, [graph]);

  // Auto-fetch cut tubings for γ whenever γ or φ changes and γ is acyclic
  const tubingsFetchId = useRef(0);
  useEffect(() => {
    if (!gAcyclic || graph.edges.length === 0) { setTubingsResult(null); setDebugResult(null); return; }
    const fetchId = ++tubingsFetchId.current;
    const body = {
      vertices: graph.vertices,
      edges: graph.edges,
      dec: decToList(gDec, graph.edges),
      positions: positionsToArray(positions),
    };
    if (physicalForm) {
      body.h_dec = graph.edges.map(([u, v]) => ({ edge: [u, v], type: "solid" }));
    } else if (hAcyclic) {
      body.h_dec = decToList(hDec, graph.edges);
    }
    fetch(`${API}/tubings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data && Array.isArray(data.cut_tubings) && fetchId === tubingsFetchId.current) {
          setTubingsResult(data);
        }
      })
      .catch(() => {});

    // Fetch debug data for period internals
    fetch(`${API}/debug_period`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vertices: graph.vertices, edges: graph.edges, dec: decToList(gDec, graph.edges), h_dec: decToList(hDec, graph.edges), positions: positionsToArray(positions) }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && fetchId === tubingsFetchId.current) setDebugResult(data); })
      .catch(() => {});
  }, [graph, gDec, gAcyclic, hDec, hAcyclic, physicalForm, positions]);

  // Fetch P(γ_phys, φ) whenever physical contour is on and φ is acyclic
  const pphysFetchId = useRef(0);
  useEffect(() => {
    if (!physContour || !hAcyclic || graph.edges.length === 0) { setPphysResult(null); return; }
    const fetchId = ++pphysFetchId.current;
    fetch(`${API}/period_pphys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vertices: graph.vertices,
        edges: graph.edges,
        dec: [],
        h_dec: decToList(hDec, graph.edges),
        positions: positionsToArray(positions),
      }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && fetchId === pphysFetchId.current) setPphysResult(data); })
      .catch(() => {});
  }, [physContour, graph, hDec, hAcyclic, positions]);

  // Auto-fetch φ_phys decomposition whenever physicalForm is enabled
  const phiPhysFetchId = useRef(0);
  useEffect(() => {
    if (!physicalForm || graph.edges.length === 0) { setPhiPhysResult(null); return; }
    const fetchId = ++phiPhysFetchId.current;
    fetch(`${API}/phi_phys_form`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vertices: graph.vertices,
        edges: graph.edges,
        positions: positionsToArray(positions),
      }),
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && fetchId === phiPhysFetchId.current) setPhiPhysResult(data); })
      .catch(() => {});
  }, [physicalForm, graph, positions]);

  // Mark results stale whenever inputs change after the first render
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    setResultsStale(true);
  }, [graph, gDec, hDec, physContour, physicalForm]);

  function handleGraphChange(newGraph) {
    setGDec((prev) => syncDec(prev, newGraph.edges));
    setHDec((prev) => syncDec(prev, newGraph.edges));
    setGraph(newGraph);
    setPhysicalForm(false);
    setPhiPhysResult(null);
    setCoactionResult(null);
    setDpResult(null);
    setDiscpResult(null);
    setDiscpPhysResult(null);
    setZonotopesResult(null);
    setResultsStale(false);
    setError(null);
  }

  async function computeAnalyticStructure() {
    const needsGDec = !physContour;
    const needsHDec = !physicalForm;
    if ((needsGDec && !gAcyclic) || (needsHDec && !hAcyclic)) {
      setError("Both decorations must be acyclic before computing.");
      return;
    }
    setLoading(true);
    setError(null);
    setResultsStale(false);
    setCoactionResult(null);
    setDpResult(null);
    setDiscpResult(null);
    setDiscpPhysResult(null);

    const body = JSON.stringify({
      vertices: graph.vertices,
      edges: graph.edges,
      g_dec: decToList(gDec, graph.edges),
      h_dec: decToList(hDec, graph.edges),
      positions: positionsToArray(positions),
    });
    const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body };

    try {
      if (physContour && physicalForm) {
        // ΔP(phys, phys) only — no d, no disc
        const graphBody = JSON.stringify({
          vertices: graph.vertices,
          edges: graph.edges,
          positions: positionsToArray(positions),
        });
        const res = await fetch(`${API}/coaction_phys_phys`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: graphBody,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Server error");
        }
        setCoactionResult(await res.json());
      } else if (physicalForm) {
        // ΔP(g, φphys) + discP(g, φphys) — no dP
        const [coactionRes, discpPhysRes] = await Promise.all([
          fetch(`${API}/coaction_phys`, opts),
          fetch(`${API}/discp_phys`, opts),
        ]);
        if (!coactionRes.ok) {
          const err = await coactionRes.json();
          throw new Error(err.detail || "Server error");
        }
        setCoactionResult(await coactionRes.json());
        if (discpPhysRes.ok) {
          setDiscpPhysResult(await discpPhysRes.json());
        } else {
          const errText = await discpPhysRes.text().catch(() => "(no body)");
          console.error("discp_phys failed", discpPhysRes.status, errText);
          setError(`discP server error ${discpPhysRes.status}: ${errText}`);
        }
      } else {
        // Normal: ΔP, dP, discP
        const [coactionRes, dpRes, discpRes] = await Promise.all([
          fetch(`${API}/coaction`, opts),
          fetch(`${API}/differential`, opts),
          fetch(`${API}/discontinuity`, opts),
        ]);
        if (!coactionRes.ok) {
          const err = await coactionRes.json();
          throw new Error(err.detail || "Server error");
        }
        const [coactionData, dpData, discpData] = await Promise.all([
          coactionRes.json(),
          dpRes.ok ? dpRes.json() : null,
          discpRes.ok ? discpRes.json() : null,
        ]);
        setCoactionResult(coactionData);
        if (dpData) setDpResult(dpData);
        if (discpData) setDiscpResult(discpData);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function loadExample(ex) {
    const newGraph = { vertices: ex.vertices, edges: ex.edges };
    setGraph(newGraph);
    setGDec(ex.g_dec);
    setHDec(ex.h_dec);
    setPositions(autoLayout(ex.vertices, ex.edges));
    setPhysicalForm(false);
    setPhiPhysResult(null);
    setCoactionResult(null);
    setDpResult(null);
    setDiscpResult(null);
    setDiscpPhysResult(null);
    setError(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <p className="app-citation">Companion website for the FRW graphical coaction by A. McLeod, A. Pokraka, and L. Ren [<a href="https://arxiv.org/abs/2603.25703" target="_blank" rel="noreferrer">arXiv:2603.25703</a>]. Send comments to <a href="mailto:apokraka.physics@gmail.com">apokraka.physics@gmail.com</a>.</p>
        <h1>FRW Graphical Coaction</h1>
        <LatexFormula tex={
          physContour && physicalForm ? COACTION_PHYS_BOTH_FORMULA :
          physContour                 ? COACTION_PHYS_CONTOUR_FORMULA :
          physicalForm                ? COACTION_PHYS_FORMULA :
                                        COACTION_FORMULA
        } />
        <p className="app-instructions">
          Draw a graph (or choose an example below) and decorate{" "}
          <span dangerouslySetInnerHTML={{ __html: renderTex("\\gamma_{\\mathfrak{g}}", false) }} />
          {" "}and{" "}
          <span dangerouslySetInnerHTML={{ __html: renderTex("\\varphi_{\\mathfrak{h}}", false) }} />
          {" "}as acyclic minors, then click <em>Compute analytic structure</em>!
        </p>
      </header>

      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button key={ex.name} className="example-btn" onClick={() => loadExample(ex)}>
            {ex.name}
          </button>
        ))}
      </div>

      <div className="editors-row">
        <div className="editor-panel">
          <div className="dec-editor-header">
            <span className="dec-label">Truncated Feynman graph <span dangerouslySetInnerHTML={{ __html: renderTex("\\mathcal{G}", false) }} /></span>
          </div>
          <GraphEditor
            graph={graph}
            onChange={handleGraphChange}
            positions={positions}
            onPositionsChange={setPositions}
          />
          <div className="hint">
            <span>Click canvas → add vertex</span>
            <span>Click two vertices → add edge</span>
            <span>Right-click → delete</span>
            <span>Drag → reposition</span>
          </div>
        </div>

        <div className="editor-panel">
          <DecorationEditor
            graph={graph}
            decoration={gDec}
            onDecorationChange={setGDec}
            isAcyclic={graph.edges.length === 0 ? null : gAcyclic}
            label={<>Contour <span dangerouslySetInnerHTML={{ __html: renderTex("\\gamma_{\\mathfrak{g}}", false) }} /></>}
            positions={positions}
            blank={physContour}
            toggleLabel="Physical contour"
            toggleValue={physContour}
            onToggleChange={setPhysContour}
          />
        </div>

        <div className="editor-panel">
          <DecorationEditor
            graph={graph}
            decoration={hDec}
            onDecorationChange={setHDec}
            isAcyclic={graph.edges.length === 0 ? null : hAcyclic}
            label={<>Form <span dangerouslySetInnerHTML={{ __html: renderTex("\\varphi_{\\mathfrak{h}}", false) }} /></>}
            positions={positions}
            blank={physicalForm}
            toggleLabel="Physical form"
            toggleValue={physicalForm}
            onToggleChange={setPhysicalForm}
          />
        </div>
      </div>

      {tubingsResult && gAcyclic && (
        <div className="result-section">
          <TubingsDisplay
            result={tubingsResult}
            periodLatex={tubingsResult.period_latex ?? []}
            periodNode={
              physicalForm && tubingsResult?.period_signs?.length > 0
                ? <PgPhysLatex
                    periodSigns={tubingsResult.period_signs}
                    regionLatex={debugResult?.period_region_latex ?? []}
                    vertices={graph.vertices}
                    cutTubings={tubingsResult.cut_tubings}
                    tubes={tubingsResult.tubes}
                    tubeSvgs={debugResult?.tube_svgs ?? []}
                  />
                : undefined
            }
            periodSigns={tubingsResult?.period_signs ?? []}
            physicalContour={physContour}
            pphysResult={pphysResult}
            physicalForm={physicalForm}
            pgphysResult={null}
            graphSvg={null}
          />
        </div>
      )}

      {physicalForm && phiPhysResult && (
        <div className="result-section">
          <PhiPhysDisplay result={phiPhysResult} />
        </div>
      )}

      {/* Debug panel hidden from UI; toggle showDebug to restore */}

      {zonotopesResult && (
        <ZonotopesDisplay result={zonotopesResult} />
      )}

      <div className="compute-row">
        <button
          className="compute-btn"
          onClick={computeAnalyticStructure}
          disabled={loading || (!physContour && !gAcyclic) || (!physicalForm && !hAcyclic)}
        >
          {loading ? "Computing…" : "Compute analytic structure"}
        </button>
        {error && <div className="error">{error}</div>}
        {coactionResult && !resultsStale && (
          <div className="stats">
            <span>|aDecGraphs| = {coactionResult.adec_count}</span>
            <span>{coactionResult.terms.length} ΔP terms</span>
            <span>{coactionResult.elapsed_ms} ms</span>
          </div>
        )}
      </div>

      <div className="results-panel">
        {resultsStale && coactionResult && (
          <div className="empty-state">
            Inputs changed — click <em>Compute analytic structure</em> to refresh results.
          </div>
        )}
        {!resultsStale && coactionResult && (
          <CoactionDisplay
            result={coactionResult}
            positions={positions}
            title={<span dangerouslySetInnerHTML={{ __html: renderTex(`\\Delta P_{${pSub(physContour, physicalForm)}}`, false) }} />}
            physContour={physContour}
            physForm={physicalForm}
          />
        )}
        {!resultsStale && (physicalForm ? discpPhysResult : (dpResult || discpResult)) && (
          <AnalyticStructureDisplay
            dpResult={physicalForm ? null : dpResult}
            discpResult={physicalForm ? discpPhysResult : (physContour ? null : discpResult)}
            vertices={graph.vertices}
            edges={graph.edges}
            physContour={physContour}
            physForm={physicalForm}
            positions={positions}
            dpTitle={<span dangerouslySetInnerHTML={{ __html: renderTex(`\\mathrm{d}P_{${pSub(physContour, physicalForm)}}`, false) }} />}
            discpTitle={<span dangerouslySetInnerHTML={{ __html: renderTex(`\\mathrm{Disc}\\, P_{${pSub(physContour, physicalForm)}}`, false) }} />}
          />
        )}
        {!coactionResult && !loading && (
          <div className="empty-state">
            Decorate{" "}
            <span dangerouslySetInnerHTML={{ __html: renderTex("\\gamma_{\\mathfrak{g}}", false) }} />
            {" "}and{" "}
            <span dangerouslySetInnerHTML={{ __html: renderTex("\\varphi_{\\mathfrak{h}}", false) }} />
            {" "}as acyclic minors, then click <em>Compute analytic structure</em>!
          </div>
        )}
      </div>
    </div>
  );
}
