import { Fragment, useState, type FormEvent } from "react";
import type { Estimate, ReserveItem } from "../lib/types";
import { EditField } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { fmtMoney, fmtPct } from "../lib/format";
import { useEdit } from "../lib/edit";

const mid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "M-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };
const opt = (xs: string[]) => xs.map((x) => ({ value: x, label: x }));
const TONE = { RED: "red", AMBER: "amber", GREEN: "green" } as const;
const POS = { within: ["green", "Within the weighted range"], below: ["amber", "Below the weighted range"], above: ["amber", "Above the weighted range"] } as const;
const money = (v: number | null | undefined) => (v === null || v === undefined ? "—" : fmtMoney(v));
const pct = (v: string) => (v === "" ? "—" : fmtPct(Number(v), 0));

function AddDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (p: Record<string, unknown>) => void }) {
  const blank = { title: "", description: "", source_ref: "", impact: "", basis: "Cost", probability_low: "", probability_high: "", prob_status: "AMBER", prob_basis: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim()) return setErr("Name the unresolved item.");
    const p = (v: string) => v.trim() === "" || (Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 100);
    if (!p(f.probability_low) || !p(f.probability_high)) return setErr("Probabilities are percentages between 0 and 100.");
    if (f.impact.trim() && !Number.isFinite(Number(f.impact.replace(/[$,]/g, "")))) return setErr("The consequence needs a number.");
    const frac = (v: string) => (v.trim() === "" ? "" : String(Number(v) / 100));
    onAdd({ ...f, impact: f.impact.replace(/[$,]/g, ""), impact_status: f.impact.trim() ? "Quantified" : "Unquantified", probability_low: frac(f.probability_low), probability_high: frac(f.probability_high || f.probability_low) });
    setF(blank); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add an unresolved item">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">Only items that <strong>cannot realistically be closed out</strong> before the price goes in belong here. Give the extra <strong>cost</strong> if it goes wrong (against the current price; cost, not sell, so the figure does not move when overhead or margin change) and how likely that is. Leave the probability blank if it cannot be supported: no dollar value will be assumed.</p>
        <label className="block"><span className="label">Unresolved item</span><input className={`${field} h-10`} value={f.title} onChange={set("title")} maxLength={300} autoFocus /></label>
        <label className="block"><span className="label">Where it comes from (RFI, risk, quote)</span><input className={`${field} h-10`} value={f.source_ref} onChange={set("source_ref")} maxLength={200} placeholder="e.g. RFI-15 / RT01" /></label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Extra cost if adverse ($)</span><input className={`${field} h-10`} inputMode="decimal" value={f.impact} onChange={set("impact")} /></label>
          <label className="block"><span className="label">Entered as</span><select className={`${field} h-10`} value={f.basis} onChange={set("basis")}><option>Cost</option><option>Sell</option></select></label>
          <label className="block"><span className="label">Probability evidence</span><select className={`${field} h-10`} value={f.prob_status} onChange={set("prob_status")}><option>GREEN</option><option>AMBER</option><option>UNKNOWN</option></select></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Probability, low (%)</span><input className={`${field} h-10`} inputMode="decimal" value={f.probability_low} onChange={set("probability_low")} /></label>
          <label className="block"><span className="label">Probability, high (%)</span><input className={`${field} h-10`} inputMode="decimal" value={f.probability_high} onChange={set("probability_high")} placeholder="same as low" /></label>
        </div>
        <label className="block"><span className="label">Why that probability (the evidence)</span><textarea className={`${field} py-2`} rows={3} value={f.prob_basis} onChange={set("prob_basis")} maxLength={3000} /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button type="submit" className="btn btn-solid">Add item</button></div>
      </form>
    </Modal>
  );
}

