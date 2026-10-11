import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { FileUp } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { go } from "../lib/route";
import type { Estimate, RevisionInfo, TenderDetail } from "../lib/types";
import { isTenderPage, Shell, type TenderPage } from "../components/Shell";
import { Modal } from "../components/Modal";
import { Chip, Select } from "../components/ui";
import { Overview } from "./Overview";
import { Consolidated } from "./Consolidated";
import { Tender } from "./Tender";
import { QSTakeoff } from "./QSTakeoff";
import { BuildUp } from "./BuildUp";
import { Weather } from "./Weather";
import { RateLibrary } from "./Library";
import { Revisions } from "./Revisions";
import type { User } from "../lib/types";

function UploadRevision({ open, onClose, tenderId, onDone }: { open: boolean; onClose: () => void; tenderId: string; onDone: (r: RevisionInfo) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [needsConfirm, setNeedsConfirm] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setFile(null); setErr(""); setNeedsConfirm(false); setConfirm(false); } }, [open]);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!file) { setErr("Choose a workbook first."); return; }
    setBusy(true); setErr("");
    try { onDone(await api.addRevision(tenderId, file, confirm)); }
    catch (x) {
      const m = x instanceof Error ? x.message : "Upload failed.";
      setErr(m); setNeedsConfirm(x instanceof ApiError && x.status === 409 && /not ".*"\. Upload it as a new tender/.test(m));
    } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Upload new revision">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted-foreground">The new workbook is recalculated and saved as the next revision. Earlier revisions are kept unchanged.</p>
        <div className="border-2 border-dashed px-4 py-6 text-center">
          <FileUp className="mx-auto mb-2 text-muted-foreground" size={24} strokeWidth={1.5} aria-hidden />
          <div className="min-h-5 break-all text-sm">{file ? file.name : "No file chosen"}</div>
          <button type="button" className="btn btn-ghost mt-3" onClick={() => ref.current?.click()}>Choose workbook (.xlsx)</button>
          <input ref={ref} type="file" accept=".xlsx" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setErr(""); setNeedsConfirm(false); setConfirm(false); }} />
        </div>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        {needsConfirm && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} /> This workbook does belong to this tender.</label>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-solid" disabled={busy || (needsConfirm && !confirm)}>{busy ? "Calculating…" : "Upload revision"}</button>
        </div>
      </form>
    </Modal>
  );
}

export function Workspace({ id, page, rev, user, onLogout }: { id: string; page: string; rev: number | null; user: User; onLogout: () => void }) {
  const [detail, setDetail] = useState<TenderDetail | null>(null);
  const [est, setEst] = useState<Estimate | null>(null);
  const [err, setErr] = useState("");
  const [upload, setUpload] = useState(false);
  const [code, setCode] = useState("all");

  const load = useCallback(async () => {
    setErr("");
    try {
      const d = await api.tender(id);
      setDetail(d);
      const n = rev ?? d.latest_rev;
      if (!d.revisions.some((r) => r.n === n)) { go({ name: "tender", id, page, rev: null }); return; }
      setEst(null);
      setEst((await api.revision(id, n)).estimate);
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't load this tender."); }
  }, [id, rev, page]);
  useEffect(() => { setDetail(null); setEst(null); }, [id]);
  useEffect(() => { load(); }, [load]);

  const cur = rev ?? detail?.latest_rev ?? 1;
  const view = (p: TenderPage) => go({ name: "tender", id, page: p, rev });
  const pg: TenderPage = isTenderPage(page) ? page : "overview";
  const label = detail?.revisions.find((r) => r.n === cur)?.label ?? "";
  const stale = detail && cur !== detail.latest_rev;

  return (
    <Shell user={user} route={{ name: "tender", id, page: pg, rev }} tenderName={detail?.name} onLogout={onLogout}>
      <div className="border-b bg-background">
        <div className="mx-auto flex max-w-[88rem] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <div className="label">Tender</div>
            <div className="truncate font-heading text-sm font-bold uppercase" title={detail?.name}>{detail?.name ?? "Loading…"}</div>
          </div>
          {detail && (
            <div className="flex flex-wrap items-center gap-2">
              <Select label="Revision" value={String(cur)} onChange={(v) => go({ name: "tender", id, page: pg, rev: +v === detail.latest_rev ? null : +v })}
                options={detail.revisions.map((r) => ({ value: String(r.n), label: `${r.label}${r.n === detail.latest_rev ? " · latest" : ""}` }))} />
              {est?.controls.cover_release && <Chip tone={/HOLD/i.test(est.controls.cover_release) ? "red" : "green"} title="Release status shown in the workbook cover">{est.controls.cover_release}</Chip>}
              {est && <Chip tone={est.reconciled ? "green" : "red"} title="Every figure is recomputed by the platform and compared with the workbook">{est.reconciled ? "Reconciled to workbook" : "Differs from workbook"}</Chip>}
              <button className="btn btn-ghost !py-1.5" onClick={() => setUpload(true)}>New revision</button>
            </div>
          )}
        </div>
      </div>
      {stale && detail && (
        <div className="border-b border-amber-line bg-amber-bg">
          <div className="mx-auto flex max-w-[88rem] flex-wrap items-center gap-3 px-4 py-2 text-sm text-amber-fg sm:px-6">
            You're viewing {label}, an earlier revision. The latest is {detail.revisions[0].label}.
            <button className="font-medium underline underline-offset-4" onClick={() => go({ name: "tender", id, page: pg, rev: null })}>Go to latest</button>
          </div>
        </div>
      )}
      <main className="mx-auto max-w-[88rem] px-4 py-6 sm:px-6 sm:py-8">
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        {!err && pg === "revisions" && detail && <Revisions detail={detail} current={cur} onAdd={() => setUpload(true)} />}
        {!err && pg !== "revisions" && !est && <div className="text-sm text-muted-foreground" aria-live="polite">Loading estimate…</div>}
        {!err && est && pg === "overview" && <Overview est={est} go={view} />}
        {!err && est && pg === "consolidated" && <Consolidated est={est} />}
        {!err && est && pg === "tender" && <Tender est={est} />}
        {!err && est && pg === "qs" && <QSTakeoff est={est} openRows={(c) => { setCode(c); view("buildup"); }} />}
        {!err && est && pg === "buildup" && <BuildUp est={est} code={code} setCode={setCode} />}
        {!err && est && pg === "weather" && <Weather est={est} />}
        {!err && est && pg === "library" && <RateLibrary est={est} />}
      </main>
      <UploadRevision open={upload} onClose={() => setUpload(false)} tenderId={id}
        onDone={() => { setUpload(false); go({ name: "tender", id, page: "revisions", rev: null }); load(); }} />
    </Shell>
  );
}
