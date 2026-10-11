import type { Estimate } from "../lib/types";
import { fmtMoney, fmtNum } from "../lib/format";
import { EditNum } from "../components/EditCells";
import { Chip, Money, PageHeader, Panel, Stat } from "../components/ui";

export function Weather({ est }: { est: Estimate }) {
  const w = est.weather, m = w.meta as Record<string, string>;
  const steps: [string, string, number][] = [
    ["Direct productivity (rain / wet ground)", `Tool output ${fmtMoney(w.tool_rain_cost)} × (current exposed pool ${fmtMoney(w.exposed_pool)} ÷ tool-run pool ${fmtMoney(w.tool_pool)})`, w.direct_productivity],
    ["Critical-path time-related preliminaries", `${fmtNum(Math.round(w.critical_path_delay_wd * 1000) / 1000)} WD delay × ${fmtMoney(w.daily_prelims)} per day`, w.critical_path_prelims],
    ["Additional billed hire / facilities", `${fmtNum(w.additional_weeks)} weeks × ${fmtMoney(w.weekly_hire)} per week`, w.billed_hire],
    ["Project recovery / remediation", "Entered separately; default nil to avoid double counting", w.recovery],
  ];
  return (
    <>
      <PageHeader title="Weather risk" sub="The weather allowance (CA10) is calculated from the approved weather tool's outputs, scaled to the labour and plant that is actually exposed to weather in this estimate." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2" title="Allowance calculation" flush>
          <div className="overflow-x-auto">
            <table className="grid-table min-w-[32rem]">
              <thead><tr><th>Component</th><th>Basis</th><th className="text-right">Amount</th></tr></thead>
              <tbody>
                {steps.map(([a, b, v]) => (
                  <tr key={a}><td className="font-medium">{a}</td><td className="text-muted-foreground">{b}</td><td className="num">{a.startsWith("Project recovery") ? <EditNum target="setting" id="weather" field="recovery_allowance" original={w.recovery} dp={2} width="w-28" label="Weather recovery allowance" display={<Money v={v} dash0 />} /> : <Money v={v} dash0 />}</td></tr>
                ))}
                <tr className="total-row"><td colSpan={2}>Weather allowance to CA10</td><td className="num"><Money v={w.allowance} /></td></tr>
                <tr><td colSpan={2} className="text-muted-foreground">AMBER wind proxy sensitivity ({w.wind_included ? "included" : "excluded by default"})</td><td className="num"><Money v={w.wind_sensitivity} dash0 /></td></tr>
              </tbody>
            </table>
          </div>
          <p className="border-t px-4 py-3 text-xs text-muted-foreground">Delay is taken from the critical path only and is not added across concurrent tasks. Weather allowance is an estimating cost view and does not establish any entitlement to an extension of time or compensation.</p>
        </Panel>
        <Panel title="Programme and basis">
          <div className="grid grid-cols-2 gap-4">
            <Stat label="Dry programme" value={`${fmtNum(est.summary.dry_programme_wd)} WD`} />
            <Stat label="Weather-adjusted" value={`${fmtNum(Math.round(w.planning_wd * 10) / 10)} WD`} />
            <Stat label="Weather delay" value={`${fmtNum(Math.round(w.critical_path_delay_wd * 1000) / 1000)} WD`} />
            <Stat label="Billed weeks" value={`${w.baseline_weeks} + ${fmtNum(w.additional_weeks)}`} />
          </div>
          <dl className="mt-5 space-y-3 border-t pt-4 text-sm">
            <div><dt className="label">Station</dt><dd className="mt-0.5">{m.tool_station || m.station}</dd></div>
            <div><dt className="label">Start (assumed)</dt><dd className="mt-0.5">{m.start}</dd></div>
            <div><dt className="label">Tool</dt><dd className="mt-0.5">{m.tool_version}</dd></div>
            <div><dt className="label">Weather-exposed labour + plant</dt><dd className="mt-0.5 font-mono">{fmtMoney(w.exposed_pool)}</dd></div>
            <div><dt className="label">Confidence</dt><dd className="mt-1 leading-snug"><Chip tone="amber">Amber</Chip> <span className="text-muted-foreground">{m.confidence?.replace(/^AMBER - /, "")}</span></dd></div>
          </dl>
        </Panel>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{m.rerun_status}</p>
    </>
  );
}
