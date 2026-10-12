import { Fragment, useState, type FormEvent } from "react";
import type { Estimate, RiskExposure, RiskMode } from "../lib/types";
import { EditField } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { fmtMoney } from "../lib/format";
import { useEdit } from "../lib/edit";

const xid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "X-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };
const MODES: RiskMode[] = ["Already in Base / No Add", "Unit Rate Delta", "Probability x Impact", "Scenario Weighted", "Fixed Allowance", "Specialist Engine", "By Others / Excluded", "RFI Hold"];
const opt = (xs: string[], blank = "") => [...(blank ? [{ value: "", label: blank }] : []), ...xs.map((x) => ({ value: x, label: x }))];
const STATUS_TONE = { RED: "red", AMBER: "amber", GREEN: "green" } as const;

function AddDialog({ open, onClose, onAdd, risks }: { open: boolean; onClose: () => void; onAdd: (p: Record<string, unknown>) => void; risks: { ref: string; title: string }[] }) {
  const blank = { risk_id: "", consequence: "", cost_ref: "", treatment: "", mode: "Already in Base / No Add" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.consequence.trim()) return setErr("Describe the cost consequence this exposure covers.");
    onAdd({ ...f, evidence: "AMBER", include: "No" }); setF(blank); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a risk exposure">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">An exposure is one cost consequence of a risk. Say where it is <strong>already priced</strong>; only a distinct residual that is not priced anywhere else ever adds cost, and only after you approve it.</p>
        <label className="block"><span className="label">Which risk?</span>
          <select className={`${field} h-10`} value={f.risk_id} onChange={set("risk_id")}>
            <option value="">(not linked to a risk)</option>
            {risks.map((r) => <option key={r.ref} value={r.ref}>{r.ref} · {r.title.slice(0, 70)}</option>)}
          </select></label>
        <label className="block"><span className="label">Cost consequence</span><textarea className={`${field} py-2`} rows={2} value={f.consequence} onChange={set("consequence")} maxLength={1500} autoFocus /></label>
        <label className="block"><span className="label">Already priced at (QS codes or cost lines)</span><input className={`${field} h-10`} value={f.cost_ref} onChange={set("cost_ref")} maxLength={200} placeholder="e.g. EW02 / ES03 / CA10" /></label>
        <label className="block"><span className="label">How the existing price treats it</span><textarea className={`${field} py-2`} rows={2} value={f.treatment} onChange={set("treatment")} maxLength={1500} placeholder="e.g. $40k PC sum retained; supplier quote Q-01 covers 44m" /></label>
        <label className="block"><span className="label">Calculation mode</span><select className={`${field} h-10`} value={f.mode} onChange={set("mode")}>{MODES.map((m) => <option key={m}>{m}</option>)}</select></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button type="submit" className="btn btn-solid">Add exposure</button></div>
      </form>
    </Modal>
  );
}

