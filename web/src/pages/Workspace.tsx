import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FileUp } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { go } from "../lib/route";
import type { Change, Estimate, RevisionInfo, TenderDetail } from "../lib/types";
import { editKey, EditProvider, toApi, type DraftEdit, type EditCtx } from "../lib/edit";
import { fmtMoney, fmtNum } from "../lib/format";
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
        <p className="text-sm text-muted-foreground">The new workbook is recalculated and saved as the next revision. Earlier revisions are kept unchanged. If you upload a file that was already saved before editing existed, that revision is switched on for editing instead.</p>
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

const FIELD_NAME: Record<string, string> = {
  quantity: "Quantity", job_rate_override: "Job rate", productivity_rate: "Productivity", duration_override_hrs: "Hours override",
  count: "Count / factor", manual_qty: "Quantity", utilisation: "Utilisation", waste: "Waste", verified: "Verified",
  weather_exposed: "Weather exposed", include: "Included", pct: "Percentage", pc_sum: "Amount", amount: "Amount",
  recovery_allowance: "Allowance", confirmed_overlap: "Amount",
};
const PCT_FIELDS = new Set(["pct", "utilisation", "waste"]);
const MONEY_FIELDS = new Set(["job_rate_override", "pc_sum", "amount", "recovery_allowance", "confirmed_overlap"]);
function showValue(field: string, v: string): string {
  if (v === "") return "blank";
  if (field === "verified" || field === "weather_exposed" || field === "include") return v === "Yes" ? "Yes" : "No";
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  if (PCT_FIELDS.has(field)) return `${Number((n * 100).toFixed(4))}%`;
  return MONEY_FIELDS.has(field) ? fmtMoney(n) : fmtNum(n);
}

