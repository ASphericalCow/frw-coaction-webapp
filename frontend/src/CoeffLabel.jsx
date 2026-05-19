/**
 * Shared coefficient label utilities for coaction and analytic-structure displays.
 *
 * Exports:
 *   SUBSCRIPTS, sub(n), alpha(v) — Unicode subscript helpers
 *   CoeffLabel                   — rendered ± coefficient with fraction
 */

const SUBSCRIPTS = "₀₁₂₃₄₅₆₇₈₉";

export function sub(n) {
  return String(n).split("").map((c) => SUBSCRIPTS[parseInt(c)] ?? c).join("");
}

export function alpha(v) {
  return `α${sub(v)}`;
}

export default function CoeffLabel({ coefficient, sign = 1 }) {
  const { factors = [], ncct_count = 1 } = coefficient ?? {};
  const hasFactors = factors.length > 0;
  const hasIntDen = ncct_count > 1;
  const signChar = sign < 0 ? "−" : "+";

  if (!hasFactors && !hasIntDen) {
    return <span className="coeff">{signChar}</span>;
  }

  const numParts = hasFactors ? factors.map((f) => f.num.map(alpha).join("")) : ["1"];
  const denParts = [
    ...(hasIntDen ? [String(ncct_count)] : []),
    ...(hasFactors ? factors.map((f) =>
      f.den.length === 1 ? alpha(f.den[0]) : `(${f.den.map(alpha).join("+")})`
    ) : []),
  ];

  return (
    <span className="coeff coeff-fraction">
      <span className="coeff-sign">{signChar}</span>
      <span className="fraction">
        <span className="frac-num">{numParts.join("·")}</span>
        <span className="frac-bar" />
        <span className="frac-den">{denParts.join("·")}</span>
      </span>
    </span>
  );
}
