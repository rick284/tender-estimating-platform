import { Fragment, useEffect, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Estimate } from "../lib/types";
import { fmtMoney, fmtNum } from "../lib/format";
import { EditCheck, EditNum } from "../components/EditCells";
import { AddRowDialog } from "../components/AddDialogs";
import { useEdit } from "../lib/edit";
import type { BuildUpLine } from "../lib/types";
import { Chip, Empty, Money, PageHeader, Panel, QaChip, RagChip, SearchBox, Select } from "../components/ui";

function RowEditor({ r }: { r: BuildUpLine }) {
  const { remove } = useEdit();
  const f = (label: string, field: string, original: number | null, opts: { scale?: number; hint?: string } = {}) => (
    <label className="block"><span className="label">{label}</span>
      <div className="mt-1"><EditNum target="row" id={r.uid} field={field} original={original} display="" scale={opts.scale} width="w-full" label={`${r.row_id} ${label}`} placeholder={opts.hint} /></div></label>
  );
  const time = r.mode === "Time x Count", qty = r.mode === "QS Qty x Factor", direct = r.mode === "Direct Qty", lump = r.mode === "Lump Sum / Quote";
  return (
    <div className="sm:col-span-2 lg:col-span-3 border border-amber-line bg-background p-4">
      <div className="label mb-3">Edit this row <span className="font-normal normal-case tracking-normal text-muted-foreground">· {r.mode}. Leave a box blank to clear it.</span></div>
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {time && f(`Productivity (${r.productivity_unit || "units/hr"})`, "productivity_rate", r.productivity)}
        {time && f("Hours override", "duration_override_hrs", r.duration_override, { hint: `${Math.round(r.hours * 100) / 100} calc` })}
        {(time || qty) && f("Count / factor", "count", r.count)}
        {(direct || lump) && f("Quantity", "manual_qty", r.manual_qty)}
        {time && f("Utilisation %", "utilisation", r.utilisation, { scale: 100, hint: "100" })}
        {(qty || direct) && f("Waste %", "waste", r.waste, { scale: 100, hint: "0" })}
        {f(`Job rate override ($/${r.unit || "unit"})`, "job_rate_override", r.job_override, { hint: String(r.library_rate) })}
      </div>
      <div className="mt-4 flex flex-wrap gap-6 text-sm">
        <label className="flex items-center gap-2"><EditCheck target="row" id={r.uid} field="verified" original={r.verified} label={`${r.row_id} verified`} /> Verified</label>
        <label className="flex items-center gap-2"><EditCheck target="row" id={r.uid} field="weather_exposed" original={r.weather_exposed} label={`${r.row_id} weather exposed`} /> Weather exposed (labour / plant)</label>
        <button type="button" className="btn btn-ghost ml-auto !py-1" onClick={() => { if (window.confirm(`Delete row ${r.row_id}? You can undo this before saving.`)) remove("row", r.uid); }}>Delete row</button>
      </div>
    </div>
  );
}

