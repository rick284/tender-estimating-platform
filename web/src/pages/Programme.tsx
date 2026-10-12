import { useState, type FormEvent } from "react";
import type { Estimate } from "../lib/types";
import { EditField, EditToggle } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { fmtMoney } from "../lib/format";
import { useEdit } from "../lib/edit";

const pid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "P-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };
const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
const Err = ({ msg }: { msg: string }) => (msg ? <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{msg}</div> : null);

function SetupDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (p: Record<string, unknown>) => void }) {
  const [f, setF] = useState({ start: "", days: "5", hours: "8" });
  const [err, setErr] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.start) return setErr("Enter the assumed start date.");
    onAdd({ start: f.start, days_per_week: f.days, hours_per_day: f.hours }); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Set up the programme">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">Creates one programme task for every QS item. A task's length is its slowest resource row (hours ÷ the working day, rounded up) unless you enter days. Then say which tasks follow which.</p>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Assumed start</span><input type="date" className={`${field} h-10`} value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} autoFocus /></label>
          <label className="block"><span className="label">Days per week</span><input className={`${field} h-10`} inputMode="numeric" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} /></label>
          <label className="block"><span className="label">Hours per day</span><input className={`${field} h-10`} inputMode="numeric" value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} /></label>
        </div>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Set up programme</button></div>
      </form>
    </Modal>
  );
}

function ControlDialog({ open, onClose, onAdd }: { open: boolean; onClose: () => void; onAdd: (p: Record<string, unknown>) => void }) {
  const [f, setF] = useState({ code: "", name: "", days: "", preds: "" });
  const [err, setErr] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$/.test(f.code.trim())) return setErr("A task code is letters, numbers and dashes, for example PRG-CURE.");
    if (!f.name.trim()) return setErr("Give the task a name.");
    if (f.days.trim() === "" || !/^\d+$/.test(f.days.trim())) return setErr("Days needs a whole number.");
    onAdd({ code: f.code.trim(), name: f.name.trim(), override_days: f.days.trim(), predecessors: f.preds }); setF({ code: "", name: "", days: "", preds: "" }); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a programme control task">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">A task with no cost of its own that still takes time, such as a cure period, a re-proof hold or a supplier lead time.</p>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Code</span><input className={`${field} h-10 uppercase`} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} maxLength={20} placeholder="PRG-CURE" autoFocus /></label>
          <label className="block col-span-2"><span className="label">Name</span><input className={`${field} h-10`} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} maxLength={200} /></label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Working days</span><input className={`${field} h-10`} inputMode="numeric" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} /></label>
          <label className="block"><span className="label">Follows (task codes)</span><input className={`${field} h-10`} value={f.preds} onChange={(e) => setF({ ...f, preds: e.target.value })} placeholder="PV01, ES01" /></label>
        </div>
        <Err msg={err} />
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add task</button></div>
      </form>
    </Modal>
  );
}

