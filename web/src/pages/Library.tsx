import { useMemo, useState } from "react";
import type { Estimate } from "../lib/types";
import { fmtMoney } from "../lib/format";
import { Empty, PageHeader, Panel, SearchBox, Select } from "../components/ui";

export function RateLibrary({ est }: { est: Estimate }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const cats = Array.from(new Set(est.library.map((l) => l.category))).filter(Boolean).sort();
  const used = useMemo(() => new Set(est.buildup.map((b) => b.resource_code)), [est.buildup]);
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return est.library.filter((l) => (cat === "all" || l.category === cat) && (!t || `${l.code} ${l.description} ${l.source}`.toLowerCase().includes(t)));
  }, [est.library, q, cat]);
  return (
    <>
      <PageHeader title="Resource rate library" sub="True direct cost rates (excl. GST). Reusable across jobs; superseded rates are kept, never deleted."
        actions={<><SearchBox value={q} onChange={setQ} placeholder="Search code, description or source" /><Select label="Category" value={cat} onChange={setCat} options={[{ value: "all", label: "All categories" }, ...cats.map((c) => ({ value: c, label: c }))]} /></>} />
      {rows.length === 0 ? <Empty title="No rates match" body="Clear the search or category." /> : (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="grid-table min-w-[40rem]">
              <thead><tr><th className="w-36">Code</th><th>Description</th><th className="hidden w-28 sm:table-cell">Category</th><th className="w-14">Unit</th><th className="w-28 text-right">Rate</th><th className="hidden w-16 lg:table-cell">Used</th><th className="hidden lg:table-cell">Source</th></tr></thead>
              <tbody>
                {rows.map((l) => (
                  <tr key={l.code}>
                    <td className="font-mono text-xs">{l.code}</td><td>{l.description}</td>
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
      <p className="mt-3 text-xs text-muted-foreground">{rows.length} of {est.library.length} library rates.</p>
    </>
  );
}
