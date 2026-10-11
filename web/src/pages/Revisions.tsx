import { Fragment, useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtDate, fmtMoney, fmtNum, fmtPct } from "../lib/format";
import { go } from "../lib/route";
import type { Diff, RevisionInfo, TenderDetail } from "../lib/types";
import { Chip, Empty, Money, PageHeader, Panel, Select } from "../components/ui";

const signed = (v: number) => (Math.abs(v) < 0.005 ? "—" : `${v > 0 ? "+" : "-"}${fmtMoney(Math.abs(v))}`);
const Delta = ({ v }: { v: number }) => <span className="num inline-block font-medium">{signed(v)}</span>;

function explain(d: Diff, a: RevisionInfo, b: RevisionInfo): string[] {
  const out: string[] = [];
  const all = d.headline.find((h) => h.key === "all_in");
  if (d.identical) return [`${a.label} and ${b.label} are identical: no cost, quantity, rate or commercial setting differs.`];
  if (all && Math.abs(all.delta) >= 0.005) out.push(`Working all-in tender moves ${signed(all.delta)} from ${fmtMoney(all.a)} to ${fmtMoney(all.b)}.`);
  if (d.settings.length) out.push(`Commercial settings changed: ${d.settings.map((s) => `${s.label} ${fmtPct(s.a, 1)} → ${fmtPct(s.b, 1)}`).join("; ")}.`);
  if (d.counts.qs_changed === 0 && d.counts.buildup_changed === 0) out.push("No quantity, rate or build-up changes: every direct cost is identical.");
  else out.push(`${d.counts.qs_changed} QS item${d.counts.qs_changed === 1 ? "" : "s"} and ${d.counts.buildup_changed} build-up row${d.counts.buildup_changed === 1 ? "" : "s"} changed.`);
  return out;
}

