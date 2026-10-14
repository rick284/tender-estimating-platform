import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Download, Plus, Sparkles } from "lucide-react";
import { api, type TimeEntry, type TimeGroup, type Timesheet as TS } from "../lib/api";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Select, Stat } from "../components/ui";
import { toast } from "../lib/toast";

const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");
const field = "mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary";
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dur = (sec: number) => { const m = Math.round(sec / 60); if (sec < 60 && sec > 0) return `${Math.round(sec)}s`; return m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m` : `${m}m`; };
const mins = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m` : `${m}m`);
const clock = (iso: string) => (iso ? new Date(iso).toLocaleTimeString("en-NZ", { hour: "2-digit", minute: "2-digit", hour12: false }) : "");
const dayLabel = (d: string) => new Date(d + "T12:00:00").toLocaleDateString("en-NZ", { weekday: "long", day: "numeric", month: "long" });

function presets() {
  const t = new Date(), day = (t.getDay() + 6) % 7;                         // Monday = 0
  const mon = new Date(t); mon.setDate(t.getDate() - day);
  const lastMon = new Date(mon); lastMon.setDate(mon.getDate() - 7);
  const lastSun = new Date(mon); lastSun.setDate(mon.getDate() - 1);
  return {
    today: [ymd(t), ymd(t)], week: [ymd(mon), ymd(t)], lastweek: [ymd(lastMon), ymd(lastSun)],
    month: [ymd(new Date(t.getFullYear(), t.getMonth(), 1)), ymd(t)], lastmonth: [ymd(new Date(t.getFullYear(), t.getMonth() - 1, 1)), ymd(new Date(t.getFullYear(), t.getMonth(), 0))],
  } as Record<string, string[]>;
}

function EntryDialog({ open, onClose, onSaved, tenders, edit }: { open: boolean; onClose: () => void; onSaved: () => void; tenders: { id: string; name: string }[]; edit: TimeEntry | null }) {
  const [date, setDate] = useState(ymd(new Date()));
  const [minutes, setMinutes] = useState("30");
  const [note, setNote] = useState("");
  const [tid, setTid] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setErr("");
    if (edit) { setDate(edit.date); setMinutes(String(Math.round(edit.active_seconds / 60))); setNote(edit.note); setTid(edit.tender_id); }
    else { setDate(ymd(new Date())); setMinutes("30"); setNote(""); setTid(""); }
  }, [open, edit]);
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const b = { date, minutes: Number(minutes), note, tender_id: tid };
      if (edit) await api.timeEditEntry(edit.id, b); else await api.timeAddEntry(b);
      onSaved(); onClose();
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={edit ? "Edit manual time" : "Add time worked off the platform"}>
      <div className="space-y-3 p-5 text-sm">
        <p className="text-muted-foreground">For work the platform can't see: phone calls, site visits, meetings, work in other programs.</p>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-3 py-2 text-red-fg">{err}</div>}
        <label className="block">Date<input type="date" className={field} value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <label className="block">Minutes<input type="number" min={1} max={1440} className={field} value={minutes} onChange={(e) => setMinutes(e.target.value)} /></label>
        <label className="block">Tender (optional)
          <select className={field} value={tid} onChange={(e) => setTid(e.target.value)}><option value="">No tender</option>{tenders.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        </label>
        <label className="block">What was it for?<input className={field} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Phone call with client about RFI-14" /></label>
        <div className="flex justify-end gap-2 pt-2"><button className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid" disabled={busy} onClick={save}>{edit ? "Save" : "Add time"}</button></div>
      </div>
    </Modal>
  );
}

