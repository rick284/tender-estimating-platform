import { useState } from "react";
import { Download } from "lucide-react";
import type { Estimate, ScheduleSource } from "../lib/types";
import { api } from "../lib/api";
import { fmtMoney } from "../lib/format";
import { editKey, useEdit } from "../lib/edit";
import { ScheduleFormatDialog, SplitDialog } from "../components/ScheduleDialogs";
import { Chip, Empty, Money, PageHeader, Panel } from "../components/ui";

type Kind = "report.pdf" | "schedule.pdf" | "pricing.xlsx";
const DOCS: { kind: Kind; title: string; body: string; button: string }[] = [
  { kind: "report.pdf", title: "Estimate basis and tender report", body: "The narrative report: summary, commercial position, pricing basis, programme and weather, assumptions and the quantity schedule.", button: "Download PDF" },
  { kind: "schedule.pdf", title: "Tender price schedule", body: "The price schedule in the client's format, ready to submit with the tender.", button: "Download PDF" },
  { kind: "pricing.xlsx", title: "Client pricing workbook", body: "Client summary, the price schedule and its reconciliation to the tender, as an Excel file.", button: "Download Excel" },
];

const asString = (m: ScheduleSource["map"]): string => (typeof m === "string" ? m : Array.isArray(m) ? JSON.stringify(m) : "");