function Compare({ detail }: { detail: TenderDetail }) {
  const revs = detail.revisions;
  const [a, setA] = useState(revs.length > 1 ? revs[1].n : revs[0].n);
  const [b, setB] = useState(revs[0].n);
  const [res, setRes] = useState<{ a: RevisionInfo; b: RevisionInfo; diff: Diff } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (a === b) { setRes(null); return; }
    setErr(""); setRes(null);
    api.compare(detail.id, a, b).then(setRes).catch((e) => setErr(e.message));
  }, [detail.id, a, b]);
  const opts = revs.map((r) => ({ value: String(r.n), label: `${r.label} (#${r.n})` }));
  const d = res?.diff;

  return (
    <Panel title="Compare revisions" className="mt-6">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span className="label">From</span><Select label="From revision" value={String(a)} onChange={(v) => setA(+v)} options={opts} />
        <span className="label">To</span><Select label="To revision" value={String(b)} onChange={(v) => setB(+v)} options={opts} />
      </div>
      {revs.length < 2 && <Empty title="Only one revision" body="Upload a later version of the workbook to compare what changed." />}
      {revs.length > 1 && a === b && <Empty title="Pick two different revisions" body="Choose an earlier and a later revision to see what changed." />}
      {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {d && res && (
        <div className="space-y-6">
          <div className="border-l-2 border-primary bg-muted/50 px-4 py-3 text-sm leading-relaxed">
            {explain(d, res.a, res.b).map((l) => <p key={l} className="[&+p]:mt-1">{l}</p>)}
          </div>

          <div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>Headline</th><th className="hidden text-right sm:table-cell">{res.a.label}</th><th className="text-right">{res.b.label}</th><th className="text-right">Change</th></tr></thead>
            <tbody>{d.headline.map((h) => <tr key={h.key}><td>{h.label}</td><td className="num hidden sm:table-cell"><Money v={h.a} /></td><td className="num"><Money v={h.b} /></td><td className="num"><Delta v={h.delta} /></td></tr>)}</tbody>
          </table></div>

          {d.settings.length > 0 && <div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>Commercial setting</th><th className="text-right">{res.a.label}</th><th className="text-right">{res.b.label}</th></tr></thead>
            <tbody>{d.settings.map((s) => <tr key={s.key}><td>{s.label}</td><td className="num">{fmtPct(s.a, 1)}</td><td className="num">{fmtPct(s.b, 1)}</td></tr>)}</tbody>
          </table></div>}

          {d.commercial.length > 0 && <div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>Commercial line</th><th className="hidden text-right sm:table-cell">{res.a.label}</th><th className="text-right">{res.b.label}</th><th className="text-right">Change</th></tr></thead>
            <tbody>{d.commercial.map((c) => <tr key={c.ref}><td><span className="font-mono text-xs">{c.ref}</span> {c.name}</td><td className="num hidden sm:table-cell"><Money v={c.amount_a} dash0 /></td><td className="num"><Money v={c.amount_b} dash0 /></td><td className="num"><Delta v={c.delta} /></td></tr>)}</tbody>
          </table></div>}

          {d.overlays.length > 0 && <div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>Subcontract package</th><th className="hidden text-right sm:table-cell">{res.a.label}</th><th className="text-right">{res.b.label}</th><th className="text-right">Change</th></tr></thead>
            <tbody>{d.overlays.map((o) => <tr key={o.name}><td>{o.name}</td><td className="num hidden sm:table-cell"><Money v={o.a} dash0 /></td><td className="num"><Money v={o.b} dash0 /></td><td className="num"><Delta v={o.delta} /></td></tr>)}</tbody>
          </table></div>}

          {d.qs.length > 0 && <div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>QS item</th><th className="hidden text-right sm:table-cell">Qty change</th><th className="hidden text-right sm:table-cell">{res.a.label}</th><th className="text-right">{res.b.label}</th><th className="text-right">Change</th></tr></thead>
            <tbody>{d.qs.map((q) => <tr key={q.code}>
              <td><span className="font-mono text-xs">{q.code}</span> {q.description} {q.kind !== "changed" && <Chip tone="neutral">{q.kind}</Chip>}</td>
              <td className="num hidden sm:table-cell">{q.qty_a === q.qty_b ? "—" : `${fmtNum(q.qty_a)} → ${fmtNum(q.qty_b)} ${q.unit}`}</td>
              <td className="num hidden sm:table-cell"><Money v={q.amount_a} dash0 /></td><td className="num"><Money v={q.amount_b} dash0 /></td><td className="num"><Delta v={q.delta} /></td></tr>)}</tbody>
          </table></div>}

          {d.buildup.length > 0 && <Fragment><div className="overflow-x-auto"><table className="grid-table">
            <thead><tr><th>Build-up row</th><th className="hidden text-right sm:table-cell">Rate</th><th className="hidden text-right sm:table-cell">{res.a.label}</th><th className="text-right">{res.b.label}</th><th className="text-right">Change</th></tr></thead>
            <tbody>{d.buildup.slice(0, 40).map((r) => <tr key={r.row_id}>
              <td><span className="font-mono text-xs">{r.row_id}</span> {r.task} {r.kind !== "changed" && <Chip tone="neutral">{r.kind}</Chip>}</td>
              <td className="num hidden sm:table-cell">{r.rate_a === r.rate_b ? "—" : `${fmtMoney(r.rate_a)} → ${fmtMoney(r.rate_b)}`}</td>
              <td className="num hidden sm:table-cell"><Money v={r.cost_a} dash0 /></td><td className="num"><Money v={r.cost_b} dash0 /></td><td className="num"><Delta v={r.delta} /></td></tr>)}</tbody>
          </table></div>{d.buildup.length > 40 && <p className="text-xs text-muted-foreground">Showing the 40 largest of {d.buildup.length} changed rows.</p>}</Fragment>}
        </div>
      )}
    </Panel>
  );
}

export function Revisions({ detail, current, onAdd }: { detail: TenderDetail; current: number; onAdd: () => void }) {
  return (
    <>
      <PageHeader title="Revisions" sub="Every uploaded version is kept exactly as received and never changed. Compare any two to see what moved the price."
        actions={<button className="btn btn-solid" onClick={onAdd}>Upload new revision</button>} />
      <Panel flush>
        <div className="overflow-x-auto"><table className="grid-table">
          <thead><tr><th>Revision</th><th className="hidden sm:table-cell">Uploaded</th><th className="hidden md:table-cell">File</th><th className="text-right">Working all-in</th><th className="w-24" /></tr></thead>
          <tbody>
            {detail.revisions.map((r) => (
              <tr key={r.n}>
                <td><span className="font-medium">{r.label}</span> {r.n === detail.latest_rev && <Chip tone="solid">Latest</Chip>} {r.n === current && r.n !== detail.latest_rev && <Chip tone="neutral">Viewing</Chip>}</td>
                <td className="hidden sm:table-cell">{fmtDate(r.created_at)}</td>
                <td className="hidden break-all text-xs text-muted-foreground md:table-cell">{r.source_filename}</td>
                <td className="num"><Money v={r.all_in} /></td>
                <td><button className="btn btn-ghost !px-2 !py-1" onClick={() => go({ name: "tender", id: detail.id, page: "overview", rev: r.n === detail.latest_rev ? null : r.n })}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Panel>
      <Compare key={`${detail.id}-${detail.latest_rev}`} detail={detail} />
    </>
  );
}
