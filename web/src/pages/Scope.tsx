import { Fragment, useState, type FormEvent } from "react";
import type { Estimate, ScopeItem } from "../lib/types";
import { EditField } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { useEdit } from "../lib/edit";

const GROUPS = ["Permanent works", "Enabling works", "Access and site establishment", "Temporary works", "Testing and inspection", "Reinstatement and handover", "Preliminaries and management", "Interface with others", "Other"];
const OWNERS = ["OWN WORKS", "SUBCONTRACT", "CLIENT", "OTHERS", "SHARED", "TBC"];
const TREATMENTS = ["PRICED", "ALLOWANCE", "PC SUM", "EXCLUDED", "BY OTHERS", "UNRESOLVED"];
const opts = (xs: string[], blank: string) => [{ value: "", label: blank }, ...xs.map((x) => ({ value: x, label: x.charAt(0) + x.slice(1).toLowerCase() }))];
const TONE = { COMPLETE: "green", CHECK: "amber", MISSING: "red" } as const;
const sid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "C-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };
const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";

function AddDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (p: Record<string, unknown>) => void }) {
  const blank = { title: "", group: "Permanent works", detail: "", source: "", owner: "OWN WORKS", treatment: "PRICED", cost_refs: "", register_refs: "", quote_refs: "", basis: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim()) return setErr("Describe the requirement.");
    onAdd(f); setF(blank); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a scope requirement" wide>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">One thing the job needs. Say who delivers it and how the price treats it; the platform checks the treatment is backed up.</p>
        <label className="block"><span className="label">Requirement</span><input className={`${field} h-10`} value={f.title} onChange={set("title")} maxLength={300} autoFocus placeholder="e.g. Temporary retaining to the cut face" /></label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Group</span><select className={`${field} h-10`} value={f.group} onChange={set("group")}>{GROUPS.map((g) => <option key={g}>{g}</option>)}</select></label>
          <label className="block"><span className="label">Delivered by</span><select className={`${field} h-10`} value={f.owner} onChange={set("owner")}>{opts(OWNERS, "Choose").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
          <label className="block"><span className="label">Price treatment</span><select className={`${field} h-10`} value={f.treatment} onChange={set("treatment")}>{opts(TREATMENTS, "Choose").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Priced in (QS codes, CA lines)</span><input className={`${field} h-10`} value={f.cost_refs} onChange={set("cost_refs")} maxLength={300} placeholder="EW01, CA09" /></label>
          <label className="block"><span className="label">Register refs</span><input className={`${field} h-10`} value={f.register_refs} onChange={set("register_refs")} maxLength={300} placeholder="A3, EX-02, RFI-05" /></label>
          <label className="block"><span className="label">Quote refs</span><input className={`${field} h-10`} value={f.quote_refs} onChange={set("quote_refs")} maxLength={200} placeholder="Q-02" /></label>
        </div>
        <label className="block"><span className="label">What was priced and why (basis)</span><textarea className={`${field} py-2`} rows={2} value={f.basis} onChange={set("basis")} maxLength={3000} /></label>
        <label className="block"><span className="label">Where the requirement comes from</span><input className={`${field} h-10`} value={f.source} onChange={set("source")} maxLength={500} placeholder="Document, sheet and page" /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add requirement</button></div>
      </form>
    </Modal>
  );
}

export function Scope({ est, goQs }: { est: Estimate; goQs: () => void }) {
  const { editing, add, remove } = useEdit();
  const [adding, setAdding] = useState(false);
  const sc = est.scope ?? { items: [], counts: { COMPLETE: 0, CHECK: 0, MISSING: 0, total: 0 }, by_treatment: {}, unhomed_qs: [], gate: "NOT STARTED - no scope items recorded" };
  const hold = /^HOLD/.test(sc.gate), pass = /^PASS/.test(sc.gate);
  const E = (it: ScopeItem, f: keyof ScopeItem, label: string, o: { kind?: "text" | "textarea" | "select"; width?: string; options?: { value: string; label: string }[] } = {}) => (
    <EditField target="scope" id={it.id} field={f} value={String(it[f] ?? "")} label={`${it.ref} ${label}`} kind={o.kind} options={o.options} width={o.width ?? "w-full"} display={String(it[f] ?? "") ? (o.options ? (String(it[f]).charAt(0) + String(it[f]).slice(1).toLowerCase()) : String(it[f])) : "—"} />
  );
  const groups = GROUPS.filter((g) => sc.items.some((i) => i.group === g)).concat(sc.items.some((i) => !GROUPS.includes(i.group)) ? [""] : []);
  const wrap = "whitespace-pre-line text-sm leading-snug";
  return (
    <>
      <PageHeader title="Scope coverage and interfaces" sub="Everything the job needs, who delivers it and how the price treats it. A detailed estimate is not proof of completeness: every requirement needs an owner and a treatment that is backed up."
        actions={editing ? <button className="btn btn-solid" onClick={() => setAdding(true)}>Add requirement</button> : undefined} />
      <div role="status" className={`mb-4 border px-4 py-3 text-sm ${hold ? "border-red-line bg-red-bg text-red-fg" : pass ? "border-green-line bg-green-bg text-green-fg" : "border-amber-line bg-amber-bg text-amber-fg"}`} data-testid="scope-gate">
        <span className="font-semibold">Scope gate:</span> {sc.gate}
      </div>
      <Panel className="mb-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-5">
          <Stat label="Requirements" value={sc.counts.total} />
          <Stat label="Complete" value={sc.counts.COMPLETE} sub="owner and backed-up treatment" />
          <Stat label="To confirm" value={sc.counts.CHECK} sub="something to check" />
          <Stat label="Missing" value={sc.counts.MISSING} sub="no treatment, or no RFI" />
          <Stat label="Priced, no scope home" value={sc.unhomed_qs.length} sub="QS items not in this schedule" />
        </div>
        {sc.unhomed_qs.length > 0 && (
          <p className="mt-3 text-sm">QS items with a cost that no requirement refers to: {sc.unhomed_qs.map((c) => <Chip key={c} tone="amber">{c}</Chip>)} <button className="underline underline-offset-4" onClick={goQs}>Open QS Takeoff</button></p>
        )}
      </Panel>
      {sc.items.length === 0 ? <Empty title="No scope requirements recorded yet" body={editing ? "Use Add requirement, or draft them from the documents on AI Drafting (choose “Scope requirements”)." : "Press Edit to record what the job needs and how each part is treated."} /> : (
        <Panel flush>
          <div className="grid-scroll">
            <table className="grid-table min-w-[72rem]">
              <thead><tr><th className="min-w-[4.5rem]">Ref</th><th className="min-w-[16rem]">Requirement</th><th className="min-w-[8rem]">Delivered by</th><th className="min-w-[8rem]">Treatment</th><th className="min-w-[8rem]">Priced in</th><th className="min-w-[8rem]">Register</th><th className="min-w-[6rem]">Quotes</th><th className="min-w-[14rem]">Basis</th><th className="min-w-[9rem]">Status</th>{editing && <th />}</tr></thead>
              <tbody>
                {groups.map((g) => (
                  <Fragment key={g || "other"}>
                    <tr><td colSpan={editing ? 10 : 9} className="bg-muted text-xs font-semibold uppercase tracking-wider">{g || "Other"}</td></tr>
                    {sc.items.filter((i) => (GROUPS.includes(i.group) ? i.group : "") === g).map((it) => (
                      <tr key={it.id} data-testid="scope-row">
                        <td className="font-mono text-xs">{E(it, "ref", "reference", { width: "w-20" })}</td>
                        <td className={wrap}><div className="font-medium">{E(it, "title", "requirement", { kind: "textarea" })}</div>{(it.source || editing) && <div className="mt-1 text-xs text-muted-foreground">{E(it, "source", "source", { kind: "textarea" })}</div>}</td>
                        <td>{E(it, "owner", "owner", { kind: "select", options: opts(OWNERS, "—"), width: "w-32" })}</td>
                        <td>{E(it, "treatment", "treatment", { kind: "select", options: opts(TREATMENTS, "—"), width: "w-32" })}</td>
                        <td className="font-mono text-xs">{E(it, "cost_refs", "priced in", { width: "w-28" })}</td>
                        <td className="font-mono text-xs">{E(it, "register_refs", "register refs", { width: "w-28" })}</td>
                        <td className="font-mono text-xs">{E(it, "quote_refs", "quote refs", { width: "w-20" })}</td>
                        <td className={wrap}>{E(it, "basis", "basis", { kind: "textarea" })}</td>
                        <td><Chip tone={TONE[it.status ?? "MISSING"]}>{(it.status ?? "").charAt(0) + (it.status ?? "").slice(1).toLowerCase()}</Chip>
                          {(it.problems ?? []).map((p) => <div key={p} className="mt-1 text-xs text-muted-foreground">{p}</div>)}</td>
                        {editing && <td><button className="btn btn-ghost !px-2 !py-1" aria-label={`Delete ${it.ref}`} onClick={() => { if (window.confirm(`Delete ${it.ref}? You can undo this before saving.`)) remove("scope", it.id); }}>Delete</button></td>}
                      </tr>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <AddDialog open={adding} onClose={() => setAdding(false)} onAdd={(p) => add("scope", sid(), p)} />
    </>
  );
}
