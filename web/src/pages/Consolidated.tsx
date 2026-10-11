import type { Estimate } from "../lib/types";
import { fmtMoney, fmtPct } from "../lib/format";
import { EditNum } from "../components/EditCells";
import { Chip, Money, PageHeader, Panel } from "../components/ui";

export function Consolidated({ est }: { est: Estimate }) {
  const c = est.consolidated;
  const row = (label: string, v: number, strong = false, note?: string) => (
    <tr className={strong ? "total-row" : ""} key={label}>
      <td>{label}{note && <div className="text-xs font-normal text-muted-foreground">{note}</div>}</td>
      <td className="num">{label.startsWith("Confirmed") ? <EditNum target="setting" id="consolidated" field="confirmed_overlap" original={c.confirmed_overlap} dp={2} width="w-32" label="Confirmed overlap" display={<Money v={v} />} /> : <Money v={v} />}</td>
    </tr>
  );
  return (
    <>
      <PageHeader title="Consolidated package" sub="Siteworks plus subcontract overlays and the commercial layer. This is the controlling all-in package view. Each subcontract quote is added once." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Package build" flush>
          <table className="grid-table">
            <tbody>
              {row("Siteworks pre-commercial package", c.own_works, false, "Includes Management Reserve")}
              {c.overlays.map((o) => (
                <tr key={o.name}>
                  <td>{o.name}<div className="mt-0.5"><Chip tone="neutral">{o.kind.toLowerCase()}</Chip></div></td>
                  <td className="num"><EditNum target="overlay" id={o.name} field="amount" original={o.amount} dp={2} width="w-32" label={`${o.name} amount`} display={<Money v={o.amount} />} /></td>
                </tr>
              ))}
              {row("Gross current known package", c.gross_known_package, true)}
              {row("Confirmed Siteworks / Coast overlap", -c.confirmed_overlap, false, c.confirmed_overlap === 0 ? "Interface closed: no overlap remains" : undefined)}
              {row("Known package after overlap", c.known_after_overlap, true)}
            </tbody>
          </table>
        </Panel>
        <Panel title="Commercial layer" flush>
          <table className="grid-table">
            <tbody>
              {row("Known cost before OH and profit", c.gross_known_package)}
              <tr><td>Company overhead <span className="text-muted-foreground">({fmtPct(c.overhead_rate, 0)} markup)</span></td><td className="num"><Money v={c.overhead} /></td></tr>
              <tr><td>Profit <span className="text-muted-foreground">({fmtPct(c.margin, 0)} true margin on sell)</span></td><td className="num"><Money v={c.profit} /></td></tr>
              <tr className="total-row"><td>Working all-in tender excl. GST</td><td className="num"><Money v={c.all_in} /></td></tr>
              <tr><td>Gross margin on sell</td><td className="num">{fmtPct(c.gross_margin_on_sell)}</td></tr>
            </tbody>
          </table>
          <p className="border-t px-4 py-3 text-xs text-muted-foreground">
            True margin means profit is a share of the selling price: sell = (cost + overhead) ÷ (1 − margin). A markup would give a different answer.
          </p>
        </Panel>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">Release position: {est.controls.cover_release}. {fmtMoney(c.all_in)} is a working figure until the technical holds in the release controls are resolved, excluded or formally accepted.</p>
    </>
  );
}
