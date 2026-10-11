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

const dateFmt = new Intl.DateTimeFormat("en-NZ", { day: "numeric", month: "short", year: "numeric" });
export function fmtDate(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
}
export function fmtAgo(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z").getTime();
  const mins = Math.round((Date.now() - d) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h} h ago`;
  const days = Math.round(h / 24);
  return days < 30 ? `${days} d ago` : dateFmt.format(new Date(d));
}
export function fmtCompactMoney(v: number): string {
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(2)}m`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}
