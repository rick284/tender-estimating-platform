import { useEffect, useMemo, useState, type FormEvent } from "react";
import { newUid } from "../lib/edit";
import { fmtMoney } from "../lib/format";
import { Modal } from "./Modal";

const BASIS = [
  ["MEASURED", "Measured from a drawing or counted"],
  ["PROVIDED", "Supplied by the client, consultant or supplier"],
  ["CALCULATED", "Worked out from visible inputs"],
  ["ALLOWANCE-PC", "A temporary allowance or PC sum"],
  ["QUOTED", "From a written quotation"],
] as const;
const MODES = [
  ["Time x Count", "Hours from productivity (plant and labour)"],
  ["QS Qty x Factor", "A factor per unit of the QS quantity (materials)"],
  ["Direct Qty", "A quantity you enter"],
  ["Lump Sum / Quote", "A one-off sum or quote"],
] as const;
const CATEGORIES = ["Labour", "Plant", "Material", "Subcontract", "Other"] as const;
const input = "mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary";
const Err = ({ msg }: { msg: string }) => (msg ? <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{msg}</div> : null);

// Next free code for a section: its letter prefix (EW) plus one more than the highest number in use (EW11).
function suggestCode(sec: { section: string; items: string[] } | undefined, used: Set<string>): string {
  if (!sec) return "";
  const parts = sec.items.map((c) => /^([A-Z]+)(\d+)$/.exec(c)).filter((m): m is RegExpExecArray => !!m);
  if (!parts.length) return "";
  const prefix = parts[0][1];
  let n = Math.max(...parts.filter((m) => m[1] === prefix).map((m) => Number(m[2]))) + 1;
  const width = parts[0][2].length;
  while (used.has(prefix + String(n).padStart(width, "0"))) n++;
  return prefix + String(n).padStart(width, "0");
}

