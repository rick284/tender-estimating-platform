import { useEffect, useMemo, useState } from "react";
import { api, type PlanTask, type PlanWindow, type ProductionPlan } from "../lib/api";
import { Chip, Empty, Panel } from "../components/ui";

const blank = (n: number): PlanTask => ({ id: `P-${String(n).padStart(3, "0")}`, ref: "", stage: "", name: "", owner: "", low: null, high: null, driver: "", predecessor: "", deliverable: "", acceptance: "", scope_refs: "", actual: null, done: false });
const num = (v: string): number | null => (v.trim() === "" ? null : Number(v));
const h = (v: number | null | undefined) => (v === null || v === undefined ? "—" : String(Math.round(v * 100) / 100));

/** Step 02: the estimating production programme (the plan for the estimating work, not the construction programme). */
export function ProductionPlanPanel({ tenderId }: { tenderId: string }) {
  const [plan, setPlan] = useState<ProductionPlan | null>(null);
  const [tasks, setTasks] = useState<PlanTask[]>([]);
  const [win, setWin] = useState<PlanWindow | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const apply = (p: ProductionPlan) => { setPlan(p); setTasks(p.tasks); setWin(p.window); setDirty(false); setErr(""); };
  useEffect(() => { api.production(tenderId).then(apply).catch((e) => setErr((e as Error).message)); }, [tenderId]);
  const run = async (fn: () => Promise<ProductionPlan>) => { setBusy(true); setErr(""); try { apply(await fn()); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };
  const change = (i: number, patch: Partial<PlanTask>) => { setTasks((t) => t.map((x, j) => (j === i ? { ...x, ...patch } : x))); setDirty(true); };
  const nextId = () => { let n = tasks.length + 1; while (tasks.some((t) => t.id === `P-${String(n).padStart(3, "0")}`)) n++; return n; };
  const live = useMemo(() => ({ low: tasks.reduce((a, t) => a + (t.low ?? 0), 0), high: tasks.reduce((a, t) => a + (t.high ?? 0), 0) }), [tasks]);
  if (!plan) return err ? <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div> : <p className="mb-4 text-sm text-muted-foreground" aria-live="polite">Reading the production plan…</p>;
  const s = plan.summary;
  const rc = s?.reconciliation;
  const inp = "h-9 w-full border bg-background px-2 text-sm";
  const stages = Array.from(new Set(tasks.map((t) => t.stage)));
  return (
    <>
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      <div className={`mb-4 border px-4 py-3 text-sm ${plan.go_ahead ? "border-green-line bg-green-bg text-green-fg" : "border-amber-line bg-amber-bg text-amber-fg"}`}>
        {plan.go_ahead ? <>Go-ahead recorded ({plan.go_ahead.mode === "client_go" ? "the client has given the go" : "proceeding anyway"}). Work steps can start.</>
          : <>No go-ahead recorded yet. Finish this plan, then stop at the go-ahead checkpoint: no take-off or pricing until the client's go (record it on the Job Record page).</>}
      </div>
      <Panel title="Planned hours against the Step 01 window" className="mb-4"
        action={<div className="flex gap-2"><button className="btn btn-ghost !py-1.5" disabled={busy} onClick={() => run(() => api.importProduction(tenderId))}>{busy ? "Working…" : "Import from Drive"}</button>
          <button className="btn btn-solid !py-1.5" disabled={busy || !dirty} onClick={() => run(() => api.saveProduction(tenderId, tasks, win))}>{dirty ? "Save plan" : "Saved"}</button></div>}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div><div className="label">Planned estimating hours</div><div className="font-mono text-2xl font-bold">{h(dirty ? live.low : s?.low)} to {h(dirty ? live.high : s?.high)}</div></div>
          <div><div className="label">Hours tracked in the Timesheet</div><div className="font-mono text-2xl font-bold">{h(s?.tracked_hours ?? 0)}</div></div>
          <div><div className="label">Hours typed against tasks</div><div className="font-mono text-2xl font-bold">{h(s?.actual_task_hours ?? 0)}</div></div>
          <div><div className="label">Tasks done</div><div className="font-mono text-2xl font-bold">{s ? `${s.done} of ${s.count}` : "—"}</div></div>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
          <span className="label !mb-0">Step 01 window (hours)</span>
          {(["low_hours", "high_hours", "benchmark_hours"] as const).map((k) => (
            <label key={k} className="flex items-center gap-1.5"><span className="text-muted-foreground">{k === "low_hours" ? "low" : k === "high_hours" ? "high" : "reference"}</span>
              <input aria-label={`Window ${k}`} className="h-9 w-20 border bg-background px-2 text-right font-mono" inputMode="decimal" value={win?.[k] ?? ""}
                onChange={(e) => { setWin({ low_hours: win?.low_hours ?? null, high_hours: win?.high_hours ?? null, benchmark_hours: win?.benchmark_hours ?? null, [k]: num(e.target.value) }); setDirty(true); }} /></label>
          ))}
          {rc && <Chip tone={rc.position === "within" ? "green" : "amber"}>{rc.position === "within" ? "Within the window" : rc.position === "below" ? "Below the window" : "Above the window"}</Chip>}
        </div>
        {rc && <p className="mt-2 text-sm text-muted-foreground">{rc.note} Production accuracy comes before matching the fee window.</p>}
        {plan.source && <p className="mt-2 text-xs text-muted-foreground">Source: {plan.source}{plan.updated_at ? `, saved ${new Date(plan.updated_at).toLocaleString()}` : ""}. Importing replaces the plan here; nothing in Drive is changed.</p>}
        {s && s.issues.length > 0 && <ul className="mt-3 list-disc pl-5 text-sm text-amber-fg">{s.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
      </Panel>
      {tasks.length === 0 ? (
        <>
          <Empty title="No production plan yet" body="Import the Step 02 task-plan workbook from the job folder, or add the tasks here. Each task needs an owner, low and high hours, what drives them, what it follows, a deliverable and an acceptance test." />
          <button className="btn btn-solid mt-3" onClick={() => { setTasks([blank(1)]); setDirty(true); }}>Add the first task</button>
        </>
      ) : (
        <Panel title={`Tasks (${tasks.length})`} flush action={<button className="btn btn-ghost !py-1.5" onClick={() => { setTasks([...tasks, { ...blank(nextId()), stage: tasks[tasks.length - 1]?.stage ?? "" }]); setDirty(true); }}>Add task</button>}>
          <div className="grid-scroll"><table className="grid-table">
            <thead><tr><th>Done</th><th className="min-w-[14rem]">Task</th><th className="min-w-[8rem]">Stage</th><th className="min-w-[7rem]">Owner</th><th className="text-right">Low h</th><th className="text-right">High h</th><th className="text-right">Actual h</th>
              <th className="min-w-[6rem]">Follows</th><th className="min-w-[10rem]">Source / driver</th><th className="min-w-[10rem]">Deliverable</th><th className="min-w-[10rem]">Acceptance test</th><th></th></tr></thead>
            <tbody>{tasks.map((t, i) => (
              <tr key={t.id}>
                <td><input type="checkbox" aria-label={`Done: ${t.name || t.id}`} checked={t.done} onChange={(e) => change(i, { done: e.target.checked })} /></td>
                <td><input aria-label="Task name" className={inp} value={t.name} onChange={(e) => change(i, { name: e.target.value })} /></td>
                <td><input aria-label="Stage" list={`stages-${tenderId}`} className={inp} value={t.stage} onChange={(e) => change(i, { stage: e.target.value })} /></td>
                <td><input aria-label="Owner" className={inp} value={t.owner} onChange={(e) => change(i, { owner: e.target.value })} /></td>
                <td><input aria-label="Low hours" className={`${inp} w-16 text-right font-mono`} inputMode="decimal" value={t.low ?? ""} onChange={(e) => change(i, { low: num(e.target.value) })} /></td>
                <td><input aria-label="High hours" className={`${inp} w-16 text-right font-mono`} inputMode="decimal" value={t.high ?? ""} onChange={(e) => change(i, { high: num(e.target.value) })} /></td>
                <td><input aria-label="Actual hours" className={`${inp} w-16 text-right font-mono`} inputMode="decimal" value={t.actual ?? ""} onChange={(e) => change(i, { actual: num(e.target.value) })} /></td>
                <td><input aria-label="Follows" className={inp} value={t.predecessor} onChange={(e) => change(i, { predecessor: e.target.value })} /></td>
                <td><input aria-label="Source or driver" className={inp} value={t.driver} onChange={(e) => change(i, { driver: e.target.value })} /></td>
                <td><input aria-label="Deliverable" className={inp} value={t.deliverable} onChange={(e) => change(i, { deliverable: e.target.value })} /></td>
                <td><input aria-label="Acceptance test" className={inp} value={t.acceptance} onChange={(e) => change(i, { acceptance: e.target.value })} /></td>
                <td className="whitespace-nowrap"><button className="btn btn-ghost !py-1" onClick={() => { setTasks(tasks.filter((_, j) => j !== i)); setDirty(true); }}>Remove</button></td>
              </tr>))}</tbody>
          </table></div>
          <datalist id={`stages-${tenderId}`}>{stages.filter(Boolean).map((x) => <option key={x} value={x} />)}</datalist>
          {s && s.stages.length > 1 && (
            <div className="border-t p-4"><div className="label mb-2">By stage (saved plan)</div>
              <table className="grid-table"><thead><tr><th>Stage</th><th className="text-right">Tasks done</th><th className="text-right">Low h</th><th className="text-right">High h</th><th className="text-right">Actual h</th></tr></thead>
                <tbody>{s.stages.map((x) => <tr key={x.stage}><td>{x.stage}</td><td className="num">{x.done} of {x.tasks}</td><td className="num">{h(x.low)}</td><td className="num">{h(x.high)}</td><td className="num">{h(x.actual)}</td></tr>)}</tbody></table></div>
          )}
        </Panel>
      )}
      <p className="mt-3 text-xs text-muted-foreground">Hours here are estimator time, not construction duration. Tracked hours come from the Timesheet; typed task hours are yours to enter.</p>
    </>
  );
}
