export function formatUnitsString(
  raw: string | number | null | undefined,
  decimals = 18,
  precision = 4
): string {
  let s = String(raw ?? "0").trim();

  // strip sign and remember it
  let neg = false;
  if (s.startsWith("-")) {
    neg = true;
    s = s.slice(1);
  }

  // keep digits only
  s = s.replace(/\D/g, "");
  if (s === "") s = "0";

  if (decimals === 0) return neg ? "-" + s : s;

  if (s.length <= decimals) {
    // 0.xxx case
    const frac = s.padStart(decimals, "0");
    let outFrac = frac.slice(0, precision).replace(/0+$/, "");
    const out = outFrac ? `0.${outFrac}` : "0";
    return neg ? "-" + out : out;
  }

  const intPart = s.slice(0, s.length - decimals).replace(/^0+(?=\d)/, "");
  let fracPart = s.slice(s.length - decimals);

  if (precision >= 0) fracPart = fracPart.slice(0, precision);
  fracPart = fracPart.replace(/0+$/, "");

  const out = fracPart ? `${intPart}.${fracPart}` : intPart;
  return neg ? "-" + out : out;
}