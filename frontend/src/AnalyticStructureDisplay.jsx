/**
 * Displays dP(γ,φ) and discP(γ,φ): the differential and discontinuity of the FRW period.
 *
 * dP terms:    P(γ,f) SVG (click for integrand) ∧ HighlightGraph letter
 * discP terms: HighlightGraph letter · P(f,φ) SVG (click for integrand)
 */
import { useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import PgPhysLatex from "./PgPhysLatex";
import PeriodSum, { periodNetSign, svgSize, LatexTerms, ResultSection } from "./PeriodSum";
import CoeffLabel, { sub, alpha } from "./CoeffLabel";
import { svgDataUri } from "./graphUtils";

function LatexInline({ tex }) {
  try {
    const html = katex.renderToString(tex, { displayMode: false, throwOnError: false });
    return <span dangerouslySetInnerHTML={{ __html: html }} />;
  } catch {
    return <span>{tex}</span>;
  }
}

function letterSize(nVerts) {
  return Math.round(svgSize(nVerts) * 0.61);
}

function LetterSVG({ svg, size }) {
  const dataUri = svgDataUri(svg);
  return (
    <img
      src={dataUri}
      style={{ width: size, height: "auto", verticalAlign: "middle", background: "white" }}
      alt="letter"
    />
  );
}

/** Builds the algebraic KaTeX terms for the expanded (click-to-toggle) letter view. */
function makeAlgebraicLatexTerms(letter_type, letter_coeffs, letter_latex, mode) {
  if (!letter_latex || letter_latex.length === 0) return null;
  const funcTex = mode === "dlog" ? "\\mathrm{dlog}" : "\\mathrm{Disc}\\,\\mathrm{log}";

  if (letter_type === "diag") {
    return letter_latex.map((ltex, i) => {
      const coeff = letter_coeffs?.[i];
      const showCoeff = coeff && coeff !== "1";
      return showCoeff
        ? `\\left(${coeff}\\right)\\,${funcTex}\\!\\left(${ltex}\\right)`
        : `${funcTex}\\!\\left(${ltex}\\right)`;
    });
  }
  if (letter_type === "ratio" && letter_latex.length >= 1) {
    const coeff = letter_coeffs?.[0];
    const showCoeff = coeff && coeff !== "1";
    return [showCoeff
      ? `\\left(${coeff}\\right)\\,${funcTex}\\!\\left(${letter_latex[0]}\\right)`
      : `${funcTex}\\!\\left(${letter_latex[0]}\\right)`];
  }
  return null;
}

/** Renders a dlog/Disc-log symbol letter using HighlightGraph SVGs.
 *  Click to toggle between SVG (graphical) and algebraic (KaTeX) view.
 *  mode: "dlog" for dP, "disc" for discP
 *  letter_type: "diag" | "ratio" | "zero"
 *  letter_svgs: array of SVG strings
 *  letter_coeffs: array of KaTeX strings for coefficients
 *  letter_latex: array of KaTeX strings for the kinematic letters (arguments of dlog)
 */
function LetterDisplay({ letter_type, letter_svgs, letter_coeffs, letter_latex, mode, nVerts }) {
  const [expanded, setExpanded] = useState(false);

  if (!letter_type || letter_type === "zero" || !letter_svgs || letter_svgs.length === 0) return null;

  const funcTex = mode === "dlog" ? "\\mathrm{dlog}" : "\\mathrm{Disc}\\,\\mathrm{log}";
  const lSize = letterSize(nVerts);
  const algebraicTerms = makeAlgebraicLatexTerms(letter_type, letter_coeffs, letter_latex, mode);
  const hasAlgebraic = algebraicTerms && algebraicTerms.length > 0;

  if (expanded && hasAlgebraic) {
    return (
      <div
        className="letter-display period-sum-hover"
        onClick={() => setExpanded(false)}
        title="Click to show graphic"
      >
        <LatexTerms terms={algebraicTerms} />
      </div>
    );
  }

  const svgView = (() => {
    if (letter_type === "ratio" && letter_svgs.length >= 2) {
      const coeff = letter_coeffs?.[0];
      const showCoeff = coeff && coeff !== "1";
      return (
        <div className="letter-display letter-ratio">
          {showCoeff && (
            <span className="letter-coeff">
              <span>(</span><LatexInline tex={coeff} /><span>)</span>
            </span>
          )}
          <LatexInline tex={funcTex} />
          <span className="letter-paren">(</span>
          <div className="letter-frac">
            <LetterSVG svg={letter_svgs[0]} size={lSize} />
            <div className="letter-frac-bar" />
            <LetterSVG svg={letter_svgs[1]} size={lSize} />
          </div>
          <span className="letter-paren">)</span>
        </div>
      );
    }

    if (letter_type === "diag") {
      return (
        <div className="letter-display letter-diag">
          {letter_svgs.map((svg, i) => {
            const coeff = letter_coeffs?.[i];
            const showCoeff = coeff && coeff !== "1";
            return (
              <span key={i} className="letter-diag-term">
                {i > 0 && <span className="letter-plus"> + </span>}
                {showCoeff && (
                  <span className="letter-coeff">
                    <span>(</span><LatexInline tex={coeff} /><span>)</span>
                  </span>
                )}
                <LatexInline tex={funcTex} />
                <span className="letter-paren">(</span>
                <LetterSVG svg={svg} size={lSize} />
                <span className="letter-paren">)</span>
              </span>
            );
          })}
        </div>
      );
    }

    return null;
  })();

  if (!svgView) return null;

  return hasAlgebraic ? (
    <div
      className="period-sum-hover"
      onClick={() => setExpanded(true)}
      title="Click to show algebraic form"
    >
      {svgView}
    </div>
  ) : svgView;
}


function DPTermRow({ term, vertices, edges, tubes, positions, physContour }) {
  const nVerts = vertices.length;
  const usePhys   = physContour && term.left_phys_svg;
  const leftSvgs  = usePhys ? [term.left_phys_svg] : term.left_svgs;
  const leftSigns = usePhys ? [1]                  : term.left_signs;
  const leftLatex = usePhys ? (term.left_phys_latex ?? []) : (term.left_latex ?? []);
  const sign = periodNetSign(leftSvgs, leftSigns);
  return (
    <div className="term-row">
      <CoeffLabel coefficient={term.coefficient} sign={sign} />
      <div className="tensor-pair">
        <div className="tensor-side">
          <PeriodSum
            svgs={leftSvgs}
            signs={leftSigns}
            latex={leftLatex}
            dec={term.f_dec}
            vertices={vertices} edges={edges}
            tubeSet={term.left_tube_sets?.[0]}
            tubes={tubes} positions={positions}
            nVerts={nVerts}
          />
        </div>
        <div className="tensor-side">
          <div className="letter-bracket-wrap">
            <div className="letter-bracket-open" />
            <LetterDisplay
              letter_type={term.letter_type}
              letter_svgs={term.letter_svgs ?? []}
              letter_coeffs={term.letter_coeffs ?? []}
              letter_latex={term.letter_latex ?? []}
              mode="dlog"
              nVerts={nVerts}
            />
            <div className="letter-bracket-close" />
          </div>
        </div>
      </div>
    </div>
  );
}

function DiscPTermRow({ term, vertices, edges, tubes, positions, physForm, tubeSvgs }) {
  const nVerts = vertices.length;
  const sign = periodNetSign(term.right_svgs, term.right_signs);

  const rightNodeContent = physForm ? (
    <PgPhysLatex
      periodSigns={term.right_signs}
      regionLatex={term.right_region_latex ?? []}
      vertices={vertices}
      cutTubings={term.right_tube_sets}
      tubes={tubes}
      tubeSvgs={tubeSvgs}
    />
  ) : null;

  return (
    <div className="term-row">
      <CoeffLabel coefficient={term.coefficient} sign={sign} />
      <div className="tensor-pair">
        <div className="tensor-side">
          <div className="letter-bracket-wrap">
            <div className="letter-bracket-open" />
            <LetterDisplay
              letter_type={term.letter_type}
              letter_svgs={term.letter_svgs ?? []}
              letter_coeffs={term.letter_coeffs ?? []}
              letter_latex={term.letter_latex ?? []}
              mode="disc"
              nVerts={nVerts}
            />
            <div className="letter-bracket-close" />
          </div>
        </div>
        <div className="tensor-side">
          <PeriodSum
            svgs={term.right_svgs}
            signs={term.right_signs}
            latex={term.right_latex}
            nodeContent={rightNodeContent}
            dec={term.f_dec}
            vertices={vertices} edges={edges}
            tubeSet={term.right_tube_sets?.[0]}
            tubes={tubes} positions={positions}
            nVerts={nVerts}
          />
        </div>
      </div>
    </div>
  );
}

function hasLetter(term) {
  return term.letter_type && term.letter_type !== "zero" &&
    Array.isArray(term.letter_svgs) && term.letter_svgs.length > 0;
}

export default function AnalyticStructureDisplay({ dpResult, discpResult, vertices, edges, positions, dpTitle = "dP(γ, φ)", discpTitle = "Disc P(γ, φ)", dpNote, physContour = false, physForm = false }) {
  const tubes = [];

  const dpTerms = dpResult ? dpResult.terms.filter(hasLetter) : [];
  const discpTerms = discpResult ? discpResult.terms.filter(hasLetter) : [];

  return (
    <div>
      {dpResult && (
        <ResultSection
          title={dpTitle}
          termCount={dpTerms.length}
          terms={dpTerms}
          note={dpNote}
          renderTerm={(t, i) => (
            <DPTermRow
              key={i}
              term={t}
              vertices={vertices}
              edges={edges}
              tubes={tubes}
              positions={positions}
              physContour={physContour}
            />
          )}
        />
      )}
      {discpResult && (
        <ResultSection
          title={discpTitle}
          termCount={discpTerms.length}
          terms={discpTerms}
          renderTerm={(t, i) => (
            <DiscPTermRow
              key={i}
              term={t}
              vertices={vertices}
              edges={edges}
              tubes={discpResult.tubes ?? tubes}
              positions={positions}
              physForm={physForm}
              tubeSvgs={discpResult.tube_svgs ?? []}
            />
          )}
        />
      )}
    </div>
  );
}
