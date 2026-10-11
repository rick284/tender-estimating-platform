import { useEffect, useState, type FormEvent } from "react";
import type { Estimate, WeatherCatalog } from "../lib/types";
import { newWeatherId } from "../lib/weatherCatalog";
import { Modal } from "./Modal";

const input = "mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary";
const Err = ({ msg }: { msg: string }) => (msg ? <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{msg}</div> : null);
const inRange = (c: WeatherCatalog, d: string) => d >= c.engine_from && d <= c.engine_to;

/** Switch the live weather tool on for this tender. */
export function WeatherSetupDialog({ open, onClose, catalog, est, onAdd }: {
  open: boolean; onClose: () => void; catalog: WeatherCatalog | null; est: Estimate; onAdd: (payload: Record<string, unknown>) => void;
}) {
  const [f, setF] = useState({ station: "Auckland", start: "", wpw: "5", baseline: "" });
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setF({ station: "Auckland", start: "", wpw: "5", baseline: est.summary.dry_programme_wd ? String(est.summary.dry_programme_wd) : "" }); setErr(""); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!catalog) return setErr("The weather data is still loading. Try again in a moment.");
    if (!f.start) return setErr("Enter the assumed project start date.");
    if (!inRange(catalog, f.start)) return setErr(`The start date must be between ${catalog.engine_from} and ${catalog.engine_to}.`);
    onAdd({ station: f.station, start: f.start, working_days_per_week: f.wpw, baseline_wd: f.baseline || "0" });
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Switch on the live weather tool">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">The platform will work out the weather allowance (CA10) itself, using NIWA climate normals and your task factors, instead of using results typed in from the separate weather spreadsheet. You then list the weather-exposed activities and their dates.</p>
        {est.weather.live === false && est.qs.length > 0 && <p className="border border-amber-line bg-amber-bg px-3 py-2 text-sm text-amber-fg">This tender currently uses weather results recorded from the weather spreadsheet. Switching on replaces them with a new calculation, so the allowance will change.</p>}
        <label className="block"><span className="label">Nearest NIWA station</span>
          <select className={input} value={f.station} onChange={set("station")}>{(catalog?.stations ?? ["Auckland"]).map((s) => <option key={s}>{s}</option>)}</select></label>
        <div className="grid grid-cols-3 gap-3">
          <label className="block"><span className="label">Assumed start</span><input type="date" className={input} value={f.start} onChange={set("start")} /></label>
          <label className="block"><span className="label">Working days / week</span><input className={input} inputMode="numeric" value={f.wpw} onChange={set("wpw")} /></label>
          <label className="block"><span className="label">Dry programme (WD)</span><input className={input} inputMode="numeric" value={f.baseline} onChange={set("baseline")} placeholder="e.g. 55" /></label>
        </div>
        {err && <Err msg={err} />}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Switch on</button></div>
      </form>
    </Modal>
  );
}

/** Add a weather-exposed activity. */
export function WeatherActivityDialog({ open, onClose, catalog, est, onAdd }: {
  open: boolean; onClose: () => void; catalog: WeatherCatalog | null; est: Estimate; onAdd: (id: string, payload: Record<string, unknown>) => void;
}) {
  const blank = { task: "", start: "", finish: "", critical: false, qs: [] as string[], labour: "", plant: "", note: "" };
  const [f, setF] = useState(blank);
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setF(blank); setErr(""); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const toggleQs = (c: string) => setF({ ...f, qs: f.qs.includes(c) ? f.qs.filter((x) => x !== c) : [...f.qs, c] });
  const task = catalog?.tasks.find((t) => t.name === f.task);
  const cats = Array.from(new Set(catalog?.tasks.map((t) => t.category) ?? []));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!catalog) return setErr("The weather data is still loading. Try again in a moment.");
    if (!f.task) return setErr("Choose the type of work from the task library.");
    if (!f.start || !f.finish) return setErr("Enter the start and finish dates of the activity.");
    if (f.finish < f.start) return setErr("The activity can't finish before it starts.");
    if (!inRange(catalog, f.start) || !inRange(catalog, f.finish)) return setErr(`Dates must be between ${catalog.engine_from} and ${catalog.engine_to}.`);
    for (const k of ["labour", "plant"] as const) if (f[k].trim() !== "" && (!Number.isFinite(Number(f[k])) || Number(f[k]) < 0)) return setErr(`Exposed ${k} needs a number that isn't negative.`);
    if (f.qs.length === 0 && f.labour.trim() === "" && f.plant.trim() === "") return setErr("Link the activity to at least one QS item, or type in the exposed labour and plant cost.");
    onAdd(newWeatherId(), { task: f.task, start: f.start, finish: f.finish, critical: f.critical, qs_codes: f.qs, labour: f.labour.trim() || null, plant: f.plant.trim() || null, note: f.note.trim() });
    onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title="Add weather activity" wide>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">One block of work that is outdoors or weather-exposed. Its dates set which months of climate apply. Only mark it critical if it is on the real critical path: delay is never added up across tasks running at the same time.</p>
        <label className="block"><span className="label">Type of work</span>
          <select className={input} value={f.task} onChange={set("task")}>
            <option value="">Choose…</option>
            {cats.map((c) => <optgroup key={c} label={c}>{catalog?.tasks.filter((t) => t.category === c).map((t) => <option key={t.name}>{t.name}</option>)}</optgroup>)}
          </select></label>
        {task && <p className="text-xs text-muted-foreground">{task.basis} Exposure {task.rain_exposure}, rain loss {task.rain_loss}, wet-ground carryover {task.carryover}, non-recoverable {task.nonrecoverable} (AMBER company defaults).</p>}
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">Start</span><input type="date" className={input} value={f.start} onChange={set("start")} /></label>
          <label className="block"><span className="label">Finish</span><input type="date" className={input} value={f.finish} onChange={set("finish")} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-black" checked={f.critical} onChange={(e) => setF({ ...f, critical: e.target.checked })} /> On the critical path</label>
        <fieldset>
          <legend className="label">Weather-exposed QS items (their labour and plant rows tagged Weather exposed)</legend>
          <div className="mt-1 max-h-40 overflow-y-auto border p-2 text-sm">
            {est.qs.length === 0 && <span className="text-muted-foreground">No QS items yet.</span>}
            {est.qs.map((q) => (
              <label key={q.code} className="flex items-center gap-2 py-0.5"><input type="checkbox" className="h-4 w-4 accent-black" checked={f.qs.includes(q.code)} onChange={() => toggleQs(q.code)} /><span className="font-mono text-xs">{q.code}</span> <span className="truncate">{q.description}</span></label>
            ))}
          </div>
        </fieldset>
        <details className="border px-3 py-2"><summary className="cursor-pointer text-sm font-medium">Or type the exposed cost in (optional)</summary>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="block"><span className="label">Exposed labour $</span><input className={input} inputMode="decimal" value={f.labour} onChange={set("labour")} /></label>
            <label className="block"><span className="label">Exposed plant $</span><input className={input} inputMode="decimal" value={f.plant} onChange={set("plant")} /></label>
          </div>
        </details>
        <label className="block"><span className="label">Note (optional)</span><input className={input} value={f.note} maxLength={300} onChange={set("note")} /></label>
        {err && <Err msg={err} />}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add activity</button></div>
      </form>
    </Modal>
  );
}
