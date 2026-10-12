import { useState, type FormEvent } from "react";
import type { Estimate, QuoteItem } from "../lib/types";
import { EditField } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Empty, PageHeader, Panel, Stat } from "../components/ui";
import { fmtMoney } from "../lib/format";
import { useEdit } from "../lib/edit";

const qid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "S-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };

function AddDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (payload: Record<string, unknown>) => void }) {
  const blank = { supplier: "", package: "", estimate_ref: "", amount: "", qty: "", unit: "", status: "", notes: "", source: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.supplier.trim() && !f.package.trim()) return setErr("Name the package or the supplier.");
    if (f.amount.trim() && !Number.isFinite(Number(f.amount.replace(/[$,]/g, "")))) return setErr("The amount needs a number.");
    onAdd(f); setF(blank); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add supplier or subcontractor quote">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">Record a quote or supplier price and where the evidence lives. A quote is evidence, not automatically the amount the tender uses: scope, quantity, exclusions, validity and duplication must reconcile first.</p>
        <label className="block"><span className="label">Supplier</span><input className={`${field} h-10`} value={f.supplier} onChange={set("supplier")} maxLength={200} autoFocus /></label>
        <label className="block"><span className="label">Package or item</span><input className={`${field} h-10`} value={f.package} onChange={set("package")} maxLength={200} placeholder="e.g. 13MPa no-fines concrete" /></label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Amount excl. GST</span><input className={`${field} h-10`} inputMode="decimal" value={f.amount} onChange={set("amount")} /></label>
          <label className="block"><span className="label">Quantity</span><input className={`${field} h-10`} value={f.qty} onChange={set("qty")} maxLength={30} /></label>
          <label className="block"><span className="label">Unit</span><input className={`${field} h-10`} value={f.unit} onChange={set("unit")} maxLength={20} /></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Feeds QS items</span><input className={`${field} h-10`} value={f.estimate_ref} onChange={set("estimate_ref")} maxLength={120} placeholder="e.g. RW04" /></label>
          <label className="block"><span className="label">Status</span><input className={`${field} h-10`} value={f.status} onChange={set("status")} maxLength={300} placeholder="e.g. RECEIVED" /></label>
        </div>
        <label className="block"><span className="label">Notes (quote number, date, what it says)</span><textarea className={`${field} py-2`} rows={3} value={f.notes} onChange={set("notes")} maxLength={3000} /></label>
        <label className="block"><span className="label">Where the evidence is</span><input className={`${field} h-10`} value={f.source} onChange={set("source")} maxLength={500} placeholder="Drive file, email, or quote number" /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add quote</button></div>
      </form>
    </Modal>
  );
}

export function Quotes({ est }: { est: Estimate }) {
  const { editing, add, remove } = useEdit();
  const [adding, setAdding] = useState(false);
  const quotes = est.quotes ?? [];
  const total = quotes.reduce((a, q) => a + (Number(q.amount) || 0), 0);
  const E = (q: QuoteItem, f: keyof QuoteItem, label: string, o: { kind?: "text" | "textarea" | "number"; width?: string } = {}) => (
    <EditField target="quote" id={q.id} field={f} value={q[f]} label={`${q.ref} ${label}`} kind={o.kind} width={o.width ?? "w-full"} display={q[f] || "—"} />
  );
  const wrap = "whitespace-pre-line text-sm leading-snug";
  return (
    <>
      <PageHeader title="Supplier and subcontractor quotes" sub="The evidence behind the rates and packages in the price. A quote is evidence, not automatically the controlling tender amount."
        actions={editing ? <button className="btn btn-solid" onClick={() => setAdding(true)}>Add quote</button> : undefined} />
      <Panel className="mb-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-3">
          <Stat label="Quotes recorded" value={quotes.length} />
          <Stat label="Value of quotes with an amount" value={fmtMoney(total)} sub="Not a tender total: some quotes overlap or are references only" />
          <Stat label="Without a recorded source" value={quotes.filter((q) => !q.source).length} sub="Add where each piece of evidence is filed" />
        </div>
      </Panel>
      {quotes.length === 0 ? <Empty title="No quotes recorded yet" body={editing ? "Use Add quote to record a supplier or subcontractor price." : "Press Edit to record the supplier and subcontractor quotes behind this price."} /> : (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="grid-table min-w-[64rem]">
              <thead><tr><th className="min-w-[4rem]">Ref</th><th className="min-w-[12rem]">Package</th><th className="min-w-[11rem]">Supplier</th><th className="min-w-[6rem]">QS items</th><th className="min-w-[7rem] text-right">Amount</th><th className="min-w-[10rem]">Status</th><th className="min-w-[18rem]">Notes and action</th><th className="min-w-[11rem]">Evidence</th>{editing && <th />}</tr></thead>
              <tbody>
                {quotes.map((q) => (
                  <tr key={q.id}>
                    <td className="font-mono text-xs">{E(q, "ref", "reference", { width: "w-14" })}</td>
                    <td className="font-medium">{E(q, "package", "package", { kind: "textarea" })}</td>
                    <td className={wrap}>{E(q, "supplier", "supplier", { kind: "textarea" })}</td>
                    <td>{E(q, "estimate_ref", "QS items", { width: "w-20" })}</td>
                    <td className="num">{editing ? E(q, "amount", "amount", { kind: "number", width: "w-24" }) : (q.amount ? fmtMoney(Number(q.amount)) : "—")}</td>
                    <td className={wrap}>{E(q, "status", "status", { kind: "textarea" })}</td>
                    <td className={wrap}>{E(q, "notes", "notes", { kind: "textarea" })}{(q.action || editing) && <div className="mt-1 text-xs text-muted-foreground">{E(q, "action", "action", { kind: "textarea" })}</div>}</td>
                    <td className={wrap}>{E(q, "source", "evidence source", { kind: "textarea" })}</td>
                    {editing && <td><button className="btn btn-ghost !px-2 !py-1" aria-label={`Delete ${q.ref}`} onClick={() => { if (window.confirm(`Delete ${q.ref}? You can undo this before saving.`)) remove("quote", q.id); }}>Delete</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <AddDialog open={adding} onClose={() => setAdding(false)} onAdd={(p) => add("quote", qid(), p)} />
    </>
  );
}