export function ManagementReserve({ est }: { est: Estimate }) {
  const { editing, add, remove } = useEdit();
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const r = est.management_reserve;
  const wrap = "whitespace-pre-line text-sm leading-snug";
  const E = (x: ReserveItem, f: keyof ReserveItem, label: string, o: { kind?: "text" | "textarea" | "number" | "select"; width?: string; options?: { value: string; label: string }[] } = {}) => (
    <EditField target="reserve_item" id={x.id} field={f} value={String(x[f] ?? "")} label={`${x.ref} ${label}`} kind={o.kind} options={o.options} width={o.width ?? "w-full"} display={String(x[f] ?? "") || "—"} />
  );
  const B = (f: "selected" | "selected_basis" | "adjudicated_by" | "adjudicated_on", label: string, kind: "text" | "textarea" | "number" = "text", width = "w-full") => (
    <EditField target="reserve" id="block" field={f} value={f === "selected" ? (r?.selected === null || r?.selected === undefined ? "" : String(r.selected)) : String(r?.[f] ?? "")} label={label} kind={kind} width={width}
      display={f === "selected" ? money(r?.selected) : String(r?.[f] ?? "") || "—"} />
  );
  return (
    <>
      <PageHeader title="Management Reserve" sub="Not a percentage and not a pulled-out sum: a reserve chosen after weighing the items that cannot realistically be closed out before the price must go in, each with a probability and a consequence."
        actions={editing && r ? <button className="btn btn-solid" onClick={() => setAdding(true)}>Add item</button> : undefined} />
      {!r ? (
        <>
          <Empty title="The reserve is not set up as an adjudication" body="Today the reserve line (CA16) is a plain amount. Switch the adjudication on to record the unresolved items, their probabilities and consequences, and to choose the reserve against them." />
          {editing && <div className="mt-4"><button className="btn btn-solid" onClick={() => add("reserve", "setup", {})}>Switch on the adjudication</button></div>}
        </>
      ) : (
        <>
          {(r.issues.length > 0 || r.notes.length > 0) && (
            <div className="mb-4 space-y-2" role="status">
              {r.issues.map((i) => <div key={i} className="border border-red-line bg-red-bg px-4 py-2 text-sm text-red-fg">{i}</div>)}
              {r.notes.map((n) => <div key={n} className="border border-amber-line bg-amber-bg px-4 py-2 text-sm text-amber-fg">{n}</div>)}
            </div>
          )}
          <Panel className="mb-4">
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
              <Stat label="Weighted exposure (tender effect)" value={`${money(r.weighted_low_sell)} – ${money(r.weighted_high_sell)}`} sub={`Midpoint ${money(r.weighted_mid_sell)} · cost basis ${money(r.weighted_low)} – ${money(r.weighted_high)}`} />
              <Stat label="Selected reserve (before overhead and margin)" value={money(r.selected)} sub={r.selected_pct !== null ? `${fmtPct(r.selected_pct, 2)} of the pre-overhead subtotal` : "Not chosen yet"} strong />
              <Stat label="Selected reserve (tender effect)" value={money(r.selected_sell)} sub={r.position ? <Chip tone={POS[r.position][0]}>{POS[r.position][1]}{r.position !== "within" && r.gap !== null ? ` by ${money(r.gap)}` : ""}</Chip> : "—"} />
              <Stat label="Left unweighted" value={`${r.unknown_items + r.unquantified_items}`} sub={`${r.unknown_items} unknown probability · ${r.unquantified_items} unquantified`} />
            </div>
          </Panel>
          <Panel title="Adjudication" className="mb-4" action={editing ? <button className="btn btn-ghost !py-1" onClick={() => { if (window.confirm("Switch the adjudication off? The selected amount stays as a plain reserve line.")) remove("reserve", "setup"); }}>Switch off</button> : undefined}>
            <div className="grid gap-4 text-sm sm:grid-cols-2">
              <div><div className="label">Selected reserve, excl. overhead and margin ($)</div><div className="mt-1">{B("selected", "selected reserve", "number", "w-40")}</div></div>
              <div className="grid grid-cols-2 gap-3">
                <div><div className="label">Adjudicated by</div><div className="mt-1">{B("adjudicated_by", "adjudicated by")}</div></div>
                <div><div className="label">Date</div><div className="mt-1">{B("adjudicated_on", "adjudicated on", "text", "w-32")}</div></div>
              </div>
              <div className="sm:col-span-2"><div className="label">Why this reserve is reasonable</div><div className={`mt-1 ${wrap}`}>{B("selected_basis", "rationale", "textarea")}</div></div>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">The reserve is a fixed amount for this revision. It does not grow when other lines change; re-adjudicate under change control when a material item resolves. When a risk resolves adversely, price the actual consequence in the right place and reassess what remains.</p>
          </Panel>
          {r.items.length === 0 ? <Empty title="No unresolved items recorded" body={editing ? "Use Add item to record what cannot realistically be closed out before the price goes in." : "Press Edit to record the unresolved items behind the reserve."} /> : (
            <Panel flush>
              <div className="grid-scroll">
                <table className="grid-table min-w-[64rem]">
                  <thead><tr><th className="w-20">Ref</th><th className="w-64">Unresolved item</th><th className="w-36 text-right">Extra cost if adverse</th><th className="w-32">Probability</th><th className="w-28">Evidence</th><th className="w-44 text-right">Weighted (tender effect)</th><th className="w-28">Counted?</th><th className="w-24">Status</th>{editing && <th className="w-12" />}</tr></thead>
                  <tbody>
                    {r.items.map((x) => (
                      <Fragment key={x.id}>
                        <tr className="cursor-pointer" onClick={() => setOpen(open === x.id ? null : x.id)}>
                          <td className="font-mono text-xs">{x.ref}</td>
                          <td className={wrap}>{E(x, "title", "item", { kind: "textarea" })}{x.source_ref && <div className="text-xs text-muted-foreground">{x.source_ref}</div>}</td>
                          <td className="num">{editing ? E(x, "impact", "extra cost", { kind: "number", width: "w-28" }) : x.impact_status === "Unquantified" || x.impact === "" ? "Unquantified" : `${fmtMoney(Number(x.impact))} ${x.basis.toLowerCase()}`}</td>
                          <td>{editing ? <div className="flex gap-1">{E(x, "probability_low", "probability low", { kind: "number", width: "w-16" })}{E(x, "probability_high", "probability high", { kind: "number", width: "w-16" })}</div> : x.probability_low === "" ? "—" : x.probability_low === x.probability_high ? pct(x.probability_low) : `${pct(x.probability_low)} – ${pct(x.probability_high)}`}</td>
                          <td>{E(x, "prob_status", "probability evidence", { kind: "select", options: opt(["GREEN", "AMBER", "UNKNOWN"]) })}</td>
                          <td className="num">{x.weighted_low_sell === null ? <span title={x.reasons.join("; ")}>—</span> : x.weighted_low_sell === x.weighted_high_sell ? money(x.weighted_low_sell) : `${money(x.weighted_low_sell)} – ${money(x.weighted_high_sell)}`}</td>
                          <td className="text-sm">{x.counted ? "Yes" : <span title={x.reasons.join("; ")}>No</span>}</td>
                          <td title={x.reasons.join("; ")}><Chip tone={TONE[x.status]}>{x.status === "RED" ? "Hold" : x.status}</Chip></td>
                          {editing && <td><button className="btn btn-ghost !px-2 !py-1" aria-label={`Delete ${x.ref}`} onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete ${x.ref}? You can undo this before saving.`)) remove("reserve_item", x.id); }}>×</button></td>}
                        </tr>
                        {open === x.id && (
                          <tr><td colSpan={editing ? 9 : 8} className="bg-muted/40">
                            <div className="grid gap-4 p-3 text-sm sm:grid-cols-2 lg:grid-cols-3" onClick={(e) => e.stopPropagation()}>
                              {x.reasons.length > 0 && <div className="sm:col-span-2 lg:col-span-3"><div className="label">Notes</div><ul className="list-inside list-disc">{x.reasons.map((q) => <li key={q}>{q}</li>)}</ul></div>}
                              <div><div className="label">Description</div><div className={wrap}>{E(x, "description", "description", { kind: "textarea" })}</div></div>
                              <div><div className="label">Why that probability</div><div className={wrap}>{E(x, "prob_basis", "probability basis", { kind: "textarea" })}</div></div>
                              <div><div className="label">Where it comes from</div>{E(x, "source_ref", "source reference")}</div>
                              <div><div className="label">Entered as</div>{E(x, "basis", "basis", { kind: "select", options: opt(["Sell", "Cost"]) })}</div>
                              <div><div className="label">Consequence status</div>{E(x, "impact_status", "impact status", { kind: "select", options: opt(["Quantified", "Proxy", "Unquantified"]) })}</div>
                              <div><div className="label">Cost owner / overlap group</div><div className="flex gap-2">{E(x, "owner", "owner", { kind: "select", options: opt(["Primary", "Contributing", "Reference Only"]) })}{E(x, "overlap_group", "overlap group", { width: "w-32" })}</div></div>
                              <div><div className="label">Linked Risk Truth exposure (so it is not counted twice)</div>{E(x, "exposure_ref", "risk truth exposure", { width: "w-32" })}</div>
                              <div><div className="label">Close-out action</div><div className={wrap}>{E(x, "action", "action", { kind: "textarea" })}</div></div>
                              <div><div className="label">Weighted, as cost (before overhead and margin)</div><div className="num !text-left">{x.weighted_low === null ? "—" : x.weighted_low === x.weighted_high ? money(x.weighted_low) : `${money(x.weighted_low)} – ${money(x.weighted_high)}`}</div>{x.sensitivity !== null && <div className="text-xs text-muted-foreground">Full consequence as a sensitivity: {money(x.sensitivity)}</div>}</div>
                            </div>
                          </td></tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}
      <AddDialog open={adding} onClose={() => setAdding(false)} onAdd={(p) => add("reserve_item", mid(), p)} />
    </>
  );
}
