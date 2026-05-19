/**
 * Displays the FRW period P(γ, φ): one image per cut tubing of γ,
 * each showing φ's decorated graph with the tubing's tube circles superimposed.
 * Also exports PhiPhysDisplay for the φphys definition box.
 */
import { useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { PeriodSVG } from "./PeriodSum";
import { svgDataUri } from "./graphUtils";

function renderTex(tex, displayMode = false) {
  try { return katex.renderToString(tex, { displayMode, throwOnError: false }); }
  catch { return tex; }
}

function periodTitleTex(physicalContour, physicalForm) {
  const g = physicalContour ? "\\mathcal{G}" : "\\mathfrak{g}";
  const h = physicalForm    ? "\\mathcal{G}" : "\\mathfrak{h}";
  return `P_{${g}${h}} = \\int_{\\gamma_{${g}}} u_{\\mathcal{G}}\\;\\varphi_{${h}}`;
}

function PeriodTitle({ physicalContour, physicalForm }) {
  const html = renderTex(periodTitleTex(physicalContour, physicalForm));
  return <>FRW period: <span dangerouslySetInnerHTML={{ __html: html }} /></>;
}

function ScrollLatex({ terms }) {
  if (!Array.isArray(terms) || terms.length === 0) return null;
  return (
    <>
      {terms.map((tex, i) => {
        try {
          const html = katex.renderToString(tex, { displayMode: true, throwOnError: false });
          return (
            <div key={i} style={{ marginTop: i > 0 ? "0.5rem" : 0 }}
                 dangerouslySetInnerHTML={{ __html: html }} />
          );
        } catch {
          return <pre key={i} style={{ fontSize: "0.8rem", whiteSpace: "pre-wrap" }}>{tex}</pre>;
        }
      })}
    </>
  );
}

const PHI_TEX = katex.renderToString("\\varphi", { throwOnError: false });

function PhiTermSVG({ svg, latex }) {
  const [showLatex, setShowLatex] = useState(false);
  const hasLatex = typeof latex === "string" && latex.length > 0;
  const toggle = () => hasLatex && setShowLatex((v) => !v);
  const dataUri = svgDataUri(svg);

  if (showLatex && hasLatex) {
    let inner;
    try {
      const html = katex.renderToString(latex, { displayMode: true, throwOnError: false });
      inner = <span dangerouslySetInnerHTML={{ __html: html }} />;
    } catch {
      inner = <span>{latex}</span>;
    }
    return (
      <span
        className="period-sum-hover"
        onClick={toggle}
        title="Click to show graphic"
        style={{ display: "inline-flex", alignItems: "center", cursor: "pointer" }}
      >
        {inner}
      </span>
    );
  }

  return (
    <span
      className={hasLatex ? "period-sum-hover" : undefined}
      onClick={toggle}
      title={hasLatex ? "Click to show LaTeX" : undefined}
      style={{ display: "inline-flex", alignItems: "flex-end", cursor: hasLatex ? "pointer" : "default" }}
    >
      <span dangerouslySetInnerHTML={{ __html: PHI_TEX }} />
      <img
        src={dataUri}
        style={{ width: 80, height: "auto", background: "white", display: "block", marginBottom: "-4px" }}
        alt="φ term"
      />
    </span>
  );
}

export function PhiPhysDisplay({ result }) {
  const { graph_svg, terms } = result;
  const hasGraphSVG = typeof graph_svg === "string" && graph_svg.length > 0;
  const hasTerms = Array.isArray(terms) && terms.length > 0;
  return (
    <div>
      <div className="coaction-header">
        <h2><span dangerouslySetInnerHTML={{ __html: renderTex("\\varphi_{\\mathcal{G}}") }} /></h2>
        <span className="term-count">{hasTerms ? terms.length : 0} terms</span>
        <span className="section-note">(click term to toggle LaTeX)</span>
      </div>
      <div className="tubings-display" style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        {hasGraphSVG && (
          <img
            src={svgDataUri(graph_svg)}
            style={{ width: 200, height: "auto", background: "white" }}
            alt="φphys graph"
          />
        )}
        {hasTerms && (
          <>
            <span style={{ fontSize: "1.1rem", fontFamily: "Georgia, serif" }}> := </span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.25rem", flexWrap: "wrap" }}>
              {terms.map((t, i) => (
                <span key={i} style={{ display: "contents" }}>
                  {(i > 0 || t.sign < 0) && (
                    <span className="period-arrow">{t.sign < 0 ? "−" : "+"}</span>
                  )}
                  <PhiTermSVG svg={t.svg} latex={t.latex} />
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function TubingsDisplay({ result, periodLatex, periodSigns, physicalContour, pphysResult, physicalForm, pgphysResult, graphSvg, periodNode }) {
  const [expanded, setExpanded] = useState(false);

  // Both physical contour and physical form: P(γ_phys, φ_phys) = $graphPlot
  if (physicalContour && physicalForm) {
    if (!graphSvg) return null;
    return (
      <div>
        <div className="coaction-header">
          <h2><PeriodTitle physicalContour={physicalContour} physicalForm={physicalForm} /> <span className="section-note">(physical contour · physical form)</span></h2>
        </div>
        <div className="tubings-display">
          <PeriodSVG svg={graphSvg} size={174} />
        </div>
      </div>
    );
  }

  // Physical form mode: P(γ, φphys) — tube circles overlaid on bare graph
  if (physicalForm && pgphysResult) {
    const { period_svgs, period_signs, period_latex } = pgphysResult;
    const svgList = Array.isArray(period_svgs) ? period_svgs : [];
    const hasLatex = Array.isArray(period_latex) && period_latex.length > 0;
    if (svgList.length === 0) return (
      <div>
        <div className="coaction-header">
          <h2><PeriodTitle physicalContour={physicalContour} physicalForm={physicalForm} /> <span className="section-note">(physical form)</span></h2>
        </div>
        <div className="tubings-display">
          <div className="empty-state" style={{ fontFamily: "Georgia, serif", fontSize: "1.1rem" }}>P(γ, φ<sub>phys</sub>) = 0</div>
        </div>
      </div>
    );
    return (
      <div>
        <div className="coaction-header">
          <h2><PeriodTitle physicalContour={physicalContour} physicalForm={physicalForm} /> <span className="section-note">(click graphic to show LaTeX)</span></h2>
          <span className="term-count">physical form · {svgList.length} tubing{svgList.length !== 1 ? "s" : ""}</span>
        </div>
        <div className="tubings-display">
          <div
            className={hasLatex ? "period-sum-hover" : undefined}
            onClick={() => hasLatex && setExpanded((v) => !v)}
            title={hasLatex ? (expanded ? "Click to show graphic" : "Click to show integrand") : undefined}
          >
            {expanded && hasLatex ? (
              <ScrollLatex terms={period_latex} />
            ) : (
              <div className="tubings-grid">
                {svgList.length > 1 && <span className="period-arrow">(</span>}
                {svgList.map((svg, i) => {
                  const sign = Array.isArray(period_signs) && period_signs[i] !== undefined ? period_signs[i] : 1;
                  return (
                    <span key={i} style={{ display: "contents" }}>
                      {(i > 0 || sign < 0) && (
                        <span className="period-arrow">{sign < 0 ? "−" : "+"}</span>
                      )}
                      <PeriodSVG svg={svg} size={174} />
                    </span>
                  );
                })}
                {svgList.length > 1 && <span className="period-arrow">)</span>}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Physical contour mode
  if (physicalContour) {
    if (!pphysResult) return null;
    const { svg, latex } = pphysResult;
    const hasLatex = Array.isArray(latex) && latex.length > 0;
    const hasSVG = typeof svg === "string" && svg.length > 0;
    return (
      <div>
        <div className="coaction-header">
          <h2><PeriodTitle physicalContour={physicalContour} physicalForm={physicalForm} /> <span className="section-note">(click graphic to show LaTeX)</span></h2>
          <span className="term-count">physical contour</span>
        </div>
        <div className="tubings-display">
          <div
            className={hasLatex ? "period-sum-hover" : undefined}
            onClick={() => hasLatex && setExpanded((v) => !v)}
            title={hasLatex ? (expanded ? "Click to show graphic" : "Click to show integrand") : undefined}
          >
            {expanded && hasLatex ? (
              <ScrollLatex terms={latex} />
            ) : hasSVG ? (
              <PeriodSVG svg={svg} size={174} />
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  // Normal cut-tubing mode
  if (!result || !Array.isArray(result.cut_tubings)) return null;
  const { cut_tubings, n_regions, period_svgs } = result;

  const isZero = !Array.isArray(period_svgs) || period_svgs.length === 0;
  if (isZero && (!Array.isArray(period_svgs))) return null;

  const hasExpandable = (Array.isArray(periodLatex) && periodLatex.length > 0) || periodNode != null;
  const svgList = Array.isArray(period_svgs) ? period_svgs : [];

  return (
    <div>
      <div className="coaction-header">
        <h2><PeriodTitle physicalContour={physicalContour} physicalForm={physicalForm} /> <span className="section-note">(click graphic to show LaTeX)</span></h2>
        {!isZero && (
          <span className="term-count">
            {cut_tubings.length} tubing{cut_tubings.length !== 1 ? "s" : ""}
            {" · "}
            {n_regions} region{n_regions !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="tubings-display">
        {isZero ? (
          <div className="empty-state" style={{ fontFamily: "Georgia, serif", fontSize: "1.1rem" }}>
            P(γ, φ) = 0
          </div>
        ) : (
          <div
            className={hasExpandable ? "period-sum-hover" : undefined}
            onClick={() => hasExpandable && setExpanded((v) => !v)}
            title={hasExpandable ? (expanded ? "Click to show graphic" : "Click to show integrand") : undefined}
          >
            {expanded && hasExpandable ? (
              periodNode != null ? periodNode : <ScrollLatex terms={periodLatex} />
            ) : (
              <div className="tubings-grid">
                {svgList.length > 1 && <span className="period-arrow">(</span>}
                {svgList.map((svg, i) => {
                  const sign = Array.isArray(periodSigns) && periodSigns[i] !== undefined ? periodSigns[i] : 1;
                  return (
                    <span key={i} style={{ display: "contents" }}>
                      {(i > 0 || sign < 0) && (
                        <span className="period-arrow">{sign < 0 ? "−" : "+"}</span>
                      )}
                      <PeriodSVG svg={svg} size={174} />
                    </span>
                  );
                })}
                {svgList.length > 1 && <span className="period-arrow">)</span>}
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
