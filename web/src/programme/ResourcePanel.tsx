import { useMemo } from "react";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore (plain JavaScript module)
import { resourceUsage } from "./programSchedule";

/* eslint-disable @typescript-eslint/no-explicit-any */
/** Who and what the programme uses: tasks, unit-days and peak units per day. */
export function ResourcePanel({ tasks, cal }: { tasks: any[]; cal: any }) {
  const rows: any[] = useMemo(() => resourceUsage(tasks, cal), [tasks, cal]);
  const max = Math.max(1, ...rows.map((r) => r.unitDays));
  if (!rows.length) return <div className="border bg-card p-8 text-center text-sm text-muted-foreground">No resources assigned yet. Select a task and use its Resources button to assign some.</div>;
  return (
    <div className="grid-scroll border bg-card" data-testid="program-resource-panel">
      <table className="grid-table">
        <thead><tr><th>Resource</th><th>Type</th><th className="text-right">Tasks</th><th className="text-right">Unit-days</th><th className="min-w-[10rem]">Share of work</th><th className="text-right">Peak units / day</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>{r.name}{r.custom && <span className="ml-1 text-2xs text-muted-foreground">(custom)</span>}</td>
              <td><span className="border px-1 text-2xs uppercase">{r.type || "other"}</span></td>
              <td className="num">{r.tasks}</td>
              <td className="num">{Math.round(r.unitDays * 10) / 10}</td>
              <td><div className="h-2 bg-muted"><div className="h-2 bg-primary" style={{ width: `${(r.unitDays / max) * 100}%` }} /></div></td>
              <td className="num">{Math.round(r.peak * 10) / 10}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
