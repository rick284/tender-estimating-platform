import type { Estimate } from "./types";

/** Plain-language overview of the job built ONLY from what is already in the estimate (scope items, register questions) and the Job Record. Nothing is priced or invented. */
export function briefFromScope(est: Estimate, recordFields: Record<string, string> = {}): Record<string, string> {
  const items = est.scope?.items ?? [];
  if (items.length === 0) return {};
  const t = (x: { title: string }) => x.title.replace(/\s+/g, " ").trim();
  const by = (f: (i: (typeof items)[number]) => boolean) => items.filter(f).map(t);
  const own = by((i) => i.owner === "OWN WORKS" && !["EXCLUDED", "BY OTHERS"].includes(i.treatment));
  const sub = by((i) => i.owner === "SUBCONTRACT");
  const shared = by((i) => i.owner === "SHARED");
  const others = by((i) => i.treatment === "BY OTHERS" || (i.owner === "OTHERS" && i.treatment !== "EXCLUDED"));
  const excluded = by((i) => i.treatment === "EXCLUDED");
  const tbc = by((i) => i.owner === "TBC" || i.treatment === "UNRESOLVED");
  const line = (label: string, xs: string[]) => (xs.length ? `${label} (${xs.length}): ${xs.join("; ")}.` : "");
  const out: Record<string, string> = {
    job_summary: [`Scope: ${items.length} items.`, line("Our own works", own), line("Subcontract packages", sub), line("Shared with others", shared), line("By others", others), line("Excluded", excluded)].filter(Boolean).join("\n"),
  };
  const open = (est.register ?? []).filter((r) => r.kind === "rfi" && r.status === "OPEN").map((r) => `${r.ref}: ${r.title.replace(/^Q\d+:\s*/, "")}`);
  const unknown = [tbc.length ? `Scope items still to confirm or decide (${tbc.length}): ${tbc.join("; ")}.` : "", open.length ? `Open questions (${open.length}):\n${open.join("\n")}` : ""].filter(Boolean).join("\n");
  if (unknown) out.unknown = unknown;
  out.known = `${items.length - tbc.length} of ${items.length} scope items have an owner and treatment. Nothing is measured or priced until the take-off steps.`;
  const due = (recordFields.tender_closes || "").trim();
  if (due && /\d/.test(due) && !/not provided|n\/a|tbc/i.test(due)) out.tender_due = due;
  return out;
}
