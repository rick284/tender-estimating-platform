import { useEffect, useState, type FormEvent } from "react";
import type { PriceSchedule, ScheduleSource } from "../lib/types";
import { fmtMoney } from "../lib/format";
import { Modal } from "./Modal";

const input = "mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary";
const Err = ({ msg }: { msg: string }) => (msg ? <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{msg}</div> : null);

const EXAMPLE = `# MAIN BUILDING | A
MB/001  Excavation
MB/002  Concrete
MB/025  Preliminaries & General  [pg]
MB/026  Margin  [margin]
# CIVIL WORKS | B
CW/001  Site Preparation/Silt Fencing
CW/002  Bulk Earthworks
CW/012  Preliminaries & General  [pg]
CW/013  Margin  [margin]`;

/** Paste the client's schedule lines (e.g. copied from their Excel). */
export function ScheduleFormatDialog({ open, onClose, current, onAdd }: {
  open: boolean; onClose: () => void; current: PriceSchedule; onAdd: (payload: Record<string, unknown>) => void;
}) {
  const [f, setF] = useState({ text: "", name: "", client: "" });
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setF({ text: "", name: current.auto ? "" : current.name, client: current.client }); setErr(""); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.text.trim()) return setErr("Paste the client's schedule lines first.");
    if (!f.text.trim().startsWith("#")) return setErr("Start with a group heading, for example: # CIVIL WORKS");
    onAdd({ text: f.text, name: f.name, client: f.client });
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Use the client's price schedule" wide>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">Paste the lines of the client's schedule, one per line: the reference, then the trade name. Put a <code className="font-mono">#</code> heading before each group. Add <code className="font-mono">[pg]</code> to preliminaries lines and <code className="font-mono">[margin]</code> to the line that should carry overhead and profit; a group with no margin line gets one.</p>
        {!current.auto && <p className="border border-amber-line bg-amber-bg px-3 py-2 text-sm text-amber-fg">This replaces the current format. Every item will need mapping to the new lines again.</p>}
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Schedule name</span><input className={input} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={80} placeholder="e.g. Main contract tender submission" /></label>
          <label className="block"><span className="label">Issued by (client)</span><input className={input} value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} maxLength={120} /></label>
        </div>
        <label className="block"><span className="label">Schedule lines</span>
          <textarea className="mt-1 h-56 w-full border bg-background px-3 py-2 font-mono text-xs focus:border-primary" value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} placeholder={EXAMPLE} spellCheck={false} /></label>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Use this format</button></div>
      </form>
    </Modal>
  );
}

type Part = { to: string; amount: string };

/** Split one item's value across several schedule lines. The last part takes whatever is left. */
export function SplitDialog({ open, onClose, source, targets, onSave }: {
  open: boolean; onClose: () => void; source: ScheduleSource | null; targets: PriceSchedule["targets"]; onSave: (json: string) => void;
}) {
  const [parts, setParts] = useState<Part[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!open || !source) return;
    const m = source.map;
    setParts(Array.isArray(m) ? m.map((p) => ({ to: p.to, amount: p.amount ?? "" })) : [{ to: typeof m === "string" ? m : "", amount: "" }, { to: "", amount: "" }]);
    setErr("");
  }, [open, source]);
  if (!source) return null;
  const set = (i: number, k: keyof Part, v: string) => setParts(parts.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  const fixed = parts.slice(0, -1).reduce((a, p) => a + (Number(p.amount) || 0), 0);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (parts.some((p) => !p.to)) return setErr("Choose a line for every part.");
    if (parts.slice(0, -1).some((p) => p.amount.trim() === "" || !Number.isFinite(Number(p.amount)) || Number(p.amount) < 0)) return setErr("Every part except the last needs an amount.");
    if (fixed > source.amount + 0.005) return setErr(`The amounts add up to more than ${fmtMoney(source.amount)}.`);
    onSave(JSON.stringify(parts.map((p, i) => (i === parts.length - 1 ? { to: p.to } : { to: p.to, amount: p.amount.trim() }))));
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Split across schedule lines">
      <form onSubmit={submit} className="space-y-3" noValidate>
        <p className="text-sm"><strong>{source.label}</strong> — {fmtMoney(source.amount)}</p>
        {parts.map((p, i) => (
          <div key={i} className="flex items-center gap-2">
            <select aria-label={`Line for part ${i + 1}`} className={`${input} !mt-0 flex-1`} value={p.to} onChange={(e) => set(i, "to", e.target.value)}>
              <option value="">Choose a line…</option>{targets.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            {i < parts.length - 1
              ? <><span className="text-sm">$</span><input aria-label={`Amount for part ${i + 1}`} className={`${input} !mt-0 w-32 text-right font-mono`} inputMode="decimal" value={p.amount} onChange={(e) => set(i, "amount", e.target.value)} /></>
              : <span className="w-40 text-right text-sm text-muted-foreground">the rest: {fmtMoney(Math.max(0, source.amount - fixed))}</span>}
            {parts.length > 2 && <button type="button" className="btn btn-ghost !px-2 !py-1" aria-label={`Remove part ${i + 1}`} onClick={() => setParts(parts.filter((_, j) => j !== i))}>×</button>}
          </div>
        ))}
        <button type="button" className="btn btn-ghost !py-1" onClick={() => setParts([...parts.slice(0, -1), { to: "", amount: "" }, parts[parts.length - 1]])}>Add a part</button>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Save split</button></div>
      </form>
    </Modal>
  );
}