function EntryRow({ e, reload, editManual }: { e: TimeEntry; reload: () => void; editManual: (e: TimeEntry) => void }) {
  const [note, setNote] = useState(e.note);
  useEffect(() => setNote(e.note), [e.note]);
  const del = async () => {
    if (!window.confirm(e.kind === "manual" ? "Delete this manual entry?" : "Delete this session from the timesheet? The time is removed (the estimate is not touched).")) return;
    try { await (e.kind === "manual" ? api.timeDeleteEntry(e.id) : api.timeSessionDelete(e.id)); reload(); } catch (x) { toast.error(msg(x)); }
  };
  const saveNote = async () => { if (note !== e.note) { try { await api.timeSessionNote(e.id, note); reload(); } catch (x) { toast.error(msg(x)); } } };
  return (
    <li className="border-t px-3 py-2.5 text-sm" data-testid="time-entry">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {e.kind === "session"
          ? <span className="font-medium tabular-nums">{clock(e.start)} – {clock(e.end)}{e.open && <Chip tone="green">Open now</Chip>}</span>
          : <span className="font-medium">Manual entry</span>}
        {e.kind === "session" && <span className="text-muted-foreground">Elapsed {dur(e.elapsed_seconds)} · Active {dur(e.active_seconds)}</span>}
        {e.kind === "manual" && <span className="text-muted-foreground">{dur(e.active_seconds)}</span>}
        <span className="ml-auto flex gap-3">
          {e.kind === "manual" && <button className="underline underline-offset-4" onClick={() => editManual(e)}>Edit</button>}
          <button className="text-red-fg underline underline-offset-4" onClick={del}>Delete</button>
        </span>
      </div>
      {e.summary.length > 0 && <ul className="mt-1 list-disc space-y-0.5 pl-5 text-muted-foreground">{e.summary.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      {e.kind === "session"
        ? <input className="mt-2 h-8 w-full max-w-xl border bg-background px-2 text-xs" placeholder="Add a note to this session (optional)" value={note} onChange={(x) => setNote(x.target.value)} onBlur={saveNote} aria-label="Session note" />
        : <p className="mt-1">{e.note}</p>}
    </li>
  );
}

export function Timesheet() {
  const P = useMemo(presets, []);
  const [range, setRange] = useState<string[]>(P.week);
  const [tid, setTid] = useState("");
  const [data, setData] = useState<TS | null>(null);
  const [tenders, setTenders] = useState<{ id: string; name: string }[]>([]);
  const [unit, setUnit] = useState<{ round: number; choices: number[]; can: boolean } | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState<{ open: boolean; edit: TimeEntry | null }>({ open: false, edit: null });

  const load = useCallback(async () => {
    try { setErr(""); setData(await api.timesheet(range[0], range[1], tid)); } catch (e) { setErr(msg(e)); }
  }, [range, tid]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    api.tenders().then((r) => setTenders(r.tenders.map((t) => ({ id: t.id, name: t.name })))).catch(() => undefined);
    api.timeSettings().then((s) => setUnit({ round: s.round_minutes, choices: s.choices, can: s.can_change })).catch(() => undefined);
  }, []);
  useEffect(() => { const t = setInterval(() => void load(), 60_000); return () => clearInterval(t); }, [load]);     // an open session keeps growing

  const byDay = useMemo(() => {
    const m = new Map<string, TimeGroup[]>();
    (data?.groups ?? []).forEach((g) => m.set(g.date, [...(m.get(g.date) ?? []), g]));
    return [...m.entries()];
  }, [data]);
  const entriesFor = (g: TimeGroup) => (data?.entries ?? []).filter((e) => e.date === g.date && e.tender_id === g.tender_id);
  const setRound = async (v: string) => { try { await api.timeSetRound(Number(v)); setUnit((u) => u && { ...u, round: Number(v) }); await load(); } catch (e) { toast.error(msg(e)); } };
  const csv = (detail: boolean) => api.timesheetCsv(range[0], range[1], tid, detail).catch((e) => toast.error(msg(e)));
  const T = data?.totals;
  const tab = (k: string, label: string) => (
    <button key={k} className={`btn ${range[0] === P[k][0] && range[1] === P[k][1] ? "btn-solid" : "btn-ghost"}`} onClick={() => setRange(P[k])}>{label}</button>
  );

  return (
    <div className="w-full px-3 py-4 sm:px-4">
      <PageHeader title="Timesheet" sub="When you had each tender open, how long you were actually working, what you did, and how long the AI worked. Written for you by the platform; edit or add to it as needed."
        actions={<>
          <button className="btn btn-ghost" onClick={() => setDlg({ open: true, edit: null })}><Plus size={14} aria-hidden /> Add manual time</button>
          <button className="btn btn-ghost" onClick={() => csv(false)}><Download size={14} aria-hidden /> CSV (per day)</button>
          <button className="btn btn-ghost" onClick={() => csv(true)}><Download size={14} aria-hidden /> CSV (every session)</button>
        </>} />
      {err && <div role="alert" className="mb-3 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      <div className="mb-4 flex flex-wrap items-end gap-2">
        {tab("today", "Today")}{tab("week", "This week")}{tab("lastweek", "Last week")}{tab("month", "This month")}{tab("lastmonth", "Last month")}
        <label className="text-xs text-muted-foreground">From<input type="date" className="ml-1 h-9 border bg-background px-2 text-sm" value={range[0]} onChange={(e) => e.target.value && setRange([e.target.value, range[1] < e.target.value ? e.target.value : range[1]])} /></label>
        <label className="text-xs text-muted-foreground">To<input type="date" className="ml-1 h-9 border bg-background px-2 text-sm" value={range[1]} onChange={(e) => e.target.value && setRange([range[0] > e.target.value ? e.target.value : range[0], e.target.value])} /></label>
        <Select label="Tender" value={tid} onChange={setTid} options={[{ value: "", label: "All tenders" }, ...tenders.map((t) => ({ value: t.id, label: t.name }))]} />
        {unit && <Select label="Round up to" value={String(unit.round)} onChange={setRound} disabled={!unit.can} options={unit.choices.map((c) => ({ value: String(c), label: `${c} min` }))} />}
      </div>
      {T && (
        <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Stat label="Active time" value={dur(T.active_seconds)} sub="actually working" />
          <Stat label="Elapsed" value={dur(T.elapsed_seconds)} sub="open to close" />
          <Stat label="Billable (rounded up)" value={mins(T.billable_minutes)} sub={`per tender per day, ${unit?.round ?? 6}-min units`} strong />
          <Stat label="AI working time" value={dur(T.ai_seconds)} sub={`${T.ai_runs} run${T.ai_runs === 1 ? "" : "s"}`} />
          <Stat label="Sessions" value={String(data?.entries.filter((e) => e.kind === "session").length ?? 0)} sub="in this range" />
        </div>
      )}
      {data && byDay.length === 0 && <Empty title="No time recorded in this range" body="Time is recorded automatically while a tender is open and you are working in it. You can also add manual time for work done elsewhere." />}
      {byDay.map(([date, groups]) => (
        <Panel key={date} title={dayLabel(date)} flush className="mb-4">
          <div className="grid-scroll"><table className="grid-table w-full text-sm">
            <thead><tr className="text-left"><th className="w-8" /><th className="min-w-[14rem]">Tender</th><th className="whitespace-nowrap text-right">Elapsed</th><th className="whitespace-nowrap text-right">Active</th><th className="whitespace-nowrap text-right">Billable</th><th className="whitespace-nowrap text-right">AI</th></tr></thead>
            <tbody>
              {groups.map((g) => {
                const k = `${g.date}|${g.tender_id}`;
                return (
                  <Fragment key={k}>
                    <tr className="cursor-pointer border-t hover:bg-muted/50" onClick={() => setOpen({ ...open, [k]: !open[k] })} data-testid="time-group">
                      <td className="pl-3">{open[k] ? <ChevronDown size={14} aria-label="Hide details" /> : <ChevronRight size={14} aria-label="Show details" />}</td>
                      <td className="font-medium">{g.tender_name}<span className="ml-2 text-xs font-normal text-muted-foreground">{g.sessions} session{g.sessions === 1 ? "" : "s"}</span></td>
                      <td className="text-right tabular-nums">{dur(g.elapsed_seconds)}</td>
                      <td className="text-right tabular-nums">{dur(g.active_seconds)}</td>
                      <td className="text-right font-semibold tabular-nums">{mins(g.billable_minutes)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{g.ai.runs ? <span className="inline-flex items-center gap-1"><Sparkles size={12} aria-hidden />{dur(g.ai.seconds)} · {g.ai.runs}</span> : "–"}</td>
                    </tr>
                    {open[k] && <tr><td colSpan={6} className="p-0"><ul>{entriesFor(g).map((e) => <EntryRow key={e.id} e={e} reload={load} editManual={(x) => setDlg({ open: true, edit: x })} />)}</ul></td></tr>}
                  </Fragment>
                );
              })}
            </tbody>
          </table></div>
        </Panel>
      ))}
      <EntryDialog open={dlg.open} edit={dlg.edit} onClose={() => setDlg({ open: false, edit: null })} onSaved={load} tenders={tenders} />
    </div>
  );
}
