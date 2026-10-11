import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FileSpreadsheet, Plus } from "lucide-react";
import { api } from "../lib/api";
import { fmtAgo, fmtCompactMoney, fmtMoney } from "../lib/format";
import { go } from "../lib/route";
import { STAGES, type Stage, type Tender, type TenderList } from "../lib/types";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, SearchBox, Stat } from "../components/ui";

const releaseTone = (r: string) => (/HOLD/i.test(r) ? "red" : r ? "green" : "neutral") as "red" | "green" | "neutral";

function NewTender({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (t: Tender) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [client, setClient] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setFile(null); setClient(""); setErr(""); } }, [open]);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!file) { setErr("Choose a workbook first."); return; }
    setBusy(true); setErr("");
    try { onCreated(await api.createTender(file, client)); } catch (x) { setErr(x instanceof Error ? x.message : "Upload failed."); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="New tender">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted-foreground">Upload the Master Estimate Workbook. The platform recalculates every figure, creates the tender and saves this as its first revision.</p>
        <div className="border-2 border-dashed px-4 py-6 text-center">
          <FileSpreadsheet className="mx-auto mb-2 text-muted-foreground" size={24} strokeWidth={1.5} aria-hidden />
          <div className="min-h-5 break-all text-sm">{file ? file.name : "No file chosen"}</div>
          <button type="button" className="btn btn-ghost mt-3" onClick={() => ref.current?.click()}>Choose workbook (.xlsx)</button>
          <input ref={ref} type="file" accept=".xlsx" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <label className="block"><span className="label">Client or head contractor (optional)</span>
          <input value={client} onChange={(e) => setClient(e.target.value)} maxLength={160} className="mt-1 h-10 w-full border bg-background px-3 text-sm focus:border-primary" /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-solid" disabled={busy}>{busy ? "Calculating…" : "Create tender"}</button>
        </div>
      </form>
    </Modal>
  );
}

