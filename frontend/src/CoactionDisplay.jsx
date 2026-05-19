/**
 * Renders the coaction result ΔP(γ,φ) as a list of terms.
 * Each term: coeff · (left_period ⊗ right_period)
 * Periods are shown as SVGs when available (tubes superimposed on acyclic minor).
 */
import PgPhysLatex from "./PgPhysLatex";
import PeriodSum, { periodNetSign, ResultSection } from "./PeriodSum";
import CoeffLabel from "./CoeffLabel";

function TermRow({ term, vertices, edges, tubes, positions, physContour, physForm, tubeSvgs }) {
  const nVerts = vertices.length;
  const usePhys   = physContour && term.left_phys_svg;
  const leftSvgs  = usePhys ? [term.left_phys_svg] : term.left_svgs;
  const leftSigns = usePhys ? [1]                  : term.left_signs;
  const leftLatex = usePhys ? (term.left_phys_latex ?? []) : (term.left_latex ?? []);
  const netSign = periodNetSign(leftSvgs, leftSigns)
                * periodNetSign(term.right_svgs, term.right_signs);

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
      <CoeffLabel coefficient={term.coefficient} sign={netSign} />
      <div className="tensor-pair">
        <div className="tensor-side">
          <PeriodSum
            svgs={leftSvgs}
            signs={leftSigns}
            latex={leftLatex}
            dec={term.left_dec}
            vertices={vertices} edges={edges}
            tubeSet={term.left_tube_sets?.[0]}
            tubes={tubes} positions={positions}
            nVerts={nVerts}
          />
        </div>
        <span className="otimes">⊗</span>
        <div className="tensor-side">
          <PeriodSum
            svgs={term.right_svgs}
            signs={term.right_signs}
            latex={term.right_latex}
            nodeContent={rightNodeContent}
            dec={term.right_dec}
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

export default function CoactionDisplay({ result, positions, title = "ΔP(γ, φ)", physContour = false, physForm = false }) {
  const { vertices, edges, tubes, terms, tube_svgs } = result;
  return (
    <ResultSection
      title={title}
      terms={terms}
      className="coaction-display result-section"
      renderTerm={(t, i) => (
        <TermRow
          key={i}
          term={t}
          vertices={vertices}
          edges={edges}
          tubes={tubes}
          positions={positions}
          physContour={physContour}
          physForm={physForm}
          tubeSvgs={tube_svgs ?? []}
        />
      )}
    />
  );
}
