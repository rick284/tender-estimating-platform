import { useState } from "react";
import type { Estimate } from "../lib/types";
import { fmtMoney, fmtNum, fmtPct } from "../lib/format";
import { EditField, EditToggle } from "../components/EditCells";
import { WeatherActivityDialog, WeatherSetupDialog } from "../components/WeatherDialogs";
import { Chip, Money, Panel } from "../components/ui";
import { editKey, useEdit } from "../lib/edit";
import { newWeatherId, useWeatherCatalog } from "../lib/weatherCatalog";

const tone = (s: string) => (s.startsWith("RED") ? "red" : s.startsWith("AMBER") ? "amber" : "green") as "red" | "amber" | "green";
const pc = (v: number) => (v ? fmtPct(v, 1) : "—");

/** Best guess at the weather task-library entry for a QS item: the row's own task type if it is in the library, else by section name. */
function guessTask(names: string[], rowType: string, section: string): string {
  if (names.includes(rowType)) return rowType;
  const s = `${section} ${rowType}`.toLowerCase();
  const pick = (n: string) => (names.includes(n) ? n : "");
  if (/erosion|sediment/.test(s)) return pick("Erosion & sediment controls");
  if (/pile|bored/.test(s)) return pick("Bored piles / drilled holes");
  if (/retaining/.test(s)) return pick("Retaining wall installation");
  if (/concrete|pavement|paving/.test(s)) return pick("External concrete placing");
  if (/drain|stormwater|wastewater/.test(s)) return pick("Drainage trenching");
  if (/service|trench|duct/.test(s)) return pick("Service trenches / ducting");
  if (/earthwork|fill|strip|clear/.test(s)) return pick("Bulk earthworks");
  return pick("Bulk earthworks");
}