function StageSelect({ t, onChange }: { t: Tender; onChange: (s: Stage) => void }) {
  return (
    <select aria-label={`Stage for ${t.name}`} value={t.stage} onClick={(e) => e.stopPropagation()} onChange={(e) => onChange(e.target.value as Stage)}
      className="h-8 border bg-background px-2 text-xs font-medium focus:border-primary">
      {STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
    </select>
  );
}

export function Tenders() {
  const [data, setData] = useState<TenderList | null>(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [stage, setStage] = useState<"all" | Stage>("all");
  const [openNew, setOpenNew] = useState(false);

  const load = useCallback(() => { api.tenders().then(setData).catch((e) => setErr(e.message)); }, []);
  useEffect(load, [load]);

  const open = (t: Tender) => go({ name: "tender", id: t.id, page: "overview", rev: null });
  const changeStage = async (t: Tender, s: Stage) => {
    if (!data) return;
    const prev = data;
    setData({ ...data, tenders: data.tenders.map((x) => (x.id === t.id ? { ...x, stage: s } : x)) });
    try { await api.setStage(t.id, s); load(); } catch (e) { setData(prev); setErr(e instanceof Error ? e.message : "Couldn't update the stage."); }
  };

  const rows = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (data?.tenders ?? []).filter((t) => (stage === "all" || t.stage === stage) && (!term || `${t.name} ${t.client} ${t.location} ${t.summary.label}`.toLowerCase().includes(term)));
  }, [data, q, stage]);

  const by = data?.totals.by_stage;
  const decided = (by?.won.count ?? 0) + (by?.lost.count ?? 0);
  const kpi = (s: Stage, label: string) => <Stat label={label} value={fmtCompactMoney(by?.[s].value ?? 0)} sub={`${by?.[s].count ?? 0} tender${by?.[s].count === 1 ? "" : "s"}`} />;

  return (
    <main className="mx-auto max-w-[88rem] px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader title="Tenders" sub="Every tender in your workspace. Open one to see its estimate, revisions and what changed between them."
        actions={<button className="btn btn-solid" onClick={() => setOpenNew(true)}><Plus size={14} aria-hidden /> New tender</button>} />
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {!data && !err && <div className="text-sm text-muted-foreground" aria-live="polite">Loading tenders…</div>}

      {data && data.totals.count === 0 && (
        <Empty title="No tenders yet" body="Upload a Master Estimate Workbook to create your first tender. Each later version you upload becomes a revision you can compare." />
      )}

      {data && data.totals.count > 0 && (
        <>
          <Panel className="mb-4">
            <div className="grid grid-cols-2 gap-x-6 gap-y-5 lg:grid-cols-5">
              {kpi("estimating", "Estimating")}
              {kpi("submitted", "Submitted")}
              {kpi("won", "Won")}
              {kpi("lost", "Lost")}
              <Stat label="Win rate" value={decided ? `${Math.round(((by?.won.count ?? 0) / decided) * 100)}%` : "—"} sub={decided ? `${decided} decided` : "No decided tenders yet"} />
            </div>
          </Panel>

          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div role="tablist" aria-label="Filter by stage" className="flex flex-wrap border">
              {([{ id: "all", label: "All" }, ...STAGES] as { id: "all" | Stage; label: string }[]).map((s) => {
                const n = s.id === "all" ? data.totals.count : by?.[s.id].count ?? 0;
                const on = stage === s.id;
                return (
                  <button key={s.id} role="tab" aria-selected={on} onClick={() => setStage(s.id)}
                    className={`px-3 py-2 font-heading text-2xs font-bold uppercase tracking-wider ${on ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
                    {s.label} <span className="ml-1 font-mono font-normal opacity-70">{n}</span>
                  </button>
                );
              })}
            </div>
            <div className="ml-auto"><SearchBox value={q} onChange={setQ} placeholder="Search tenders" /></div>
          </div>

          {rows.length === 0 ? <Empty title="No matching tenders" body="Try a different stage or search term." /> : (
            <>
              <Panel flush className="hidden md:block">
                <table className="grid-table">
                  <thead><tr>
                    <th>Tender</th><th className="w-36">Stage</th><th className="w-40">Latest revision</th>
                    <th className="w-40 text-right">Tender value</th><th className="w-44">Release</th><th className="w-28 text-right">Updated</th>
                  </tr></thead>
                  <tbody>
                    {rows.map((t) => (
                      <tr key={t.id} className="cursor-pointer" onClick={() => open(t)}>
                        <td>
                          <a href={`#/tenders/${t.id}/overview`} className="font-medium underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>{t.name}</a>
                          <div className="mt-0.5 text-xs text-muted-foreground">{[t.client, t.location].filter(Boolean).join(" · ") || "—"}</div>
                        </td>
                        <td><StageSelect t={t} onChange={(s) => changeStage(t, s)} /></td>
                        <td><Chip tone="neutral">{t.summary.label}</Chip> <span className="ml-1 text-xs text-muted-foreground">{t.latest_rev} revision{t.latest_rev === 1 ? "" : "s"}</span></td>
                        <td className="num font-medium">{fmtMoney(t.summary.all_in)}</td>
                        <td><Chip tone={releaseTone(t.summary.release)}>{t.summary.release || "—"}</Chip></td>
                        <td className="num text-xs text-muted-foreground">{fmtAgo(t.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <ul className="space-y-3 md:hidden">
                {rows.map((t) => (
                  <li key={t.id} className="panel p-4" onClick={() => open(t)}>
                    <a href={`#/tenders/${t.id}/overview`} className="font-heading text-sm font-bold uppercase leading-snug" onClick={(e) => e.stopPropagation()}>{t.name}</a>
                    <div className="mt-1 text-xs text-muted-foreground">{[t.client, t.location].filter(Boolean).join(" · ") || "—"}</div>
                    <div className="num mt-3 !text-left text-xl font-semibold">{fmtMoney(t.summary.all_in)}</div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Chip tone="neutral">{t.summary.label}</Chip>
                      <Chip tone={releaseTone(t.summary.release)}>{t.summary.release || "—"}</Chip>
                      <span className="ml-auto text-xs text-muted-foreground">{fmtAgo(t.updated_at)}</span>
                    </div>
                    <div className="mt-3"><StageSelect t={t} onChange={(s) => changeStage(t, s)} /></div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      <NewTender open={openNew} onClose={() => setOpenNew(false)} onCreated={(t) => { setOpenNew(false); go({ name: "tender", id: t.id, page: "overview", rev: null }); }} />
    </main>
  );
}