export function BuildUp({ est, code, setCode, focusUid }: { est: Estimate; code: string; setCode: (c: string) => void; focusUid?: string | null }) {
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [qa, setQa] = useState("all");
  const [open, setOpen] = useState<string | null>(null);
  const { editing, add } = useEdit();
  const [adding, setAdding] = useState(false);
  useEffect(() => { if (focusUid) setOpen(focusUid); }, [focusUid]);

  const codes = est.qs.map((i) => i.code);
  const types = Array.from(new Set(est.buildup.map((b) => b.resource_type))).sort();
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return est.buildup.filter((b) =>
      (code === "all" || b.qs_code === code) && (type === "all" || b.resource_type === type) &&
      (qa === "all" || (qa === "attention" ? b.qa !== "OK" : b.qa === qa)) &&
      (!t || `${b.row_id} ${b.task} ${b.resource} ${b.resource_code} ${b.quote_ref}`.toLowerCase().includes(t)));
  }, [est.buildup, q, code, type, qa]);
  const total = rows.reduce((a, r) => a + r.cost, 0);

  return (
    <>
      <PageHeader title="Resource build-up" sub="How each QS item is physically built: labour, plant, materials and subcontract. Rates come from the library unless a job rate overrides them." />
      <div className="no-print mb-4 flex flex-wrap items-center gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Search task, resource or quote" />
        <Select label="QS code" value={code} onChange={setCode} options={[{ value: "all", label: "All QS codes" }, ...codes.map((c) => ({ value: c, label: c }))]} />
        <Select label="Resource type" value={type} onChange={setType} options={[{ value: "all", label: "All types" }, ...types.map((t) => ({ value: t, label: t }))]} />
        <Select label="Check" value={qa} onChange={setQa} options={[{ value: "all", label: "All checks" }, { value: "attention", label: "Needs attention" }, { value: "VERIFY", label: "Verify" }, { value: "OK", label: "OK" }]} />
        {editing && <button className="btn btn-solid !py-1.5" onClick={() => setAdding(true)}>Add row</button>}
        <span className="ml-auto text-sm text-muted-foreground">{rows.length} of {est.buildup.length} rows</span>
      </div>
      {rows.length === 0 ? (est.buildup.length === 0 ? <Empty title="No build-up rows yet" body="Rows price your QS items. Add a QS item first, then add its plant, labour and material rows here." /> : <Empty title="No rows match" body="Clear a filter or change the search." />) : (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="grid-table sm:min-w-[46rem]">
              <thead>
                <tr>
                  <th className="hidden w-28 sm:table-cell">Row</th><th className="sm:min-w-[16rem]">Task / resource</th>
                  <th className="hidden w-28 md:table-cell">Mode</th>
                  <th className="hidden w-20 text-right sm:table-cell">Hours</th>
                  <th className="hidden w-16 text-right sm:table-cell">Count</th>
                  <th className="hidden w-24 text-right sm:table-cell">Rate</th><th className="w-24 text-right sm:w-32">Cost</th>
                  <th className="w-20 sm:w-28">Check</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const isOpen = open === r.uid;
                  return (
                    <Fragment key={r.uid}>
                      <tr className="cursor-pointer" onClick={() => setOpen(isOpen ? null : r.uid)} aria-expanded={isOpen}>
                        <td className="nowrap hidden whitespace-nowrap font-mono text-xs sm:table-cell"><span className="inline-flex items-center gap-1"><ChevronRight size={12} className={`transition-transform ${isOpen ? "rotate-90" : ""}`} aria-hidden />{r.row_id}</span></td>
                        <td>
                          <div className="mb-1 flex items-center gap-1 font-mono text-2xs text-muted-foreground sm:hidden"><ChevronRight size={11} className={`transition-transform ${isOpen ? "rotate-90" : ""}`} aria-hidden />{r.row_id}</div>
                          <div className="leading-snug">{r.task} {r.uid.startsWith("N-") && <Chip tone="neutral">New</Chip>}</div>
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            <span className="mr-1.5 inline-block border px-1 text-2xs uppercase">{r.resource_type}</span>
                            {r.resource || r.resource_code}
                          </div>
                          <div className="mt-1 font-mono text-xs text-muted-foreground sm:hidden">{r.mode === "Time x Count" ? `${fmtNum(Math.round(r.hours * 100) / 100)} h × ` : ""}{fmtMoney(r.applied_rate)}</div>
                        </td>
                        <td className="hidden text-xs text-muted-foreground md:table-cell">{r.mode}</td>
                        <td className="num hidden sm:table-cell">{r.mode === "Time x Count" ? fmtNum(Math.round(r.hours * 100) / 100) : "—"}</td>
                        <td className="num hidden sm:table-cell">{fmtNum(r.mode === "Direct Qty" || r.mode === "Lump Sum / Quote" ? r.manual_qty : r.count)}</td>
                        <td className="num hidden sm:table-cell">{fmtMoney(r.applied_rate)}</td>
                        <td className="num"><Money v={r.cost} dash0 /></td>
                        <td><QaChip value={r.qa} workbook={r.workbook_qa} /></td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={9} className="!bg-muted/40 !p-0">
                            <dl className="grid gap-x-8 gap-y-3 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                              {editing && <RowEditor r={r} />}
                              <div><dt className="label">QS item</dt><dd className="mt-0.5">{r.qs_code} · {fmtNum(r.qs_qty)} {est.qs.find((i) => i.code === r.qs_code)?.unit}</dd></div>
                              <div><dt className="label">Calculation mode</dt><dd className="mt-0.5">{r.mode}</dd></div>
                              <div><dt className="label">Productivity</dt><dd className="mt-0.5">{r.productivity ? `${fmtNum(r.productivity)} ${r.productivity_unit}` : "—"}</dd></div>
                              <div><dt className="label">Library rate → applied</dt><dd className="mt-0.5 font-mono">{fmtMoney(r.library_rate)} → {fmtMoney(r.applied_rate)}{r.job_override ? " (job rate)" : ""} / {r.unit}</dd></div>
                              <div><dt className="label">Utilisation / waste</dt><dd className="mt-0.5">{r.utilisation ?? 1} / {r.waste ?? 0}</dd></div>
                              <div><dt className="label">Weather exposed</dt><dd className="mt-0.5">{r.weather_exposed ? "Yes" : "No"}</dd></div>
                              <div><dt className="label">Evidence</dt><dd className="mt-0.5 flex flex-wrap items-center gap-2"><RagChip value={r.rag} /><span className="text-muted-foreground">{r.verified ? "Verified" : "Not verified"}</span></dd></div>
                              {r.quote_ref && <div className="sm:col-span-2"><dt className="label">Job quote / source</dt><dd className="mt-0.5 leading-snug">{r.quote_ref}{r.source_date && ` (${r.source_date})`}</dd></div>}
                              {r.library_source && <div><dt className="label">Library source</dt><dd className="mt-0.5 leading-snug">{r.library_source}</dd></div>}
                              {r.confidence && <div className="sm:col-span-3"><dt className="label">Confidence</dt><dd className="mt-0.5 leading-snug">{r.confidence}</dd></div>}
                              {r.assumption && <div className="sm:col-span-3"><dt className="label">Assumption / RFI</dt><dd className="mt-0.5 leading-snug">{r.assumption}</dd></div>}
                              {r.workbook_qa && r.workbook_qa !== r.qa && <div className="sm:col-span-3"><dt className="label">Workbook note</dt><dd className="mt-0.5 leading-snug">{r.workbook_qa}</dd></div>}
                              {r.note && <div className="sm:col-span-3"><dt className="label">Notes</dt><dd className="mt-0.5 leading-snug">{r.note}</dd></div>}
                            </dl>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
                <tr className="total-row"><td colSpan={1} className="sm:hidden">Total {code !== "all" ? `for ${code}` : "resource cost"}</td><td colSpan={2} className="hidden sm:table-cell">Total {code !== "all" ? `for ${code}` : "resource cost"}</td><td className="hidden md:table-cell" /><td className="hidden sm:table-cell" /><td className="hidden sm:table-cell" /><td className="hidden sm:table-cell" /><td className="num"><Money v={total} /></td><td /></tr>
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      {est.buildup.some((b) => b.workbook_qa && b.workbook_qa !== b.qa) && (
        <p className="mt-3 text-xs text-muted-foreground">
          <Chip tone="neutral">Note</Chip> Checks are worked out from the build-up rules. Where the workbook shows different hand-typed text, hover the chip or open the row to see what the workbook said.
        </p>
      )}
      <AddRowDialog open={adding} onClose={() => setAdding(false)} qs={est.qs} library={est.library.map((l) => ({ code: l.code, description: l.description, unit: l.unit, rate: l.rate, category: l.category }))} defaultQs={code}
        onAdd={(uid, row, rate) => {
          if (rate) add("library", rate.code, rate.payload);
          add("row", uid, row);
          setCode(String(row.qs_code)); setOpen(uid);
        }} />
    </>
  );
}