/** The platform's own run of the Rev2 weather tool: settings, programme-cost links and the weather-exposed activities. */
export function WeatherLive({ est }: { est: Estimate }) {
  const w = est.weather, t = w.tool as any | null;
  const { editing, add, remove, edits, set, reset } = useEdit();
  const catalog = useWeatherCatalog();
  const [setup, setSetup] = useState(false);
  const [adding, setAdding] = useState(false);
  const rowOptions = [{ value: "", label: "— none —" }, ...est.buildup.map((r) => ({ value: r.uid, label: `${r.row_id} ${r.task} (${fmtMoney(r.applied_rate)}/${r.unit || "unit"})` }))];

  if (!t) {
    return (
      <Panel className="mt-4" title="Live weather tool" action={editing ? <button className="btn btn-solid !py-1" onClick={() => setSetup(true)}>Switch on</button> : undefined}>
        <p className="text-sm text-muted-foreground">
          {est.qs.length === 0 ? "This tender has no quantities yet. " : ""}The allowance above uses results recorded from the separate weather spreadsheet. Switch on the live tool and the platform works the allowance out itself from NIWA climate normals, your weather-exposed activities and their dates{editing ? "." : ". Press Edit to switch it on."}
        </p>
        <WeatherSetupDialog open={setup} onClose={() => setSetup(false)} catalog={catalog} est={est} onAdd={(p) => add("weather", "setup", p)} />
      </Panel>
    );
  }

  const s = t.settings as Record<string, any>;
  const stations: { value: string; label: string }[] = (catalog?.stations ?? [s.station]).map((x) => ({ value: x, label: x }));
  const weeklyKey = editKey("weather", "links", "weekly_uids");
  const weeklyNow: string[] = edits[weeklyKey] ? edits[weeklyKey].value.split(",").filter(Boolean) : (w.links.weekly_uids as string[]);
  const toggleWeekly = (uid: string) => {
    const next = weeklyNow.includes(uid) ? weeklyNow.filter((x) => x !== uid) : [...weeklyNow, uid];
    const original = edits[weeklyKey]?.original ?? (w.links.weekly_uids as string[]).join(",");
    if (next.join(",") === original) reset("weather", "links", "weekly_uids");
    else set({ target: "weather", key: "links", field: "weekly_uids", value: next.join(","), original });
  };
  const fillFromProgramme = () => {
    const names = (catalog?.tasks ?? []).map((x) => x.name);
    const covered = new Set<string>(t.activities.flatMap((a: any) => a.qs_codes as string[]));
    const exposed = new Map<string, { type: string }>();
    for (const r of est.buildup) if (r.weather_exposed && (r.resource_type === "Labour" || r.resource_type === "Plant") && !exposed.has(r.qs_code)) exposed.set(r.qs_code, { type: r.weather_task_type ?? "" });
    const tasks = est.programme.tasks.filter((x) => x.qs_code && exposed.has(x.qs_code) && !covered.has(x.qs_code) && x.start && x.finish && x.duration > 0);
    if (tasks.length === 0) { window.alert("Nothing to add: every programme task with weather-exposed labour or plant already has an activity (or the programme has no dates yet)."); return; }
    for (const x of tasks) {
      add("weather_activity", newWeatherId(), { task: guessTask(names, exposed.get(x.qs_code)!.type, x.section) || names[0], start: x.start, finish: x.finish, critical: x.critical, qs_codes: [x.qs_code], note: `From programme task ${x.code}` });
    }
  };
  const windWarn = s.wind_override == null && catalog && !catalog.wind_proxy_stations.includes(s.station);

  return (
    <>
      <Panel className="mt-4" title="Weather tool settings" action={editing ? <button className="btn btn-ghost !py-1" onClick={() => { if (window.confirm("Switch the live weather tool off? The tender goes back to the recorded weather results. You can undo this before saving.")) remove("weather", "setup"); }}>Switch off</button> : <Chip tone="neutral">Live in platform</Chip>}>
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="label">Nearest NIWA station</dt><dd className="mt-1"><EditField target="weather" id="setup" field="station" kind="select" options={stations} value={s.station} label="Weather station" width="w-44" /></dd></div>
          <div><dt className="label">Assumed project start</dt><dd className="mt-1"><EditField target="weather" id="setup" field="start" kind="date" value={s.start} label="Project start" /></dd></div>
          <div><dt className="label">Working days per week</dt><dd className="mt-1"><EditField target="weather" id="setup" field="working_days_per_week" kind="number" value={String(s.working_days_per_week)} label="Working days per week" width="w-20" /></dd></div>
          <div><dt className="label">Dry programme (WD)</dt><dd className="mt-1"><EditField target="weather" id="setup" field="baseline_wd" kind="number" value={String(s.baseline_wd)} label="Dry programme working days" width="w-24" /></dd></div>
          <div><dt className="label">Local wet-day factor</dt><dd className="mt-1"><EditField target="weather" id="setup" field="local_factor" kind="number" value={String(s.local_factor)} label="Local wet-day factor" width="w-24" /></dd></div>
          <div className="sm:col-span-2"><dt className="label">Basis for a local factor (needed if not 1.00)</dt><dd className="mt-1"><EditField target="weather" id="setup" field="local_basis" value={s.local_basis} label="Local factor basis" width="w-full" placeholder="Site topography, station comparison, site history…" /></dd></div>
          <div><dt className="label">Wind probability override</dt><dd className="mt-1"><EditField target="weather" id="setup" field="wind_override" kind="number" value={s.wind_override ?? ""} label="Wind probability override" width="w-24" placeholder="none" display={s.wind_override ?? "Auckland proxy / none"} /></dd></div>
          <div><dt className="label">Include wind proxy (AMBER)</dt><dd className="mt-1"><EditToggle target="weather" id="setup" field="include_wind" value={!!s.include_wind} label="Include wind proxy" /></dd></div>
        </dl>
        {Number(s.local_factor) !== 1 && !s.local_basis && <p className="mt-4 border border-red-line bg-red-bg px-3 py-2 text-sm text-red-fg">A local wet-day factor other than 1.00 needs a written basis before the estimate is issued.</p>}
        {windWarn && <p className="mt-4 border border-amber-line bg-amber-bg px-3 py-2 text-sm text-amber-fg">There is no wind data for {s.station}. Wind is left out unless you enter a sourced wind probability; wind-sensitive tasks are flagged until you do.</p>}
        <dl className="mt-5 grid gap-x-8 gap-y-4 border-t pt-4 sm:grid-cols-2">
          <div>
            <dt className="label">Daily time-related preliminaries come from</dt>
            <dd className="mt-1 flex flex-wrap items-center gap-2">
              <EditField target="weather" id="links" field="daily_uid" kind="select" options={rowOptions} value={w.links.daily_uid} label="Daily preliminaries row" width="w-72" display={rowOptions.find((o) => o.value === w.links.daily_uid)?.label} />
              <span className="text-sm text-muted-foreground">× <EditField target="weather" id="links" field="hours_per_day" kind="number" value={String(w.links.hours_per_day)} label="Hours per day" width="w-16" /> h/day = <strong className="font-mono text-foreground">{fmtMoney(w.daily_prelims)}</strong> per day</span>
            </dd>
          </div>
          <div>
            <dt className="label">Weekly billed hire / facilities come from</dt>
            <dd className="mt-1 text-sm">
              {editing ? (
                <details className="border px-2 py-1"><summary className="cursor-pointer">{weeklyNow.length} row{weeklyNow.length === 1 ? "" : "s"} selected</summary>
                  <div className="mt-2 max-h-40 overflow-y-auto">
                    {est.buildup.map((r) => <label key={r.uid} className="flex items-center gap-2 py-0.5"><input type="checkbox" className="h-4 w-4 accent-black" checked={weeklyNow.includes(r.uid)} onChange={() => toggleWeekly(r.uid)} /><span className="font-mono text-xs">{r.row_id}</span><span className="truncate">{r.task}</span></label>)}
                  </div></details>
              ) : <span>{weeklyNow.length ? weeklyNow.map((u) => est.buildup.find((r) => r.uid === u)?.task ?? u).join(", ") : "— none —"}</span>}
              <div className="mt-1 text-muted-foreground">= <strong className="font-mono text-foreground">{fmtMoney(w.weekly_hire)}</strong> per week</div>
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel className="mt-4" title="Weather-exposed activities" flush action={editing ? <span className="flex gap-2">
        {est.programme?.set_up && <button className="btn btn-ghost !py-1" onClick={fillFromProgramme}>Fill from programme</button>}
        <button className="btn btn-solid !py-1" onClick={() => setAdding(true)}>Add activity</button></span> : undefined}>
        {t.activities.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">No activities yet. Add each block of outdoor work with its dates; the allowance is worked out per activity, and only critical-path activities add delay.</p>
        ) : (
          <div className="grid-scroll">
            <table className="grid-table min-w-[64rem]">
              <thead><tr>
                <th>Work</th><th>Dates</th><th className="text-center">Critical</th><th>QS items</th>
                <th className="text-right">Labour</th><th className="text-right">Plant</th><th className="text-right">Work days</th>
                <th className="text-right">Wet-day prob.</th><th className="text-right">Impact</th><th className="text-right">Allowance</th><th className="text-right">Lost WD</th><th>Status</th>{editing && <th />}
              </tr></thead>
              <tbody>
                {t.activities.map((a: any) => (
                  <tr key={a.id}>
                    <td className="min-w-[11rem]"><EditField target="weather_activity" id={a.id} field="task" kind="select" options={(catalog?.tasks ?? [{ name: a.task }]).map((x) => ({ value: x.name, label: x.name }))} value={a.task} label={`${a.task} task`} width="w-48" />{a.note && <div className="mt-0.5 text-xs text-muted-foreground">{a.note}</div>}</td>
                    <td className="whitespace-nowrap"><EditField target="weather_activity" id={a.id} field="start" kind="date" value={a.start} label={`${a.task} start`} width="w-36" /> – <EditField target="weather_activity" id={a.id} field="finish" kind="date" value={a.finish} label={`${a.task} finish`} width="w-36" /></td>
                    <td className="text-center"><EditToggle target="weather_activity" id={a.id} field="critical" value={a.critical} label={`${a.task} critical path`} /></td>
                    <td><EditField target="weather_activity" id={a.id} field="qs_codes" value={a.qs_codes.join(", ")} label={`${a.task} QS items`} width="w-28" placeholder="EW01, EW02" /></td>
                    <td className="num"><EditField target="weather_activity" id={a.id} field="labour" kind="number" value={a.labour_input ?? ""} label={`${a.task} exposed labour`} width="w-24" placeholder={String(Math.round(a.labour))} display={<Money v={a.labour} dash0 />} /></td>
                    <td className="num"><EditField target="weather_activity" id={a.id} field="plant" kind="number" value={a.plant_input ?? ""} label={`${a.task} exposed plant`} width="w-24" placeholder={String(Math.round(a.plant))} display={<Money v={a.plant} dash0 />} /></td>
                    <td className="num">{a.workdays}</td>
                    <td className="num">{pc(a.wet_probability)}</td>
                    <td className="num">{pc(a.combined_impact)}</td>
                    <td className="num"><Money v={a.direct_allowance} dash0 /></td>
                    <td className="num">{fmtNum(Math.round(a.lost_wd * 100) / 100)}</td>
                    <td><Chip tone={tone(a.status)}>{a.status.split(" - ")[0]}</Chip><div className="mt-0.5 text-2xs text-muted-foreground">{a.status.split(" - ")[1]}</div></td>
                    {editing && <td><button className="btn btn-ghost !px-2 !py-1" aria-label={`Remove ${a.task}`} onClick={() => remove("weather_activity", a.id)}>Remove</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(t.red_flags.length > 0 || t.warnings.length > 0) && (
          <ul className="space-y-1 border-t px-4 py-3 text-sm">
            {t.red_flags.map((x: string) => <li key={x} className="text-red-fg"><Chip tone="red">Red</Chip> {x}</li>)}
            {t.warnings.map((x: string) => <li key={x} className="text-amber-fg"><Chip tone="amber">Check</Chip> {x}</li>)}
          </ul>
        )}
        <p className="border-t px-4 py-3 text-xs text-muted-foreground">
          Rain, wet-ground carryover and (if included) wind are worked out per activity as: wet-day probability × exposure × productivity loss × non-recoverable share. NIWA 1991-2020 climate normals are sourced evidence (GREEN); task factors are company defaults and stay AMBER until calibrated from actual job records. Public holidays and shutdowns are not modelled. {catalog?.attribution}
        </p>
      </Panel>
      <WeatherActivityDialog open={adding} onClose={() => setAdding(false)} catalog={catalog} est={est} onAdd={(id, p) => add("weather_activity", id, p)} />
    </>
  );
}
