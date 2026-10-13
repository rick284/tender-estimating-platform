import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import type { Estimate } from "../lib/types";
import { fmtMoney } from "../lib/format";
import { EditField } from "../components/EditCells";
import { useEdit } from "../lib/edit";
import { Chip, Empty, Money, PageHeader, Panel } from "../components/ui";
import { Modal } from "../components/Modal";
import { Basis } from "./Tender";

type Line = Estimate["commercial"][number];

const GROUPS: { id: string; title: string; hint: string; pick: (c: Line) => boolean }[] = [
  { id: "pre", title: "Allowances added before overhead and margin", hint: "Added to the base direct cost. Overhead and margin are then charged on them. Your own allowances (CX) can be added and removed here; the platform lines (CA) can be switched off but not removed.", pick: (c) => c.stage === "pre" },
  { id: "commercial", title: "Overhead, profit, bonds and finance", hint: "Company overhead (CA17), margin (CA18), bonds (CA19), retention finance (CA20) and GST (CA21).", pick: (c) => c.stage === "commercial" },
  { id: "cashflow", title: "Retention (cash-flow visibility only)", hint: "These do not change the price. They show what is withheld over the job.", pick: (c) => c.stage === "cashflow" },
];
// Lines whose amount is worked out on another page: say where to change them
const ELSEWHERE: Record<string, string> = { CA01: "Risk Truth page", CA02: "Risk Truth page", CA10: "Weather Risk page", CA16: "Management Reserve page" };

const nextRef = (lines: Line[]) => {
  let n = 1;
  while (lines.some((c) => c.ref === `CX${String(n).padStart(2, "0")}`)) n++;
  return `CX${String(n).padStart(2, "0")}`;
};

function AddDialog({ open, onClose, lines }: { open: boolean; onClose: () => void; lines: Line[] }) {
  const { add } = useEdit();
  const [f, setF] = useState({ name: "", method: "%", value: "", note: "" });
  const [err, setErr] = useState("");
  const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const name = f.name.trim();
    if (!name) return setErr("Give the allowance a name, e.g. Temporary works.");
    if (lines.some((c) => c.name.toLowerCase() === name.toLowerCase())) return setErr("There is already a commercial line with that name.");
    const v = Number(f.value);
    if (f.value.trim() === "" || !Number.isFinite(v) || v < 0) return setErr(f.method === "%" ? "Enter the percentage, e.g. 1.5" : "Enter the amount in dollars, e.g. 5000");
    add("commercial", nextRef(lines), { name, method: f.method, include: "Yes", note: f.note.trim(), ...(f.method === "%" ? { pct: String(Number((v / 100).toFixed(8))) } : { pc_sum: String(v) }) });
    setF({ name: "", method: "%", value: "", note: "" }); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add an allowance">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">It is added to the base direct cost before overhead and margin, and appears in the Tender Build-Up, the price schedule and the report.</p>
        <label className="block"><span className="label">Name</span><input className={`${field} h-10`} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={80} autoFocus placeholder="e.g. Temporary works" /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Basis</span>
            <select className={`${field} h-10`} value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })}><option value="%">Percentage of base direct</option><option value="PC Sum">PC sum ($)</option></select></label>
          <label className="block"><span className="label">{f.method === "%" ? "Percentage (%)" : "Amount ($)"}</span>
            <input className={`${field} h-10 text-right font-mono`} inputMode="decimal" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></label>
        </div>
        <label className="block"><span className="label">Note (what it covers and why)</span><textarea className={`${field} py-2`} rows={3} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} maxLength={500} /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add allowance</button></div>
      </form>
    </Modal>
  );
}

export function Commercial({ est }: { est: Estimate }) {
  const { editing, remove } = useEdit();
  const [adding, setAdding] = useState(false);
  const lines = est.commercial;
  return (
    <>
      <PageHeader title="Commercial" sub="Where the commercial lines are set up: switch them on or off, choose the basis, set the rate or amount, describe them and add your own allowances. Everything here flows to the Tender Build-Up, the price schedule and the report."
        actions={editing ? <button className="btn btn-solid" onClick={() => setAdding(true)} data-testid="add-allowance"><Plus size={14} aria-hidden />Add allowance</button> : undefined} />
      {lines.length === 0 ? <Empty title="No commercial lines" body="This estimate has no commercial inputs." /> : GROUPS.map((g) => {
        const rows = lines.filter(g.pick);
        if (!rows.length) return null;
        return (
          <Panel key={g.id} className="mb-4" title={g.title} flush>
            <p className="border-b px-4 py-2 text-xs text-muted-foreground">{g.hint}</p>
            <div className="grid-scroll">
              <table className="grid-table min-w-[66rem]">
                <thead><tr><th className="w-24">Ref</th><th className="min-w-[18rem]">Description</th><th className="min-w-[26rem]">On / basis / rate</th><th className="min-w-[18rem]">Note</th><th className="w-36 text-right">Amount</th>{editing && <th className="w-24" />}</tr></thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.ref} className={c.include ? "" : "text-muted-foreground"} data-testid={`line-${c.ref}`}>
                      <td className="nowrap whitespace-nowrap font-mono text-xs">{c.ref}{c.custom && <> <Chip tone="neutral">Yours</Chip></>}</td>
                      <td>
                        <EditField target="commercial" id={c.ref} field="name" value={c.name} width="w-full" label={`${c.ref} description`} display={<span className="font-medium">{c.name}</span>} />
                        {ELSEWHERE[c.ref] && <div className="mt-0.5 text-xs text-muted-foreground">Amount set on the {ELSEWHERE[c.ref]}</div>}
                      </td>
                      <td><Basis c={c} /></td>
                      <td className="text-sm leading-snug"><EditField target="commercial" id={c.ref} field="note" value={c.note ?? ""} kind="textarea" rows={2} width="w-full" label={`${c.ref} note`} display={c.note ? <span className="whitespace-pre-line">{c.note}</span> : <span className="text-muted-foreground">—</span>} /></td>
                      <td className="num"><Money v={c.include ? c.amount : null} dash0 /></td>
                      {editing && <td>{c.custom && <button className="btn btn-ghost !px-2 !py-1" aria-label={`Remove ${c.ref} ${c.name}`} onClick={() => { if (window.confirm(`Remove ${c.ref} ${c.name} (${fmtMoney(c.amount)})? You can undo this before saving.`)) remove("commercial", c.ref); }}>Remove</button>}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        );
      })}
      <AddDialog open={adding} onClose={() => setAdding(false)} lines={lines} />
    </>
  );
}
