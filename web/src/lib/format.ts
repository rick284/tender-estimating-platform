const money = new Intl.NumberFormat("en-NZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const qty = new Intl.NumberFormat("en-NZ", { minimumFractionDigits: 0, maximumFractionDigits: 3 });

/** $1,234.56 — negatives as -$1,234.56; null/undefined as an em dash. */
export function fmtMoney(v: number | null | undefined, opts: { dash0?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (opts.dash0 && Math.abs(v) < 0.005) return "—";
  const s = money.format(Math.abs(v));
  return v < 0 ? `-$${s}` : `$${s}`;
}
export function fmtNum(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return qty.format(v);
}
export function fmtPct(v: number | null | undefined, dp = 2): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(dp)}%`;
}
export function rag(text: string | undefined): "GREEN" | "AMBER" | "RED" | "" {
  const t = (text || "").toUpperCase();
  if (t.startsWith("GREEN")) return "GREEN";
  if (t.startsWith("AMBER")) return "AMBER";
  if (t.startsWith("RED")) return "RED";
  return "";
}
