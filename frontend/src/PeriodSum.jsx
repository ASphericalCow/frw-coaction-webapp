/**
 * Shared period-rendering primitives used by CoactionDisplay, AnalyticStructureDisplay,
 * and TubingsDisplay.
 *
 * PeriodSum renders a single P(g,h) entry: SVG tube diagram(s) with click-to-toggle
 * LaTeX integrand (or arbitrary nodeContent), falling back to GraphMini when no SVG
 * is available.
 */
import { useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import GraphMini from "./GraphMini";
import { svgDataUri } from "./graphUtils";

/** ±1 net sign for a period entry: negative only when there is exactly one SVG and its sign is −1. */
export function periodNetSign(svgs, signs) {
  if (!svgs || svgs.length !== 1) return 1;
  return Array.isArray(signs) && signs[0] < 0 ? -1 : 1;
}

/**
 * Shared titled + paginated section used by CoactionDisplay and AnalyticStructureDisplay.
 *
 * Props:
 *   title      — section heading string
 *   termCount  — number shown in the "N terms" badge (defaults to terms.length)
 *   terms      — full array of data items
 *   renderTerm — (term, index) => JSX — renders one row
 *   note       — optional string shown in the header
 *   className  — wrapper class (default "result-section")
 */
export function ResultSection({ title, termCount, terms, renderTerm, note, className = "result-section" }) {
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  const pageTerms = terms.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(terms.length / PAGE_SIZE);
  return (
    <div className={className}>
      <div className="coaction-header">
        <h2>{title}</h2>
        <span className="term-count">{termCount ?? terms.length} terms</span>
        {note && <span className="section-note">{note}</span>}
      </div>
      {terms.length === 0 && (
        <div className="empty-state">{title} = 0</div>
      )}
      <div className="terms-box">
        <div className="terms-grid">
          {pageTerms.map((t, i) => renderTerm(t, i))}
        </div>
      </div>
      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>◀</button>
          <span>{page + 1} / {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>▶</button>
        </div>
      )}
    </div>
  );
}

export function svgSize(nVerts) {
  return Math.max(128, Math.min(208, 93 + nVerts * 23));
}

export function LatexTerms({ terms }) {
  if (!Array.isArray(terms) || terms.length === 0) return null;
  return (
    <div>
      {terms.map((tex, i) => {
        try {
          const html = katex.renderToString(tex, { displayMode: true, throwOnError: false });
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
              {i > 0 && <span style={{ fontSize: "1.1rem", color: "#64748b" }}>+</span>}
              <span dangerouslySetInnerHTML={{ __html: html }} />
            </div>
          );
        } catch {
          return <div key={i}>{tex}</div>;
        }
      })}
    </div>
  );
}

export function PeriodSVG({ svg, size }) {
  const dataUri = svgDataUri(svg);
  return (
    <img
      src={dataUri}
      style={{ width: size, height: "auto", display: "block", background: "white" }}
      alt="period"
    />
  );
}

/**
 * Renders one period P(g,h) entry.
 *
 * Props:
 *   svgs        — array of SVG strings (one per cut tubing)
 *   signs       — array of ±1 signs matching svgs
 *   latex       — array of LaTeX strings shown on click (when nodeContent is absent)
 *   nodeContent — optional JSX shown on click instead of latex
 *   dec         — decoration list (GraphMini fallback)
 *   vertices, edges, tubeSet, tubes, positions — GraphMini fallback props
 *   nVerts      — number of vertices (controls SVG display size)
 */
export default function PeriodSum({ svgs, signs, latex, nodeContent, dec, vertices, edges, tubeSet, tubes, positions, nVerts }) {
  const [expanded, setExpanded] = useState(false);
  const hasLatex = Array.isArray(latex) && latex.length > 0;
  const hasContent = nodeContent != null || hasLatex;
  const pSize = svgSize(nVerts);

  if (svgs && svgs.length > 0) {
    const multi = svgs.length > 1;
    return (
      <div
        className={hasContent ? "period-sum-hover" : undefined}
        onClick={() => hasContent && setExpanded((v) => !v)}
        title={hasContent ? (expanded ? "Click to show graphic" : "Click to show integrand") : undefined}
      >
        {expanded && hasContent ? (
          nodeContent != null ? nodeContent : <LatexTerms terms={latex} />
        ) : (
          <div className="period-sum">
            {multi && <span className="period-brace">(</span>}
            {svgs.map((svg, i) => {
              const sign = Array.isArray(signs) && signs[i] !== undefined ? signs[i] : 1;
              return (
                <span key={i} className="period-sum-item">
                  {(i > 0 || (sign < 0 && multi)) && (
                    <span className="period-plus">{sign < 0 ? "−" : "+"}</span>
                  )}
                  <PeriodSVG svg={svg} size={pSize} />
                </span>
              );
            })}
            {multi && <span className="period-brace">)</span>}
          </div>
        )}
      </div>
    );
  }

  return (
    <GraphMini
      dec={dec}
      vertices={vertices}
      edges={edges}
      tubeIndices={tubeSet ?? []}
      tubes={tubes}
      positions={positions}
    />
  );
}