export function AddQsDialog({ open, onClose, sections: secs, usedCodes, onAdd }: {
  open: boolean; onClose: () => void; sections: { section: string; items: string[] }[]; usedCodes: Set<string>;
  onAdd: (code: string, payload: Record<string, unknown>, lumpSum: string) => void;
}) {
  const sections = secs.map((x) => x.section);
  const codeFor = (section: string) => suggestCode(secs.find((x) => x.section === section), usedCodes);
  const blank = { code: codeFor(sections[0] ?? ""), section: sections[0] ?? "", newSection: "", description: "", unit: "", quantity: "", basis: "", source: "", lump: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setF({ ...blank }); setErr(""); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  // Choosing a section fills in the next code for it (the estimator can still overtype it).
  const pickSection = (e: { target: { value: string } }) => setF({ ...f, section: e.target.value, code: codeFor(e.target.value) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const code = f.code.trim().toUpperCase();
    const section = f.section === "__new" ? f.newSection.trim() : f.section;
    if (!/^[A-Z][A-Z0-9]{1,11}$/.test(code)) return setErr("A QS code is letters and numbers starting with a letter, for example EW11.");
    if (usedCodes.has(code)) return setErr(`QS code ${code} is already used.`);
    if (!section) return setErr("Choose a section or name a new one.");
    if (!f.description.trim() || !f.unit.trim()) return setErr("Add a description and a unit.");
    if (f.quantity.trim() === "" || !Number.isFinite(Number(f.quantity)) || Number(f.quantity) < 0) return setErr("Quantity needs a number that isn't negative.");
    if (!f.basis) return setErr("Classify the quantity (measured, provided, calculated, allowance or quoted).");
    if (f.lump.trim() !== "" && (!Number.isFinite(Number(f.lump)) || Number(f.lump) < 0)) return setErr("The lump sum needs a number that isn't negative.");
    onAdd(code, { section, description: f.description.trim(), unit: f.unit.trim(), quantity: f.quantity.trim(), basis: f.basis, source: f.source.trim() }, f.lump.trim());
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add QS item">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div className="grid grid-cols-[7rem_1fr] gap-3">
          <label className="block"><span className="label">Code</span><input className={`${input} uppercase`} value={f.code} onChange={set("code")} maxLength={12} placeholder="e.g. EW11" /></label>
          <label className="block"><span className="label">Section</span>
            <select className={input} value={f.section} onChange={pickSection}>
              {sections.map((s) => <option key={s} value={s}>{s}</option>)}<option value="__new">New section…</option>
            </select></label>
        </div>
        {f.section === "__new" && <label className="block"><span className="label">New section name</span><input className={input} value={f.newSection} onChange={set("newSection")} maxLength={80} /></label>}
        <label className="block"><span className="label">Description</span><input className={input} value={f.description} onChange={set("description")} maxLength={200} /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Quantity</span><input className={input} inputMode="decimal" value={f.quantity} onChange={set("quantity")} /></label>
          <label className="block"><span className="label">Unit</span><input className={input} value={f.unit} onChange={set("unit")} maxLength={12} placeholder="m2, m3, lm, ea, LS" /></label>
        </div>
        <label className="block"><span className="label">Where does the quantity come from?</span>
          <select className={input} value={f.basis} onChange={set("basis")}>
            <option value="">Choose…</option>{BASIS.map(([v, d]) => <option key={v} value={v}>{v} — {d}</option>)}
          </select></label>
        <label className="block"><span className="label">Source or reference (optional)</span><input className={input} value={f.source} onChange={set("source")} maxLength={300} placeholder="Drawing number, schedule, quote reference" /></label>
        <div className="border bg-muted/50 p-3">
          <label className="block"><span className="label">Price it now as a lump sum (optional)</span>
            <div className="mt-1 flex items-center gap-2"><span className="text-sm">$</span><input className={`${input} !mt-0`} inputMode="decimal" value={f.lump} onChange={set("lump")} placeholder="Leave blank to price it with build-up rows next" /></div></label>
          <p className="mt-2 text-xs text-muted-foreground">A QS item has no cost of its own: its price is the total of its build-up rows. If you leave this blank, the next step lets you add them.</p>
        </div>
        <p className="text-xs text-muted-foreground">New items start as AMBER and not verified until you check them.</p>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add item</button></div>
      </form>
    </Modal>
  );
}

interface Lib { code: string; description: string; unit: string; rate: number; category: string }

export function AddRowDialog({ open, onClose, qs, library, defaultQs, onAdd }: {
  open: boolean; onClose: () => void; qs: { code: string; description: string }[]; library: Lib[]; defaultQs: string;
  onAdd: (uid: string, row: Record<string, unknown>, newRate: { code: string; payload: Record<string, unknown> } | null) => void;
}) {
  const blank = { qs: defaultQs, mode: "Time x Count", resource: "", filter: "", task: "", newRate: false, rc: "", rd: "", ru: "hr", rr: "", rcat: "Plant" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setF({ ...blank, qs: defaultQs && defaultQs !== "all" ? defaultQs : qs[0]?.code ?? "" }); setErr(""); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const shown = useMemo(() => {
    const t = f.filter.trim().toLowerCase();
    return library.filter((l) => !t || `${l.code} ${l.description} ${l.category}`.toLowerCase().includes(t)).slice(0, 200);
  }, [library, f.filter]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.qs) return setErr("Choose the QS item this row belongs to.");
    let resource = f.resource, rate: { code: string; payload: Record<string, unknown> } | null = null;
    if (f.newRate) {
      const code = f.rc.trim().toUpperCase();
      if (!/^[A-Z0-9][A-Z0-9-]{1,23}$/.test(code)) return setErr("A rate code is letters, numbers and dashes, for example PL-EXC-20.");
      if (library.some((l) => l.code === code)) return setErr(`Rate code ${code} already exists.`);
      if (!f.rd.trim() || !f.ru.trim()) return setErr("Add a description and a unit for the new rate.");
      if (f.rr.trim() === "" || !Number.isFinite(Number(f.rr)) || Number(f.rr) < 0) return setErr("The new rate needs a number that isn't negative.");
      rate = { code, payload: { description: f.rd.trim(), unit: f.ru.trim(), base_rate: f.rr.trim(), category: f.rcat } };
      resource = code;
    } else if (!resource && f.mode !== "Lump Sum / Quote") return setErr("Choose a rate from the library, or add a new one. Only a Lump Sum row can go without a rate.");
    const task = f.task.trim() || (f.newRate ? f.rd.trim() : library.find((l) => l.code === resource)?.description ?? "");
    if (!task) return setErr("Add a description for the row.");
    onAdd(newUid(), { qs_code: f.qs, mode: f.mode, resource_code: resource, task }, rate);
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add build-up row">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <label className="block"><span className="label">QS item</span>
          <select className={input} value={f.qs} onChange={set("qs")}>{qs.map((q) => <option key={q.code} value={q.code}>{q.code} · {q.description.slice(0, 60)}</option>)}</select></label>
        <label className="block"><span className="label">How is it calculated?</span>
          <select className={input} value={f.mode} onChange={set("mode")}>{MODES.map(([v, d]) => <option key={v} value={v}>{v} — {d}</option>)}</select></label>
        {!f.newRate ? (
          <div>
            <span className="label">Rate from the library</span>
            <input className={input} placeholder="Search the library" value={f.filter} onChange={set("filter")} aria-label="Search the rate library" />
            <select size={6} className="mt-2 w-full border bg-background text-sm" value={f.resource} onChange={set("resource")} aria-label="Library rate">
              {f.mode === "Lump Sum / Quote" && <option value="">No library rate (priced by a job rate)</option>}
              {shown.map((l) => <option key={l.code} value={l.code}>{l.code} · {l.description} · {fmtMoney(l.rate)}/{l.unit}</option>)}
            </select>
          </div>
        ) : (
          <div className="space-y-3 border p-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="label">Rate code</span><input className={`${input} uppercase`} value={f.rc} onChange={set("rc")} maxLength={24} placeholder="PL-EXC-20" /></label>
              <label className="block"><span className="label">Category</span><select className={input} value={f.rcat} onChange={set("rcat")}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></label>
            </div>
            <label className="block"><span className="label">Description</span><input className={input} value={f.rd} onChange={set("rd")} maxLength={200} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="label">Rate (excl. GST)</span><input className={input} inputMode="decimal" value={f.rr} onChange={set("rr")} /></label>
              <label className="block"><span className="label">Per (unit)</span><input className={input} value={f.ru} onChange={set("ru")} maxLength={12} /></label>
            </div>
            <p className="text-xs text-muted-foreground">New rates are marked as added in the platform with no supplier evidence yet.</p>
          </div>
        )}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.newRate} onChange={(e) => setF({ ...f, newRate: e.target.checked })} /> This rate isn't in the library</label>
        <label className="block"><span className="label">Description of the row</span><input className={input} value={f.task} onChange={set("task")} maxLength={200} placeholder="Leave blank to use the rate's description" /></label>
        <p className="text-xs text-muted-foreground">After adding, fill in productivity or quantity in the row's edit panel.</p>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add row</button></div>
      </form>
    </Modal>
  );
}
