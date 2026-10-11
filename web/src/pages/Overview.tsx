import type { Estimate } from "../lib/types";
import { INTAKE_FIELDS } from "../lib/intake";
import { fmtMoney, fmtNum, fmtPct } from "../lib/format";
import { Chip, Money, PageHeader, Panel, Stat } from "../components/ui";
import type { TenderPage } from "../components/Shell";

export function Overview({ est, go }: { est: Estimate; go: (p: TenderPage) => void }) {
  const s = est.summary, c = est.consolidated, ct = est.controls;
  const parts = [
    { name: "Siteworks pre-commercial (incl. Management Reserve)", v: c.own_works, shade: "bg-primary" },
    ...c.overlays.reduce<{ name: string; v: number; shade: string }[]>((acc, o) => {
      const key = o.name.startsWith("Allied") ? "Allied drainage subcontract" : o.name.startsWith("Coast") ? "Coast Concrete subcontract" : o.name;
      const hit = acc.find((a) => a.name === key);
      if (hit) hit.v += o.amount; else acc.push({ name: key, v: o.amount, shade: key.startsWith("Coast") ? "bg-foreground/60" : "bg-foreground/30" });
      return acc;
    }, []),
  ];
  const total = parts.reduce((a, p) => a + p.v, 0);
  const intake = INTAKE_FIELDS.filter((f) => est.meta[f.key]);
  const empty = est.qs.length === 0;
  const holds = /HOLD/i.test(ct.release_status || "");
  const released = !!ct.release_status && !/^NOT RELEASED$/i.test(ct.release_status);

  return (
    <>
      <PageHeader title="Tender overview" sub={est.meta.snapshot} />

      {empty && (
        <Panel className="mb-4" title="Getting started">
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            <li>Press <strong>Edit</strong> at the top, then open <button className="underline underline-offset-4" onClick={() => go("qs")}>QS Takeoff</button> and add your quantities.</li>
            <li>Price each item with build-up rows (plant, labour, materials) or a quick lump sum.</li>
            <li>Add subcontract quotes under <button className="underline underline-offset-4" onClick={() => go("consolidated")}>Consolidated Package</button>.</li>
            <li>Review overhead and margin under <button className="underline underline-offset-4" onClick={() => go("tender")}>Tender Build-Up</button>, then save with a reason.</li>
          </ol>
        </Panel>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2" title="What will this cost? (excl. GST)">
          <div className="grid gap-6 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <div>
              <div className="label">Working all-in tender</div>
              <div className="num !text-left font-mono text-3xl font-semibold leading-none sm:text-4xl">{fmtMoney(s.all_in)}</div>
              <p className="mt-3 text-sm text-muted-foreground">
                {est.meta.commercial ? `${est.meta.commercial}. Supplier and material costs inside Siteworks are already in its cost chain; Coast and Allied are separate subcontract overlays added once.` : "Your own works plus any subcontract packages, with overhead and margin applied once. Supplier and material costs are already inside the build-up."}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
              <Stat label="Known cost before OH/profit" value={fmtMoney(s.known_cost)} />
              <Stat label="Gross margin on sell" value={fmtPct(s.gross_margin_on_sell)} />
              <Stat label="Dry programme" value={`${fmtNum(s.dry_programme_wd)} WD`} />
              <Stat label="Weather-adjusted" value={`${fmtNum(Math.round(s.planning_wd * 10) / 10)} WD`} />
            </dl>
          </div>
          {total > 0 ? <div className="mt-6" role="img" aria-label="Package split">
            <div className="flex h-3 w-full overflow-hidden">
              {parts.map((p) => <div key={p.name} className={p.shade} style={{ width: `${(p.v / total) * 100}%` }} />)}
            </div>
            <ul className="mt-4 space-y-2 text-sm">
              {parts.map((p) => (
                <li key={p.name} className="flex items-baseline gap-2">
                  <span className={`h-2 w-2 shrink-0 self-center ${p.shade}`} aria-hidden />
                  <span className="min-w-0 flex-1 leading-snug">{p.name}</span><span className="num w-14 text-xs text-muted-foreground">{((p.v / total) * 100).toFixed(1)}%</span>
                  <span className="num font-medium">{fmtMoney(p.v)}</span>
                </li>
              ))}
            </ul>
          </div> : <p className="mt-6 text-sm text-muted-foreground">Nothing is priced yet, so there is no package split to show.</p>}
        </Panel>

        <Panel title="Release controls" action={released ? <Chip tone={holds ? "red" : "green"}>{holds ? "Hold" : "Pass"}</Chip> : <Chip tone="neutral">Not released</Chip>}>
          <p className="text-sm leading-snug">{ct.release_status || "Not released"}</p>
          <dl className="mt-4 divide-y border-y text-sm">
            {[
              ["Red risks", ct.red_risks, +ct.red_risks > 0],
              ["Red exposures", ct.red_exposures, +ct.red_exposures > 0],
              ["Duplicate-cost gate", ct.duplicate_gate, ct.duplicate_gate !== "OK"],
              ["Programme / cost gate", ct.programme_gate, ct.programme_gate !== "OK"],
              ["Tender equals Risk Truth", ct.tender_equals_risk_truth, ct.tender_equals_risk_truth !== "YES"],
            ].map(([k, v, bad]) => (
              <div key={String(k)} className="flex items-center justify-between py-2">
                <dt className="text-muted-foreground">{k}</dt>
                <dd>{v === "" || v == null ? <Chip tone="neutral">Not started</Chip> : <Chip tone={bad ? "red" : "green"}>{String(v)}</Chip>}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">Status shown as recorded in the workbook. Risk Truth and release gates are recalculated by the platform in a later phase.</p>
        </Panel>
      </div>

      {intake.length > 0 && (
        <Panel className="mt-4" title="Tender intake">
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {est.meta.tender_level && <div><dt className="label">Estimate level</dt><dd className="mt-0.5 text-sm">{est.meta.tender_level}</dd></div>}
            {intake.map((f) => <div key={f.key} className={f.long ? "sm:col-span-2" : ""}><dt className="label">{f.label}</dt><dd className="mt-0.5 whitespace-pre-line text-sm leading-snug">{est.meta[f.key]}</dd></div>)}
          </dl>
        </Panel>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="Siteworks cost chain" flush action={<button className="btn btn-ghost !py-1" onClick={() => go("tender")}>Open</button>}>
          <table className="grid-table">
            <tbody>
              {[
                ["Base direct estimate", est.tender.base_direct],
                ["Pre-margin additions", est.tender.pre_margin_total],
                ["Subtotal before commercial", est.tender.subtotal],
                ["Company overhead", est.tender.overhead],
                ["Profit (true margin)", est.tender.profit],
              ].map(([k, v]) => (
                <tr key={String(k)}><td>{k}</td><td className="num"><Money v={v as number} /></td></tr>
              ))}
              <tr className="total-row"><td>Siteworks tender</td><td className="num"><Money v={est.tender.total_excl_gst} /></td></tr>
            </tbody>
          </table>
        </Panel>

        {ct.rate_green !== "" && <Panel title="Rate verification" flush>
          <table className="grid-table">
            <thead><tr><th>Status</th><th className="text-right">Rows</th><th className="text-right">Cost exposure</th></tr></thead>
            <tbody>
              {([["green", "Green", ct.rate_green, ct.rate_green_cost], ["amber", "Amber", ct.rate_amber, ct.rate_amber_cost], ["red", "Red", ct.rate_red, ct.rate_red_cost]] as const).map(([tone, label, n, cost]) => (
                <tr key={label}>
                  <td><Chip tone={tone}>{label}</Chip></td>
                  <td className="num">{n}</td>
                  <td className="num"><Money v={+cost} dash0 /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-3 text-xs text-muted-foreground">From the workbook's Rate Verification sheet. AMBER means a benchmark or allowance with a check still open and a firm-up action assigned.</p>
        </Panel>}
      </div>

      {est.reconciled !== null && <Panel className="mt-4" title="Reconciliation to workbook" action={<Chip tone={est.reconciled ? "green" : "red"}>{est.reconciled ? "All figures agree" : "Differences found"}</Chip>} flush>
        <div className="overflow-x-auto">
          <table className="grid-table">
            <thead><tr><th>Check</th><th className="text-right">Platform</th><th className="hidden text-right sm:table-cell">Workbook</th><th className="hidden text-right sm:table-cell">Difference</th><th className="w-16" /></tr></thead>
            <tbody>
              {est.reconciliation.map((r) => (
                <tr key={r.name}>
                  <td>{r.name}</td><td className="num"><Money v={r.engine} /></td><td className="num hidden sm:table-cell"><Money v={r.workbook} /></td>
                  <td className="num hidden sm:table-cell"><Money v={r.difference} dash0 /></td>
                  <td>{r.ok ? <Chip tone="green">OK</Chip> : <Chip tone="red">Check</Chip>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-4 py-3 text-xs text-muted-foreground">The platform recalculates every figure from the workbook's inputs (quantities, productivities, rates, commercial settings). It does not copy the workbook's totals.</p>
      </Panel>}
      {est.reconciled === null && !empty && (
        <Panel className="mt-4" title="Edited in the platform">
          <p className="text-sm text-muted-foreground">This revision was changed inside the platform, so there is no source workbook to reconcile it against. Use <strong className="text-foreground">Revisions</strong> to compare it with the revision it was based on and see exactly what moved the price.</p>
        </Panel>
      )}
    </>
  );
}