function SaveEdits({ open, onClose, changes, defaultLabel, onSave }: { open: boolean; onClose: () => void; changes: Change[]; defaultLabel: string; onSave: (label: string, note: string) => Promise<void> }) {
  const [label, setLabel] = useState(defaultLabel);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setLabel(defaultLabel); setNote(""); setErr(""); } }, [open, defaultLabel]);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await onSave(label, note); } catch (x) { setErr(x instanceof Error ? x.message : "Couldn't save."); } finally { setBusy(false); }
  };
  const input = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  return (
    <Modal open={open} onClose={onClose} title="Save as new revision">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted-foreground">This creates a new revision. The revision you started from stays exactly as it is.</p>
        <div className="max-h-52 overflow-y-auto border">
          <table className="grid-table"><thead><tr><th>Change</th><th className="text-right">Was</th><th className="text-right">Now</th></tr></thead>
            <tbody>{changes.map((c) => <tr key={`${c.target}${c.key}${c.field}`}><td><div className="font-medium">{FIELD_NAME[c.field] ?? c.field}</div><div className="text-xs text-muted-foreground">{c.label}</div></td><td className="num">{showValue(c.field, c.before)}</td><td className="num font-medium">{showValue(c.field, c.after)}</td></tr>)}</tbody></table>
        </div>
        <label className="block"><span className="label">Revision name</span><input className={`${input} h-10`} value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} /></label>
        <label className="block"><span className="label">Reason for the change (required)</span>
          <textarea className={`${input} py-2`} rows={3} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder="For example: Quantity updated from Rev18 drawings" /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Back</button>
          <button className="btn btn-solid" disabled={busy || note.trim().length < 5}>{busy ? "Saving…" : "Save revision"}</button>
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

  // Revisions are immutable once saved, so a loaded revision can be kept for the whole visit.
  // Switching menu pages must never refetch or blank the estimate; only a new tender or revision loads data.
  const cache = useRef(new Map<string, Estimate>());
  const pageRef = useRef(page);
  pageRef.current = page;

  const loadDetail = useCallback(async () => {
    try { setDetail(await api.tender(id)); }
    catch (e) { setErr(e instanceof Error ? e.message : "Couldn't load this tender."); }
  }, [id]);
  useEffect(() => { setDetail(null); setEst(null); setErr(""); loadDetail(); }, [id, loadDetail]);

  const wanted = rev ?? detail?.latest_rev ?? null;
  useEffect(() => {
    if (!detail || wanted === null) return;
    if (!detail.revisions.some((r) => r.n === wanted)) { go({ name: "tender", id, page: pageRef.current, rev: null }); return; }
    const key = `${id}:${wanted}`;
    const hit = cache.current.get(key);
    if (hit) { setEst(hit); return; }
    let live = true;
    setEst(null);
    api.revision(id, wanted)
      .then((r) => { cache.current.set(key, r.estimate); if (live) setEst(r.estimate); })
      .catch((e) => { if (live) setErr(e instanceof Error ? e.message : "Couldn't load this revision."); });
    return () => { live = false; };
  }, [detail, id, wanted]);

  // ---- editing: edits are typed values keyed by target; the server recalculates (preview) and saves (new revision)
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Record<string, DraftEdit>>({});
  const [draft, setDraft] = useState<Estimate | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [editErr, setEditErr] = useState("");
  const [calculating, setCalculating] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const exitEdit = useCallback(() => { setEditing(false); setEdits({}); setDraft(null); setChanges([]); setEditErr(""); setSaveOpen(false); }, []);
  useEffect(() => { exitEdit(); }, [id, rev, exitEdit]);

  const editList = useMemo(() => Object.values(edits).map(toApi), [edits]);
  useEffect(() => {
    if (!editing || wanted === null) return;
    if (editList.length === 0) { setDraft(null); setChanges([]); setEditErr(""); setCalculating(false); return; }
    let live = true;
    setCalculating(true);
    const t = setTimeout(() => {
      api.preview(id, wanted, editList)
        .then((r) => { if (live) { setDraft(r.estimate); setChanges(r.changes); setEditErr(""); } })
        .catch((e) => { if (live) setEditErr(e instanceof Error ? e.message : "Couldn't recalculate."); })
        .finally(() => { if (live) setCalculating(false); });
    }, 350);
    return () => { live = false; clearTimeout(t); };
  }, [editing, editList, id, wanted]);
  useEffect(() => {
    if (!editing || editList.length === 0) return;
    const f = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", f);
    return () => window.removeEventListener("beforeunload", f);
  }, [editing, editList.length]);

  const ctx = useMemo<EditCtx>(() => ({
    editing, edits,
    set: (e) => setEdits((p) => ({ ...p, [editKey(e.target, e.key, e.field)]: e })),
    reset: (t, k, f) => setEdits((p) => { const n = { ...p }; delete n[editKey(t, k, f)]; return n; }),
  }), [editing, edits]);
  const shown = editing && draft ? draft : est;

  const cur = rev ?? detail?.latest_rev ?? 1;
  const view = (p: TenderPage) => go({ name: "tender", id, page: p, rev });
  const pg: TenderPage = isTenderPage(page) ? page : "overview";
  const curInfo = detail?.revisions.find((r) => r.n === cur);
  const label = curInfo?.label ?? "";
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
              <Select label="Revision" disabled={editing} value={String(cur)} onChange={(v) => go({ name: "tender", id, page: pg, rev: +v === detail.latest_rev ? null : +v })}
                options={detail.revisions.map((r) => ({ value: String(r.n), label: `${r.label}${r.n === detail.latest_rev ? " · latest" : ""}` }))} />
              {est?.controls.cover_release && <Chip tone={/HOLD/i.test(est.controls.cover_release) ? "red" : "green"} title="Release status shown in the workbook cover">{est.controls.cover_release}</Chip>}
              {est && (est.reconciled === null
                ? <Chip tone="neutral" title="Changed inside the platform; compare with the revision it was based on">Edited in platform</Chip>
                : <Chip tone={est.reconciled ? "green" : "red"} title="Every figure is recomputed by the platform and compared with the workbook">{est.reconciled ? "Reconciled to workbook" : "Differs from workbook"}</Chip>)}
              {editing
                ? <Chip tone="solid">Editing</Chip>
                : <>
                    <button className="btn btn-solid !py-1.5" disabled={!est || !curInfo?.has_inputs} onClick={() => setEditing(true)}
                      title={curInfo && !curInfo.has_inputs ? "This revision was saved before editing was available. Upload the workbook again to edit it." : "Change quantities, rates and settings and recalculate"}>Edit</button>
                    <button className="btn btn-ghost !py-1.5" onClick={() => setUpload(true)}>New revision</button>
                  </>}
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
      <EditProvider value={ctx}>
      <main className={`mx-auto max-w-[88rem] px-4 py-6 sm:px-6 sm:py-8 ${editing ? "pb-28" : ""}`}>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        {!err && pg === "revisions" && detail && <Revisions detail={detail} current={cur} onAdd={() => setUpload(true)} />}
        {!err && pg !== "revisions" && !shown && <div className="text-sm text-muted-foreground" aria-live="polite">Loading estimate…</div>}
        {!err && shown && pg === "overview" && <Overview est={shown} go={view} />}
        {!err && shown && pg === "consolidated" && <Consolidated est={shown} />}
        {!err && shown && pg === "tender" && <Tender est={shown} />}
        {!err && shown && pg === "qs" && <QSTakeoff est={shown} openRows={(c) => { setCode(c); view("buildup"); }} />}
        {!err && shown && pg === "buildup" && <BuildUp est={shown} code={code} setCode={setCode} />}
        {!err && shown && pg === "weather" && <Weather est={shown} />}
        {!err && shown && pg === "library" && <RateLibrary est={shown} />}
      </main>
      </EditProvider>
      {editing && est && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-primary bg-background lg:left-60">
          <div className="mx-auto flex max-w-[88rem] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
            <div>
              <div className="label">Editing {label}</div>
              <div className="text-sm">{editList.length === 0 ? "No changes yet. Change a value in the tables." : `${changes.length || editList.length} change${(changes.length || editList.length) === 1 ? "" : "s"}${calculating ? " · recalculating…" : ""}`}</div>
            </div>
            {shown && editList.length > 0 && (
              <div className="font-mono text-sm" aria-live="polite">
                <span className="label mr-2 font-heading">All-in</span>{fmtMoney(est.summary.all_in)} → <strong>{fmtMoney(shown.summary.all_in)}</strong>
                <span className="ml-2">({shown.summary.all_in - est.summary.all_in >= 0 ? "+" : "-"}{fmtMoney(Math.abs(shown.summary.all_in - est.summary.all_in))})</span>
              </div>
            )}
            {editErr && !calculating && <div role="alert" className="min-w-0 flex-1 text-sm text-red-fg">{editErr}</div>}
            <div className="ml-auto flex gap-2">
              <button className="btn btn-ghost" onClick={() => { if (editList.length === 0 || window.confirm("Discard your changes?")) exitEdit(); }}>{editList.length === 0 ? "Cancel" : "Discard"}</button>
              <button className="btn btn-solid" disabled={changes.length === 0 || !!editErr || calculating} onClick={() => setSaveOpen(true)}>Review &amp; save</button>
            </div>
          </div>
        </div>
      )}
      <SaveEdits open={saveOpen} onClose={() => setSaveOpen(false)} changes={changes} defaultLabel={`${label}-ed${(detail?.latest_rev ?? 0) + 1}`}
        onSave={async (lab, note) => { await api.saveEdits(id, cur, editList, lab, note); exitEdit(); go({ name: "tender", id, page: "revisions", rev: null }); await loadDetail(); }} />
      <UploadRevision open={upload} onClose={() => setUpload(false)} tenderId={id}
        onDone={() => { setUpload(false); go({ name: "tender", id, page: "revisions", rev: null }); loadDetail(); }} />
    </Shell>
  );
}