export function Outputs({ est, tenderId, rev }: { est: Estimate; tenderId: string; rev: number }) {
  const sch = est.schedule;
  const { editing, edits, set, reset, add, remove } = useEdit();
  const [busy, setBusy] = useState<Kind | null>(null);
  const [err, setErr] = useState("");
  const [formatOpen, setFormatOpen] = useState(false);
  const [split, setSplit] = useState<ScheduleSource | null>(null);
  const unsaved = Object.keys(edits).length > 0;
  if (!sch) {
    return (
      <>
        <PageHeader title="Client outputs" />
        <Empty title="Not available for this revision" body="This revision was saved before client outputs existed. Upload its workbook again from the Revisions page and the report, price schedule and pricing workbook will be available." />
      </>
    );
  }

  const get = async (kind: Kind) => {
    setBusy(kind); setErr("");
    try { await api.downloadOutput(tenderId, rev, kind); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't create the document."); } finally { setBusy(null); }
  };
  const mapKey = (key: string) => editKey("schedule_map", key, "to");
  const current = (s: ScheduleSource) => edits[mapKey(s.key)]?.value ?? asString(s.map);
  const change = (s: ScheduleSource, v: string) => {
    const original = edits[mapKey(s.key)]?.original ?? asString(s.map);
    if (v === original) reset("schedule_map", s.key, "to");
    else set({ target: "schedule_map", key: s.key, field: "to", value: v, original });
  };
  const multi = sch.groups.length > 1;
  const groups = Array.from(new Set(sch.targets.map((t) => t.group)));
  const unmappedKeys = new Set(sch.unmapped.map((u) => u.key));
  const sources = [...sch.sources].sort((a, b) => Number(unmappedKeys.has(b.key)) - Number(unmappedKeys.has(a.key)));

  return (
    <>
      <PageHeader title="Client outputs" sub="The documents you send with the tender, generated from this estimate. Every figure comes from the same calculation as the rest of the platform." />
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {unsaved && <p className="mb-4 border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">You have changes that aren't saved yet. Documents are created from the saved revision, so save first to include them.</p>}

      <Panel title="Documents" flush>
        <ul className="divide-y">
          {DOCS.map((d) => (
            <li key={d.kind} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1"><div className="font-medium">{d.title}</div><div className="text-sm text-muted-foreground">{d.body}</div></div>
              <button className="btn btn-ghost" onClick={() => get(d.kind)} disabled={busy !== null}><Download size={14} aria-hidden /> {busy === d.kind ? "Creating…" : d.button}</button>
            </li>
          ))}
        </ul>
        {!sch.reconciles && <p className="border-t px-4 py-3 text-sm text-red-fg">The price schedule doesn't reconcile yet, so the schedule documents are marked DRAFT. Map every item below to a schedule line first.</p>}
      </Panel>

      <Panel className="mt-4" title="Price schedule" flush
        action={<span className="flex items-center gap-2"><Chip tone={sch.reconciles ? "green" : "red"}>{sch.reconciles ? "Reconciles" : "Not reconciled"}</Chip>
          {editing && <button className="btn btn-ghost !py-1" onClick={() => setFormatOpen(true)}>{sch.auto ? "Use the client's format" : "Replace format"}</button>}
          {editing && !sch.auto && <button className="btn btn-ghost !py-1" onClick={() => { if (window.confirm("Go back to the automatic schedule by section? You can undo this before saving.")) remove("schedule", "format"); }}>Back to automatic</button>}</span>}>
        <div className="border-b px-4 py-3 text-sm text-muted-foreground">
          {sch.auto ? "Automatic format: one line per QS section and one per subcontract package. If the client gave you their own schedule, use their format." : <>Format: <strong className="text-foreground">{sch.name || "Client format"}</strong>{sch.client && <> · {sch.client}</>}</>}
        </div>
        <div className="overflow-x-auto">
          <table className="grid-table">
            <thead><tr><th className="w-28">Ref</th><th>Trade</th><th className="w-40 text-right">Total (excl. GST)</th></tr></thead>
            <tbody>
              {sch.groups.map((g) => (
                <GroupRows key={g.id} g={g} single={!multi} />
              ))}
              <tr className="total-row"><td /><td>{multi ? "COMBINED TOTAL (EXCL GST)" : "TOTAL (EXCL GST)"}</td><td className="num"><Money v={sch.total} /></td></tr>
            </tbody>
          </table>
        </div>
        <div className="grid gap-x-8 gap-y-1 border-t px-4 py-3 text-sm sm:grid-cols-3">
          <div><span className="text-muted-foreground">Known package</span> <span className="num ml-2">{fmtMoney(sch.gross_package)}</span></div>
          <div><span className="text-muted-foreground">Working all-in tender</span> <span className="num ml-2">{fmtMoney(sch.all_in)}</span></div>
          <div><span className="text-muted-foreground">Difference</span> <span className="num ml-2">{fmtMoney(sch.difference)}</span></div>
        </div>
        {sch.problems.length > 0 && <ul className="border-t px-4 py-3 text-sm text-red-fg">{sch.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
        <p className="border-t px-4 py-3 text-xs text-muted-foreground">Overhead, profit and any cost the client's schedule has no line for are carried in each group's Margin line. Each group is priced as (cost + overhead) ÷ (1 − margin), so the groups add up to the tender exactly.</p>
      </Panel>

      <Panel className="mt-4" title="Where each cost goes" flush
        action={sch.unmapped.length > 0 ? <Chip tone="red">{sch.unmapped.length} not mapped</Chip> : <Chip tone="green">All mapped</Chip>}>
        <div className="overflow-x-auto">
          <table className="grid-table min-w-[40rem]">
            <thead><tr><th>Item</th><th className="w-28">Type</th><th className="w-36 text-right">Amount</th><th className="w-80">Schedule line</th></tr></thead>
            <tbody>
              {sources.map((s) => {
                const v = current(s);
                const isSplit = v.startsWith("[");
                const label = isSplit ? `Split across ${(JSON.parse(v) as unknown[]).length} lines` : (sch.targets.find((t) => t.value === v)?.label ?? "— not mapped —");
                return (
                  <tr key={s.key} className={unmappedKeys.has(s.key) ? "bg-red-bg/40" : ""}>
                    <td>{s.label}</td>
                    <td><Chip tone="neutral">{s.key.startsWith("overlay:") ? "Subcontract" : s.key.startsWith("ca:") ? "Allowance" : "Own works"}</Chip></td>
                    <td className="num"><Money v={s.amount} /></td>
                    <td>
                      {editing ? (
                        <div className="flex items-center gap-2">
                          <select aria-label={`Schedule line for ${s.label}`} value={isSplit ? "__split" : v} onChange={(e) => change(s, e.target.value)}
                            className={`h-8 min-w-0 flex-1 border bg-background px-2 text-sm focus:border-primary ${edits[mapKey(s.key)] ? "border-amber-line bg-amber-bg" : ""}`}>
                            <option value="">— not mapped —</option>
                            {isSplit && <option value="__split" disabled>{label}</option>}
                            {groups.map((gname) => (
                              <optgroup key={gname || "other"} label={gname || "Other"}>
                                {sch.targets.filter((t) => t.group === gname).map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                              </optgroup>
                            ))}
                          </select>
                          <button className="btn btn-ghost !px-2 !py-1" onClick={() => setSplit({ ...s, map: splitInit(v) })}>Split</button>
                        </div>
                      ) : <span className={unmappedKeys.has(s.key) ? "text-red-fg" : ""}>{label}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="border-t px-4 py-3 text-xs text-muted-foreground">Every item must go on exactly one line (or be split across lines), so nothing is missed or counted twice. Use "Inside margin" for a cost the schedule has no line for, or "Spread" to share it across the groups by their own-works lines.</p>
      </Panel>

      <ScheduleFormatDialog open={formatOpen} onClose={() => setFormatOpen(false)} current={sch} onAdd={(p) => add("schedule", "format", p)} />
      <SplitDialog open={split !== null} onClose={() => setSplit(null)} source={split} targets={sch.targets.filter((t) => t.value.startsWith("line:"))}
        onSave={(json) => { if (split) change(split, json); }} />
    </>
  );
}

function splitInit(v: string): ScheduleSource["map"] {
  if (v.startsWith("[")) { try { return JSON.parse(v); } catch { return null; } }
  return v || null;
}

function GroupRows({ g, single }: { g: import("../lib/types").ScheduleGroup; single: boolean }) {
  const work = g.lines.filter((x) => x.kind === "work");
  const rest = g.lines.filter((x) => x.kind !== "work");
  return (
    <>
      {!single && <tr className="bg-muted/60"><td colSpan={3} className="font-heading text-xs font-bold uppercase tracking-wider">{g.name}{g.code && ` (${g.code})`}</td></tr>}
      {work.map((x) => <tr key={x.ref}><td className="font-mono text-xs">{x.ref}</td><td>{x.trade}</td><td className="num"><Money v={x.amount} dash0 /></td></tr>)}
      <tr className="font-semibold"><td /><td>SUB-TOTAL</td><td className="num"><Money v={g.subtotal} dash0 /></td></tr>
      {rest.map((x) => <tr key={x.ref}><td className="font-mono text-xs">{x.ref}</td><td>{x.trade}{x.kind === "margin" && g.hidden > 0.005 && <span className="ml-2 text-xs text-muted-foreground">(includes {fmtMoney(g.hidden)} allocated)</span>}</td><td className="num"><Money v={x.amount} dash0 /></td></tr>)}
      {!single && <tr className="total-row"><td /><td>{g.name} SUB-TOTAL (EXCL GST){g.code && ` ${g.code}`}</td><td className="num"><Money v={g.total} /></td></tr>}
    </>
  );
}