export function Programme({ est }: { est: Estimate }) {
  const { editing, add, remove } = useEdit();
  const [setup, setSetup] = useState(false);
  const [control, setControl] = useState(false);
  const p = est.programme;

  if (!p?.set_up) {
    return (
      <>
        <PageHeader title="Programme" sub="Task durations, what follows what, and the critical path. It feeds the weather allowance and the MS Project export." />
        <Empty title="No programme yet" body={editing ? "Use Set up the programme to create a task for every QS item, then set the order." : "Press Edit, then Set up the programme to create a task for every QS item."} />
        {editing && <div className="mt-4 flex justify-center"><button className="btn btn-solid" onClick={() => setSetup(true)}>Set up the programme</button></div>}
        <SetupDialog open={setup} onClose={() => setSetup(false)} onAdd={(v) => add("programme", "setup", v)} />
      </>
    );
  }
  const total = Math.max(p.duration, 1);
  const crit = new Set(p.critical_path);
  const E = (id: string, f: string, value: string, label: string, o: { kind?: "text" | "number"; width?: string; placeholder?: string; display?: React.ReactNode } = {}) => (
    <EditField target="programme_task" id={id} field={f} value={value} label={label} kind={o.kind} width={o.width ?? "w-full"} placeholder={o.placeholder} display={o.display} />
  );
  const sections = Array.from(new Set(p.tasks.map((t) => t.section)));
  return (
    <>
      <PageHeader title="Programme" sub="Task durations, what follows what, and the critical path. It feeds the weather allowance and the MS Project export."
        actions={editing ? <button className="btn btn-ghost" onClick={() => setControl(true)}>Add control task</button> : undefined} />
      <Panel className="mb-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
          <Stat label="Dry duration" value={`${p.duration} WD`} sub={p.finish ? `finishes ${p.finish}` : "set a start date for finish dates"} />
          <Stat label="Assumed start" value={<EditField target="programme" id="config" field="start" kind="text" value={p.start} label="Programme start" width="w-40" display={p.start || "—"} />} />
          <Stat label="Working week" value={<span className="inline-flex items-center gap-1"><EditField target="programme" id="config" field="days_per_week" kind="number" value={String(p.days_per_week)} label="Days per week" width="w-14" /> days ×
            <EditField target="programme" id="config" field="hours_per_day" kind="number" value={String(p.hours_per_day)} label="Hours per day" width="w-14" /> h</span>} />
          <Stat label="Critical path" value={`${p.critical_path.length} tasks`} />
        </div>
        {p.critical_path.length > 0 && <p className="mt-4 text-sm"><span className="label mr-2">Controlling path</span><span className="font-mono text-xs">{p.critical_path.join("  ›  ")}</span></p>}
      </Panel>
      {p.problems.length > 0 && <ul className="mb-4 space-y-1 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{p.problems.map((x) => <li key={x}>{x}</li>)}</ul>}
      {p.missing.length > 0 && (
        <p className="mb-4 flex flex-wrap items-center gap-3 border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">
          {p.missing.length} QS item{p.missing.length === 1 ? " has" : "s have"} no programme task: {p.missing.slice(0, 8).map((m) => m.code).join(", ")}{p.missing.length > 8 ? "…" : ""}.
          {editing && <button className="btn btn-ghost !py-1" onClick={() => p.missing.forEach((m) => add("programme_task", pid(), { code: m.code, name: m.description, qs_code: m.code }))}>Add them</button>}
        </p>
      )}
      <Panel flush>
        <div className="overflow-x-auto">
          <table className="grid-table min-w-[64rem]">
            <thead><tr><th className="w-20">Code</th><th className="min-w-[17rem]">Task</th><th className="w-20 text-right">Days</th><th className="w-32">Follows</th><th className="w-[6.5rem]">Start</th><th className="w-[6.5rem]">Finish</th><th className="w-16 text-right">Float</th><th className="w-[14%] min-w-[7rem]">Timeline ({p.duration} WD)</th><th className="w-32" />{editing && <th className="w-24" />}</tr></thead>
            <tbody>
              {sections.map((sec) => (
                <SectionRows key={sec} sec={sec} tasks={p.tasks.filter((t) => t.section === sec)} total={total} crit={crit} editing={editing} E={E} remove={remove} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="border-t px-4 py-3 text-xs text-muted-foreground">Tasks follow finish-to-start with no lags. A task's days are what you enter, otherwise its slowest resource row ÷ the working day, rounded up (shown beneath when you override it). Tasks marked "runs throughout" (preliminaries) span the job and are not on the critical path. Public holidays and shutdowns are not modelled.</p>
      </Panel>
      <ControlDialog open={control} onClose={() => setControl(false)} onAdd={(v) => add("programme_task", pid(), v)} />
    </>
  );
}

type EFn = (id: string, f: string, value: string, label: string, o?: { kind?: "text" | "number"; width?: string; placeholder?: string; display?: React.ReactNode }) => React.ReactNode;

function SectionRows({ sec, tasks, total, crit, editing, E, remove }: { sec: string; tasks: import("../lib/types").ProgrammeTask[]; total: number; crit: Set<string>; editing: boolean; E: EFn; remove: (t: string, k: string) => void }) {
  return (
    <>
      <tr className="bg-muted/60"><td colSpan={editing ? 10 : 9} className="font-heading text-xs font-bold uppercase tracking-wider">{sec}</td></tr>
      {tasks.map((t) => (
        <tr key={t.id} className={t.critical ? "bg-red-bg/30" : ""}>
          <td className="font-mono text-xs">{t.code}</td>
          <td><div className="leading-snug">{t.name}</div>{t.basis && <div className="mt-0.5 text-xs text-muted-foreground">{t.basis}</div>}{t.amount ? <div className="text-xs text-muted-foreground">{fmtMoney(t.amount)}</div> : null}</td>
          <td className="num">{E(t.id, "override_days", t.override ?? "", `${t.code} days`, { kind: "number", width: "w-16", placeholder: t.derived != null ? String(t.derived) : "0", display: <>{t.duration}{t.override != null && t.derived != null && t.derived !== t.duration && <div className="text-2xs text-muted-foreground">derived {t.derived}</div>}</> })}</td>
          <td className="font-mono text-xs">{E(t.id, "predecessors", t.predecessors.join(", "), `${t.code} follows`, { width: "w-32", display: t.predecessors.join(", ") || "—" })}</td>
          <td className="whitespace-nowrap text-xs">{t.start ?? "—"}</td><td className="whitespace-nowrap text-xs">{t.finish ?? "—"}</td>
          <td className="num text-xs">{t.hammock ? "—" : t.float}</td>
          <td>
            <div className="relative h-3 bg-muted" role="img" aria-label={`${t.code}: day ${t.es + 1} to ${t.ef}`}>
              {t.duration > 0 && <div className={`absolute top-0 h-3 ${t.hammock ? "bg-foreground/30" : crit.has(t.code) ? "bg-red-fg" : "bg-primary"}`} style={{ left: `${(t.es / total) * 100}%`, width: `${Math.max((t.duration / total) * 100, 0.8)}%` }} />}
            </div>
          </td>
          <td className="whitespace-nowrap" data-col="flag">{t.critical ? <Chip tone="red">Critical</Chip> : t.hammock ? <span className="text-xs text-muted-foreground">runs throughout</span> : null}{editing && <label className="mt-1 flex items-center gap-1 text-2xs text-muted-foreground"><EditToggle target="programme_task" id={t.id} field="hammock" value={t.hammock} label={`${t.code} runs throughout`} display="" /> throughout</label>}</td>
          {editing && <td className="whitespace-nowrap" data-col="remove"><button className="btn btn-ghost whitespace-nowrap !px-3 !py-1" aria-label={`Remove ${t.code}`} onClick={() => remove("programme_task", t.id)}>Remove</button></td>}
        </tr>
      ))}
    </>
  );
}
