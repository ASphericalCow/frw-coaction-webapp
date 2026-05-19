/**
 * PgPhysLatex — standalone component for P(γ, φ_phys) formula display.
 *
 * Renders: ∫_Γ [ Σ_i sign_i · Res_{tube} ∘ … [ twist · φ_phys ] ]
 * Tube SVGs appear in Res subscripts when provided; falls back to t_{j+1}.
 *
 * Props:
 *   periodSigns  : number[]          — sign per cut tubing  (±1)
 *   regionLatex  : string[]          — Γ constraint strings  (empty → ℝⁿ₊)
 *   vertices     : number[]          — vertex ids (sorted)
 *   cutTubings   : number[][]        — cut tubings (indices into tubes array)
 *   tubes        : {verts, edges}[]  — tube objects from API
 *   tubeSvgs     : string[]          — one SVG string per global tube index
 */
import katex from "katex";
import "katex/dist/katex.min.css";
import { svgDataUri } from "./graphUtils";

export default function PgPhysLatex({ periodSigns, regionLatex, vertices, cutTubings, tubes, tubeSvgs }) {
  if (!periodSigns || periodSigns.length === 0) return null;

  const twistTex = vertices?.length > 0
    ? vertices.map(v => `x_{${v}}^{\\alpha_{${v}}}`).join("\\,")
    : "\\prod_v x_v^{\\alpha_v}";

  // regionLatex is empty when all x_i are fixed (fully localised) — no integral remains.
  // regionLatex is non-empty when some x_i are free and must be integrated over.
  const fullyLocalised = !regionLatex || regionLatex.length === 0;
  const intTex  = fullyLocalised ? null : `\\int_{\\Delta_{\\mathfrak{g}}}`;
  const gammaTex = fullyLocalised
    ? null
    : `\\scriptstyle \\Delta_{\\mathfrak{g}} = \\left\\{${regionLatex.join(",\\,")}\\right\\}`;

  function r(tex, displayMode = false) {
    try { return katex.renderToString(tex, { displayMode, throwOnError: false }); }
    catch { return tex; }
  }

  const intHtml   = intTex ? r(intTex, true) : null;
  const gammaHtml = gammaTex ? r(gammaTex) : null;
  const twistHtml = r(twistTex);
  const phiHtml   = r("\\varphi_{\\mathcal{G}}");
  const circHtml  = r("\\circ");

  // Sort by global tube index ascending (t1 < ... < tn), then reverse to write Res_{tn} ∘ ... ∘ Res_{t1}
  function sortedTubing(ct) {
    return [...ct].sort((a, b) => b - a);
  }

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: "0.1em" }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "0.2em", lineHeight: 1.4 }}>
        {intHtml && <span dangerouslySetInnerHTML={{ __html: intHtml }} style={{ display: "inline-block" }} />}
        {!fullyLocalised && <span style={{ fontSize: "1.1em" }}>&#x5B;</span>}
        {periodSigns.map((sign, i) => {
          const sorted = cutTubings?.[i] ? sortedTubing(cutTubings[i]) : [];
          return (
            <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "0.12em" }}>
              {(i > 0 || sign < 0) && (
                <span style={{ margin: "0 0.15em" }}>{sign < 0 ? "−" : "+"}</span>
              )}
              {sorted.map((j, k) => (
                <span key={j} style={{ display: "inline-flex", alignItems: "center", gap: "0.05em" }}>
                  {k > 0 && (
                    <span dangerouslySetInnerHTML={{ __html: circHtml }} style={{ margin: "0 0.12em" }} />
                  )}
                  <span style={{ display: "inline-flex", alignItems: "flex-end", gap: "1px" }}>
                    <span style={{ fontFamily: "KaTeX_Main, Times New Roman, serif", fontStyle: "normal" }}>Res</span>
                    {tubeSvgs?.[j] ? (
                      <img
                        src={svgDataUri(tubeSvgs[j])}
                        style={{ width: 32, height: "auto", marginBottom: "-3px" }}
                        alt={`t${j + 1}`}
                      />
                    ) : (
                      <sub style={{ fontSize: "0.75em" }}>{j + 1}</sub>
                    )}
                  </span>
                </span>
              ))}
              <span style={{ margin: "0 0.1em" }}>&#x5B;</span>
              <span dangerouslySetInnerHTML={{ __html: twistHtml }} />
              <span dangerouslySetInnerHTML={{ __html: phiHtml }} />
              <span>&#x5D;</span>
            </span>
          );
        })}
        {!fullyLocalised && <span style={{ fontSize: "1.1em" }}>&#x5D;</span>}
      </div>
      {gammaHtml && (
        <div dangerouslySetInnerHTML={{ __html: gammaHtml }} style={{ textAlign: "center" }} />
      )}
    </div>
  );
}
