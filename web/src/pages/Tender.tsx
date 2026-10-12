import type { Estimate } from "../lib/types";
import { fmtPct } from "../lib/format";
import { EditCheck, EditNum } from "../components/EditCells";
import { useEdit } from "../lib/edit";
import { Chip, Money, PageHeader, Panel } from "../components/ui";

function Basis({ c }: { c: Estimate["commercial"][number] }) {
  const { editing } = useEdit();
  const pctMethod = c.method === "%" || c.method === "Markup %" || c.method === "Margin %";
  const amtMethod = c.method === "PC Sum" || c.method === "Fixed Amount";
  const text = c.method === "%" || c.method === "Markup %" || c.method === "Margin %" ? `${c.method.replace(" %", "")} ${fmtPct(c.pct, 1)}` : c.method;
  if (!editing) return <>{c.include ? text : <Chip tone="neutral">Off</Chip>}</>;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-1.5 text-xs"><EditCheck target="commercial" id={c.ref} field="include" original={c.include} label={`${c.ref} included`} /> On</label>
      <span className="text-xs text-muted-foreground">{c.method}</span>
      {pctMethod && <span className="inline-flex items-center gap-1"><EditNum target="commercial" id={c.ref} field="pct" original={c.pct} scale={100} width="w-20" label={`${c.ref} percentage`} display="" /><span className="text-xs">%</span></span>}
      {amtMethod && <span className="inline-flex items-center gap-1"><span className="text-xs">$</span><EditNum target="commercial" id={c.ref} field="pc_sum" original={c.pc_sum} dp={2} width="w-28" label={`${c.ref} amount`} display="" /></span>}
    </div>
  );
}

export function Tender({ est }: { est: Estimate }) {
  const t = est.tender;
  const gst = est.commercial.find((c) => c.ref === "CA21");
  const pre = est.commercial.filter((c) => c.stage === "pre");
  const com = est.commercial.filter((c) => c.stage === "commercial");
  return (
    <>
      <PageHeader title="Tender build-up" sub="Siteworks only. Base direct cost flows from the QS Takeoff. Press Edit to switch commercial lines on or off and change their percentages and amounts, including GST at the bottom." />
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
                  <td><Basis c={c} /></td>
                  <td className="num"><Money v={c.include ? c.amount : null} dash0 /></td>
                </tr>
              ))}
              <tr className="total-row"><td colSpan={2}>Pre-margin additions</td><td className="num"><Money v={t.pre_margin_total} /></td></tr>
              <tr className="total-row"><td colSpan={2}>Subtotal before commercial adjustments</td><td className="num"><Money v={t.subtotal} /></td></tr>

              <tr className="group-row"><td colSpan={3}>Overhead, profit and other commercial adjustments</td></tr>
              {com.filter((c) => c.ref !== "CA21").map((c) => (
                <tr key={c.ref} className={c.include ? "" : "text-muted-foreground"}>
                  <td><span className="font-mono text-xs">{c.ref}</span> {c.name}</td>
                  <td><Basis c={c} /></td>
                  <td className="num"><Money v={c.include ? c.amount : null} dash0 /></td>
                </tr>
              ))}
              <tr className="total-row"><td colSpan={2}>Siteworks tender excl. GST</td><td className="num"><Money v={t.total_excl_gst} /></td></tr>
              {gst && (
                <tr className={gst.include ? "" : "text-muted-foreground"}>
                  <td><span className="font-mono text-xs">{gst.ref}</span> {gst.name}</td>
                  <td><Basis c={gst} /></td>
                  <td className="num"><Money v={gst.include ? t.gst : null} dash0 /></td>
                </tr>
              )}
              <tr className="total-row"><td colSpan={2}>Siteworks tender incl. GST{gst && !gst.include ? " (GST off, same as excl. GST)" : ""}</td><td className="num"><Money v={t.total_incl_gst} /></td></tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
