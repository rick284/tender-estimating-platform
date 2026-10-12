import type { Estimate } from "../lib/types";
import { fmtMoney, fmtPct } from "../lib/format";
import { EditCheck, EditField, EditNum } from "../components/EditCells";
import { useEdit } from "../lib/edit";
import { Chip, Money, PageHeader, Panel } from "../components/ui";

const METHOD_LABEL: Record<string, string> = { "%": "Percentage", "PC Sum": "PC sum ($)", "Markup %": "Markup %", "Margin %": "Margin % (true margin)", "Fixed Amount": "Fixed amount ($)", "Risk Engine": "From Risk Truth (platform)" };
// What a percentage is taken of, so the estimator knows what typing 2 means
const PCT_OF = (ref: string, method: string) => (method === "Margin %" ? "true margin on cost" : method === "Markup %" ? (ref === "CA18" ? "of cost" : "of subtotal") : ref === "CA19" || ref === "CA20" ? "of subtotal" : ref === "CA21" ? "of tender" : "of base direct");

function Basis({ c }: { c: Estimate["commercial"][number] }) {
  const { editing } = useEdit();
  const pctMethod = c.method === "%" || c.method === "Markup %" || c.method === "Margin %";
  const amtMethod = c.method === "PC Sum" || c.method === "Fixed Amount";
  const text = pctMethod ? `${c.method.replace(" %", "")} ${fmtPct(c.pct, 1)}` : c.method;
  if (!editing) return <>{c.include ? text : <Chip tone="neutral">Off</Chip>}</>;
  // Three fixed columns (switch | basis | value) so every row lines up: the switch, the basis and the $ / % box start at the same place down the page.
  const manualRisk = (c.ref === "CA01" || c.ref === "CA02") && c.method !== "Risk Engine" && (c.engine_value ?? 0) > 0;
  return (
    <div>
      <div className="grid grid-cols-[3.5rem_13.5rem_minmax(0,1fr)] items-center gap-x-3">
        <label className="flex items-center gap-1.5 text-xs"><EditCheck target="commercial" id={c.ref} field="include" original={c.include} label={`${c.ref} included`} /> On</label>
        {c.methods && c.methods.length > 1
          ? <EditField target="commercial" id={c.ref} field="method" value={c.method} kind="select" width="w-full" label={`${c.ref} basis`} options={c.methods.map((m) => ({ value: m, label: METHOD_LABEL[m] ?? m }))} />
          : <span className="text-xs text-muted-foreground">{c.method}</span>}
        <div className="flex items-center gap-1.5">
          {pctMethod && <><span className="w-3" aria-hidden="true" /><EditNum target="commercial" id={c.ref} field="pct" original={c.pct} scale={100} width="w-28" label={`${c.ref} percentage`} display="" /><span className="whitespace-nowrap text-xs text-muted-foreground">% {PCT_OF(c.ref, c.method)}</span></>}
          {amtMethod && <><span className="w-3 text-right text-xs text-muted-foreground">$</span><EditNum target="commercial" id={c.ref} field="pc_sum" original={c.pc_sum} dp={2} width="w-28" label={`${c.ref} amount`} display="" /></>}
        </div>
      </div>
      {manualRisk && <p className="mt-1 text-xs text-red-fg">Risk Truth has {fmtMoney(c.engine_value ?? 0)} of approved provisions for this line that are not in the price while a manual basis is used.</p>}
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
