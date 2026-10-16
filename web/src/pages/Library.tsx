import { useMemo, useState } from "react";
import type { Estimate } from "../lib/types";
import { fmtMoney } from "../lib/format";
import { Chip, Empty, PageHeader, Panel, SearchBox, Select } from "../components/ui";
import { LabourBuilder } from "../components/LabourBuilder";
import { useEdit } from "../lib/edit";

export function RateLibrary({ est }: { est: Estimate }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const { editing, add } = useEdit();
  const [dlg, setDlg] = useState<{ code: string } | "new" | null>(null);
  const builds = est.labour_builds ?? {};
  const cats = Array.from(new Set(est.library.map((l) => l.category))).filter(Boolean).sort();
  const used = useMemo(() => new Set(est.buildup.map((b) => b.resource_code)), [est.buildup]);
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return est.library.filter((l) => (cat === "all" || l.category === cat) && (!t || `${l.code} ${l.description} ${l.source}`.toLowerCase().includes(t)));
  }, [est.library, q, cat]);
  return (
    <>
      <PageHeader title="Resource rate library" sub="True direct cost rates (excl. GST). Reusable across jobs; superseded rates are kept, never deleted."
        actions={<>{editing && <button className="btn btn-solid" onClick={() => setDlg("new")}>Build labour rate</button>}<SearchBox value={q} onChange={setQ} placeholder="Search code, description or source" /><Select label="Category" value={cat} onChange={setCat} options={[{ value: "all", label: "All categories" }, ...cats.map((c) => ({ value: c, label: c }))]} /></>} />
      {rows.length === 0 ? <Empty title="No rates match" body="Clear the search or category." /> : (
        <Panel flush>
          <div className="grid-scroll">
            <table className="grid-table min-w-[48rem]">
              <thead><tr><th className="w-36">Code</th><th className="min-w-[14rem]">Description</th><th className="hidden w-28 sm:table-cell">Category</th><th className="w-20">Unit</th><th className="w-28 text-right">Rate</th><th className="hidden w-16 lg:table-cell">Used</th><th className="hidden lg:table-cell">Source</th></tr></thead>
              <tbody>
                {rows.map((l) => (
                  <tr key={l.code}>
                    <td className="nowrap whitespace-nowrap font-mono text-xs">{l.code}</td><td>{l.description}{builds[l.code] && <> <button type="button" className="ml-1 align-middle" onClick={() => setDlg({ code: l.code })} title="Show how this rate was built"><Chip tone={builds[l.code].status === "GREEN" ? "green" : builds[l.code].status === "RED" ? "red" : "amber"}>build-up {builds[l.code].status}</Chip></button></>}</td>
                    <td className="hidden text-muted-foreground sm:table-cell">{l.category}</td><td>{l.unit}</td>
                    <td className="num">{fmtMoney(l.rate)}</td>
                    <td className="hidden lg:table-cell">{used.has(l.code) ? "Yes" : <span className="text-muted-foreground">—</span>}</td>
                    <td className="hidden max-w-sm truncate text-muted-foreground lg:table-cell" title={l.source}>{l.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      <LabourBuilder open={dlg !== null} onClose={() => setDlg(null)} editing={editing} existing={est.library.map((l) => l.code)}
        build={dlg && dlg !== "new" ? { code: dlg.code, calc: builds[dlg.code] } : undefined} onSave={(code, inputs) => add("labour", code, inputs)} />
      <p className="mt-3 text-xs text-muted-foreground">{rows.length} of {est.library.length} library rates.</p>
    </>
  );
}
