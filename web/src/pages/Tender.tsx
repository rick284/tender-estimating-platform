import type { Estimate } from "../lib/types";
import { fmtPct } from "../lib/format";
import { Chip, Money, PageHeader, Panel } from "../components/ui";

export function Tender({ est }: { est: Estimate }) {
  const t = est.tender;
  const pre = est.commercial.filter((c) => c.stage === "pre");
  const com = est.commercial.filter((c) => c.stage === "commercial");
  const how = (c: Estimate["commercial"][number]) =>
    c.method === "%" || c.method === "Markup %" || c.method === "Margin %" ? `${c.method.replace(" %", "")} ${fmtPct(c.pct, 1)}` : c.method;
  return (
    <>
      <PageHeader title="Tender build-up" sub="Siteworks only. Base direct cost flows from the QS Takeoff; commercial provisions flow from Commercial Inputs. Nothing is entered on this page." />
      <Panel flush>
        <div className="overflow-x-auto">
          <table className="grid-table min-w-[36rem]">
            <thead><tr><th>Item</th><th>Basis</th><th className="text-right">Amount excl. GST</th></tr></thead>
            <tbody>
              <tr className="group-row"><td colSpan={3}>Base direct estimate</td></tr>
              {est.sections.map((s) => (
                <tr key={s.section}><td>{s.section}</td><td className="text-muted-foreground">QS Takeoff · {s.items.length} item{s.items.length === 1 ? "" : "s"}</td><td className="num"><Money v={s.amount} dash0 /></td></tr>
              ))}
              <tr className="total-row"><td colSpan={2}>Base direct estimate</td><td className="num"><Money v={t.base_direct} /></td></tr>

              <tr className="group-row"><td colSpan={3}>Pre-margin additions</td></tr>
              {pre.map((c) => (
                <tr key={c.ref} className={c.include ? "" : "text-muted-foreground"}>
                  <td><span className="font-mono text-xs">{c.ref}</span> {c.name}</td>
                  <td>{c.include ? how(c) : <Chip tone="neutral">Off</Chip>}</td>
                  <td className="num"><Money v={c.include ? c.amount : null} dash0 /></td>
                </tr>
              ))}
              <tr className="total-row"><td colSpan={2}>Pre-margin additions</td><td className="num"><Money v={t.pre_margin_total} /></td></tr>
              <tr className="total-row"><td colSpan={2}>Subtotal before commercial adjustments</td><td className="num"><Money v={t.subtotal} /></td></tr>

              <tr className="group-row"><td colSpan={3}>Overhead, profit and other commercial adjustments</td></tr>
              {com.filter((c) => c.ref !== "CA21").map((c) => (
                <tr key={c.ref} className={c.include ? "" : "text-muted-foreground"}>
                  <td><span className="font-mono text-xs">{c.ref}</span> {c.name}</td>
                  <td>{c.include ? how(c) : <Chip tone="neutral">Off</Chip>}</td>
                  <td className="num"><Money v={c.include ? c.amount : null} dash0 /></td>
                </tr>
              ))}
              <tr className="total-row"><td colSpan={2}>Siteworks tender excl. GST</td><td className="num"><Money v={t.total_excl_gst} /></td></tr>
              <tr><td colSpan={2} className="text-muted-foreground">GST (switched off in Commercial Inputs)</td><td className="num"><Money v={t.gst} dash0 /></td></tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