export function RiskTruth({ est }: { est: Estimate }) {
  const { editing, add, remove } = useEdit();
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const rt = est.risk_truth;
  const xs = rt?.exposures ?? [];
  const risks = est.register.filter((r) => r.kind === "risk").map((r) => ({ ref: r.ref, title: r.title }));
  const E = (x: RiskExposure, f: keyof RiskExposure, label: string, o: { kind?: "text" | "textarea" | "number" | "select"; width?: string; options?: { value: string; label: string }[] } = {}) => (
    <EditField target="exposure" id={x.id} field={f} value={String(x[f] ?? "")} label={`${x.ref} ${label}`} kind={o.kind} options={o.options} width={o.width ?? "w-full"} display={String(x[f] ?? "") || "—"} />
  );
  const hold = rt?.gate.startsWith("HOLD");
  const wrap = "whitespace-pre-line text-sm leading-snug";
  return (
    <>
      <PageHeader title="Risk Truth" sub="Where every material risk is already priced, and the only part of it that adds cost. Likelihood and impact never create dollars; a residual only counts once it is evidenced, distinct, and approved."
        actions={editing ? <button className="btn btn-solid" onClick={() => setAdding(true)}>Add exposure</button> : undefined} />
      {xs.length === 0 ? (
        <Empty title="Risk Truth is not set up for this tender" body={editing ? "Use Add exposure to record where a risk is already priced and whether any distinct residual remains." : "Press Edit to record where each risk is already priced. Until then the risk allowances CA01 and CA02 stay at zero."} />
      ) : (
        <>
          <div className={`mb-4 border px-4 py-3 ${hold ? "border-red-line bg-red-bg text-red-fg" : "border-green-line bg-green-bg text-green-fg"}`} role="status">
            <div className="flex flex-wrap items-center gap-3">
              <Chip tone={hold ? "red" : "green"}>{hold ? "Release hold" : "Release gate passed"}</Chip>
              <span className="text-sm font-medium">{hold ? "Final release is blocked until the red items are resolved, excluded or formally accepted." : "No red items, no duplicate costs, and every provision is integrated."}</span>
            </div>
            <ul className="mt-2 list-inside list-disc text-sm">
              <li>{rt.red_risks} red risk(s) and {rt.red_exposures} red exposure(s); {rt.amber_exposures} amber.</li>
              <li>Duplicate-cost check: {rt.duplicate_gate === "OK" ? "clear" : "RED, the same cost is covered twice or a provision is not distinct"}.</li>
              {rt.issues.map((i) => <li key={i}>{i}</li>)}
            </ul>
          </div>
          <Panel className="mb-4">
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
              <Stat label="CA01 design / scope residual" value={fmtMoney(rt.ca01)} sub="Added before overhead and margin" />
              <Stat label="CA02 construction residual" value={fmtMoney(rt.ca02)} sub="Added before overhead and margin" />
              <Stat label="Exposures" value={xs.length} sub={`${xs.filter((x) => x.addition > 0).length} adding cost`} />
              <Stat label="Priced elsewhere" value={xs.filter((x) => x.mode === "Already in Base / No Add").length} sub="Already in the estimate, nothing added" />
            </div>
          </Panel>
          <Panel flush>
            <div className="grid-scroll">
              <table className="grid-table min-w-[86rem]">
                <thead><tr><th className="min-w-[6rem]">Ref</th><th className="min-w-[18rem]">Exposure</th><th className="min-w-[14rem]">Already priced at</th><th className="min-w-[12rem]">Calculation</th><th className="min-w-[7rem] text-right">Provision</th><th className="min-w-[5rem]">Adds cost?</th><th className="min-w-[12rem]">Aimed at</th><th className="min-w-[7rem]">Evidence</th><th className="min-w-[7rem]">Status</th>{editing && <th className="min-w-[3rem]" />}</tr></thead>
                <tbody>
                  {xs.map((x) => (
                    <Fragment key={x.id}>
                      <tr className="cursor-pointer" onClick={() => setOpen(open === x.id ? null : x.id)}>
                        <td className="font-mono text-xs">{x.ref}</td>
                        <td className={wrap}>{E(x, "consequence", "consequence", { kind: "textarea" })}</td>
                        <td className={wrap}>{E(x, "cost_ref", "cost reference", { kind: "textarea" })}</td>
                        <td>{E(x, "mode", "calculation mode", { kind: "select", options: opt(MODES) })}</td>
                        <td className="num">{editing ? E(x, "provision", "provision", { kind: "number", width: "w-24" }) : (x.provision ? fmtMoney(Number(x.provision)) : "—")}</td>
                        <td>{E(x, "include", "include new risk cost", { kind: "select", options: opt(["Yes", "No"]) })}</td>
                        <td>{E(x, "target", "integration target", { kind: "select", options: opt(["CA01", "CA02", ...(x.target && !["CA01", "CA02", ""].includes(x.target) ? [x.target] : [])], "(none)") })}</td>
                        <td>{E(x, "evidence", "evidence status", { kind: "select", options: opt(["GREEN", "AMBER", "RED"], "(not set)") })}</td>
                        <td title={x.reasons.join("; ")}><Chip tone={STATUS_TONE[x.status]}>{x.status}</Chip></td>
                        {editing && <td><button className="btn btn-ghost !px-2 !py-1" aria-label={`Delete ${x.ref}`} onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete ${x.ref}? You can undo this before saving.`)) remove("exposure", x.id); }}>×</button></td>}
                      </tr>
                      {open === x.id && (
                        <tr><td colSpan={editing ? 10 : 9} className="bg-muted/40">
                          <div className="grid gap-4 p-3 text-sm sm:grid-cols-2 lg:grid-cols-3" onClick={(e) => e.stopPropagation()}>
                            {x.reasons.length > 0 && <div className="sm:col-span-2 lg:col-span-3"><div className="label">Why {x.status}</div><ul className="list-inside list-disc">{x.reasons.map((r) => <li key={r}>{r}</li>)}</ul></div>}
                            <div><div className="label">Risk</div>{E(x, "risk_id", "risk id", { width: "w-24" })}</div>
                            <div><div className="label">How the existing price treats it</div><div className={wrap}>{E(x, "treatment", "treatment", { kind: "textarea" })}</div></div>
                            <div><div className="label">Residual after the existing price</div><div className={wrap}>{E(x, "residual", "residual", { kind: "textarea" })}</div></div>
                            <div><div className="label">Cost treatment owner</div>{E(x, "owner", "owner", { kind: "select", options: opt(["Primary", "Contributing", "Reference Only"], "(not set)") })}</div>
                            <div><div className="label">Residual distinct?</div>{E(x, "distinct", "residual distinct", { kind: "select", options: opt(["Yes", "No", "N/A"], "(not set)") })}</div>
                            <div><div className="label">Integration complete?</div>{E(x, "integration_complete", "integration complete", { kind: "select", options: opt(["Yes", "No", "N/A"], "(not set)") })}</div>
                            <div><div className="label">Overlap group</div>{E(x, "overlap_group", "overlap group")}</div>
                            <div><div className="label">Already embedded in productivity / waste / prelims?</div>{E(x, "embedded", "embedded variability", { kind: "textarea" })}</div>
                            <div><div className="label">Evidence note</div>{E(x, "evidence_note", "evidence note", { kind: "textarea" })}</div>
                            <div><div className="label">Quantity · unit · rate (Unit Rate Delta)</div><div className="flex gap-2">{E(x, "qty", "quantity", { kind: "number", width: "w-20" })}{E(x, "unit", "unit", { width: "w-16" })}{E(x, "unit_rate", "unit rate", { kind: "number", width: "w-24" })}</div></div>
                            <div><div className="label">Probability · impact (Probability x Impact)</div><div className="flex gap-2">{E(x, "probability", "probability", { kind: "number", width: "w-20" })}<span className="text-xs text-muted-foreground self-center">0 to 1; impact goes in unit rate</span></div></div>
                            <div><div className="label">Modelled residual</div><div className="num !text-left">{x.modelled === null ? "—" : fmtMoney(x.modelled)}</div></div>
                            <div><div className="label">Sensitivity / basis</div><div className={wrap}>{E(x, "basis", "basis", { kind: "textarea" })}</div></div>
                            <div><div className="label">Firm-up / rerun action</div><div className={wrap}>{E(x, "action", "action", { kind: "textarea" })}</div></div>
                            <div><div className="label">Source</div><div className={wrap}>{E(x, "source", "source", { kind: "textarea" })}</div></div>
                          </div>
                        </td></tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
      <AddDialog open={adding} onClose={() => setAdding(false)} onAdd={(p) => add("exposure", xid(), p)} risks={risks} />
    </>
  );
}
