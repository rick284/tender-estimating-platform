import { Fragment, useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Estimate } from "../lib/types";
import { fmtNum } from "../lib/format";
import { EditNum } from "../components/EditCells";
import { AddQsDialog } from "../components/AddDialogs";
import { useEdit } from "../lib/edit";
import { Chip, Empty, Money, PageHeader, Panel, RagChip, SearchBox } from "../components/ui";

export function QSTakeoff({ est, openRows }: { est: Estimate; openRows: (code: string) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const { editing, add, remove } = useEdit();
  const items = useMemo(() => {
    const t = q.trim().toLowerCase();
    return est.qs.filter((i) => !t || `${i.code} ${i.description} ${i.section} ${i.basis}`.toLowerCase().includes(t));
  }, [est.qs, q]);
  const sections = est.sections.map((s) => ({ ...s, lines: items.filter((i) => i.section === s.section) })).filter((s) => s.lines.length);
  const total = items.reduce((a, i) => a + i.amount, 0);

  return (
    <>
      <PageHeader
        title="QS takeoff"
        sub="Measured, provided and allowance quantities with their section cost. Each amount is the sum of its resource build-up rows. Open a line for its source and status."
        actions={<>{editing && <button className="btn btn-solid" onClick={() => setAdding(true)}>Add QS item</button>}<SearchBox value={q} onChange={setQ} placeholder="Search code, description or section" /></>}
      />
      {sections.length === 0 ? <Empty title="No matching items" body="Try a different search term." /> : (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="grid-table">
              <thead>
                <tr>
                  <th className="w-24">Code</th><th>Description</th>
                  <th className="hidden w-14 sm:table-cell">Unit</th>
                  <th className="hidden w-24 text-right sm:table-cell">Qty</th>
                  <th className="hidden w-28 text-right md:table-cell">Rate</th>
                  <th className="w-32 text-right">Amount</th>
                  <th className="hidden w-24 lg:table-cell">Status</th>
                </tr>
              </thead>
              <tbody>
                {sections.map((s) => (
                  <Fragment key={s.section}>
                    <tr className="group-row"><td colSpan={2}>{s.section}</td><td className="hidden sm:table-cell" /><td className="hidden sm:table-cell" /><td className="hidden md:table-cell" /><td className="num">{<Money v={s.lines.reduce((a, i) => a + i.amount, 0)} />}</td><td className="hidden lg:table-cell" /></tr>
                    {s.lines.map((i) => {
                      const isOpen = open === i.code;
                      return (
                        <Fragment key={i.code}>
                          <tr className="cursor-pointer" onClick={() => setOpen(isOpen ? null : i.code)} aria-expanded={isOpen}>
                            <td className="font-mono text-xs"><span className="inline-flex items-center gap-1"><ChevronRight size={12} className={`transition-transform ${isOpen ? "rotate-90" : ""}`} aria-hidden />{i.code}</span></td>
                            <td>
                              <div className="leading-snug">{i.description} {i.status.includes("ADDED IN PLATFORM") && <Chip tone="neutral">New</Chip>}</div>
                              <div className="mt-1 text-xs text-muted-foreground sm:hidden">{fmtNum(i.quantity)} {i.unit} · <RagChip value={i.rag} /></div>
                            </td>
                            <td className="hidden sm:table-cell">{i.unit}</td>
                            <td className="num hidden sm:table-cell"><EditNum target="qs" id={i.code} field="quantity" original={i.quantity} label={`${i.code} quantity`} display={fmtNum(i.quantity)} /></td>
                            <td className="num hidden md:table-cell"><Money v={i.rate} dash0 /></td>
                            <td className="num"><Money v={i.amount} dash0 /></td>
                            <td className="hidden lg:table-cell"><RagChip value={i.rag} /></td>
                          </tr>
                          {isOpen && (
                            <tr>
                              <td colSpan={7} className="!bg-muted/40 !p-0">
                                <dl className="grid gap-x-8 gap-y-3 p-4 text-sm sm:grid-cols-2">
                                  {([["Quantity basis", i.basis], ["Source drawing / scope", i.source], ["Status", i.status], ["Verification", i.verification], ["Quote / reference", i.quote_ref], ["Owner", i.owner]] as const).map(([k, v]) => v ? (
                                    <div key={k}><dt className="label">{k}</dt><dd className="mt-0.5 leading-snug">{v}</dd></div>
                                  ) : null)}
                                  {i.notes && <div className="sm:col-span-2"><dt className="label">Notes / assumptions</dt><dd className="mt-0.5 leading-snug">{i.notes}</dd></div>}
                                  <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                                    <span className="label mr-1">Build-up rows</span>
                                    {i.rows.length ? i.rows.map((r) => <Chip key={r} tone="neutral">{r}</Chip>) : <span className="text-muted-foreground">None (no resources priced)</span>}
                                    {i.rows.length > 0 && <button className="btn btn-ghost ml-auto !py-1" onClick={(e) => { e.stopPropagation(); openRows(i.code); }}>View build-up</button>}
                                    {editing && <button className={`btn btn-ghost !py-1 ${i.rows.length ? "" : "ml-auto"}`} onClick={(e) => {
                                      e.stopPropagation();
                                      if (window.confirm(i.rows.length ? `Delete ${i.code} and its ${i.rows.length} build-up row${i.rows.length === 1 ? "" : "s"}? You can undo this before saving.` : `Delete ${i.code}? You can undo this before saving.`)) remove("qs", i.code);
                                    }}>Delete item</button>}
                                  </div>
                                </dl>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </Fragment>
                ))}
                <tr className="total-row"><td colSpan={2}>Total direct cost</td><td className="hidden sm:table-cell" /><td className="hidden sm:table-cell" /><td className="hidden md:table-cell" /><td className="num"><Money v={total} /></td><td className="hidden lg:table-cell" /></tr>
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <AddQsDialog open={adding} onClose={() => setAdding(false)} sections={est.sections.map((x) => x.section)} usedCodes={new Set(est.qs.map((x) => x.code))}
        onAdd={(code, payload) => { add("qs", code, payload); setOpen(code); }} />
    </>
  );
}
