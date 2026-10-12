import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { FileUp } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { go } from "../lib/route";
import type { Change, Estimate, RevisionInfo, TenderDetail } from "../lib/types";
import { editKey, EditProvider, opKey, toApi, type DraftEdit, type EditCtx } from "../lib/edit";
import { fmtMoney, fmtNum } from "../lib/format";
import { isTenderPage, Shell, type TenderPage } from "../components/Shell";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { Modal } from "../components/Modal";
import { Chip, Select } from "../components/ui";
import { Overview } from "./Overview";
import { Consolidated } from "./Consolidated";
import { Tender } from "./Tender";
import { QSTakeoff } from "./QSTakeoff";
import { BuildUp } from "./BuildUp";
import { Weather } from "./Weather";
import { RateLibrary } from "./Library";
import { Outputs } from "./Outputs";
import { Register } from "./Register";
import { Quotes } from "./Quotes";
import { DriveDocs } from "./DriveDocs";
import { RiskTruth } from "./RiskTruth";
import { ManagementReserve } from "./ManagementReserve";
import { AiDraft } from "./AiDraft";
import { Takeoff } from "./Takeoff";
import { Programme } from "./Programme";
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
  weather_exposed: "Weather exposed", include: "Included", method: "Basis", pct: "Percentage", pc_sum: "Amount", amount: "Amount",
  recovery_allowance: "Allowance", confirmed_overlap: "Amount", added: "Added", removed: "Removed",
};
const PCT_FIELDS = new Set(["pct", "utilisation", "waste"]);
const MONEY_FIELDS = new Set(["job_rate_override", "pc_sum", "amount", "recovery_allowance", "confirmed_overlap"]);
function showValue(field: string, v: string): string {
  if (field === "added" || field === "removed") return v || "—";
  if (v === "") return "blank";
  if (field === "verified" || field === "weather_exposed" || field === "include") return v === "Yes" ? "Yes" : "No";
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  if (PCT_FIELDS.has(field)) return `${Number((n * 100).toFixed(4))}%`;
  return MONEY_FIELDS.has(field) ? fmtMoney(n) : fmtNum(n);
}

function ChangeRow({ c, undo }: { c: Change; undo?: () => void }) {
  const added = c.field === "added", removed = c.field === "removed";
  return (
    <li className="flex items-start gap-3 border-b px-3 py-2.5 last:border-b-0">
      <span className={`label mt-0.5 w-24 shrink-0 ${added ? "!text-green-fg" : removed ? "!text-red-fg" : ""}`}>{FIELD_NAME[c.field] ?? c.field}</span>
      <div className="min-w-0 flex-1">
        <div className="text-sm leading-snug">{c.label}</div>
        <div className="mt-0.5 break-words font-mono text-xs text-muted-foreground">
          {added ? showValue(c.field, c.after) : removed ? showValue(c.field, c.before) : <>{showValue(c.field, c.before)} <span aria-label="to">→</span> <span className="font-medium text-foreground">{showValue(c.field, c.after)}</span></>}
        </div>
      </div>
      {undo && <button className="btn btn-ghost !px-2 !py-1" onClick={undo}>Undo</button>}
    </li>
  );
}

function changeKey(c: Change): string {
  return c.field === "added" ? opKey(c.target, c.key, "add") : c.field === "removed" ? opKey(c.target, c.key, "delete") : editKey(c.target, c.key, c.field);
}

function ChangesDialog({ open, onClose, changes, edits, undoKey }: { open: boolean; onClose: () => void; changes: Change[]; edits: Record<string, DraftEdit>; undoKey: (k: string) => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Changes in this edit" wide>
      <div className="max-h-[60vh] overflow-y-auto border">
        {changes.length === 0 ? <p className="p-4 text-sm text-muted-foreground">No changes yet.</p> : (
          <ul>{changes.map((c) => {
            const k = changeKey(c);
            return <ChangeRow key={`${c.target}${c.key}${c.field}`} c={c} undo={edits[k] ? () => undoKey(k) : undefined} />;
          })}</ul>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Rows that belong to a deleted item go with it. Undo the item to bring them back.</p>
      <div className="mt-4 flex justify-end"><button className="btn btn-solid" onClick={onClose}>Done</button></div>
    </Modal>
  );
}

function SaveEdits({ open, onClose, changes, defaultLabel, onSave }: { open: boolean; onClose: () => void; changes: Change[]; defaultLabel: string; onSave: (label: string, note: string) => Promise<void> }) {
  const [label, setLabel] = useState(defaultLabel);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { if (open) { setLabel(defaultLabel); setNote(""); setErr(""); } }, [open, defaultLabel]);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr("");
    if (note.trim().length < 5) { setErr("Write a short reason for the change first (at least 5 characters). It is saved with the revision."); noteRef.current?.focus(); return; }
    setBusy(true);
    try { await onSave(label, note); } catch (x) { setErr(x instanceof Error ? x.message : "Couldn't save."); } finally { setBusy(false); }
  };
  const input = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  return (
    <Modal open={open} onClose={onClose} title="Save as new revision" wide>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted-foreground">This creates a new revision. The revision you started from stays exactly as it is.</p>
        <div className="max-h-60 overflow-y-auto border"><ul>{changes.map((c) => <ChangeRow key={`${c.target}${c.key}${c.field}`} c={c} />)}</ul></div>
        <label className="block"><span className="label">Revision name</span><input className={`${input} h-10`} value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} /></label>
        <label className="block"><span className="label">Reason for the change (required)</span>
          <textarea ref={noteRef} className={`${input} py-2 ${err && note.trim().length < 5 ? "border-red-line" : ""}`} rows={3} value={note} maxLength={2000} onChange={(e) => { setNote(e.target.value); setErr(""); }} placeholder="For example: Quantity updated from Rev18 drawings" /></label>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Back</button>
          <button className="btn btn-solid" disabled={busy}>{busy ? "Saving…" : "Save revision"}</button>
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
  const [focusUid, setFocusUid] = useState<string | null>(null);

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
  const [changesOpen, setChangesOpen] = useState(false);
  const exitEdit = useCallback(() => { setEditing(false); setEdits({}); setDraft(null); setChanges([]); setEditErr(""); setSaveOpen(false); setChangesOpen(false); }, []);
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

  const cur = rev ?? detail?.latest_rev ?? 1;
  const curInfo = detail?.revisions.find((r) => r.n === cur);
  const ctx = useMemo<EditCtx>(() => {
    const dropPrefix = (m: Record<string, DraftEdit>, prefix: string) => {
      for (const k of Object.keys(m)) if (k.startsWith(prefix)) delete m[k];
    };
    const baseRows = est?.buildup ?? [];
    return {
      editing, edits,
      canEdit: !!est && !!curInfo?.has_inputs,
      editHint: curInfo && !curInfo.has_inputs ? "This revision was saved before editing was available. Open New revision at the top and upload the same workbook again; it switches this revision on for editing." : "",
      startEdit: () => setEditing(true),
      set: (e) => setEdits((p) => ({ ...p, [editKey(e.target, e.key, e.field)]: e })),
      reset: (t, k, f) => setEdits((p) => { const n = { ...p }; delete n[editKey(t, k, f)]; return n; }),
      add: (target, key, payload) => setEdits((p) => {
        const n = { ...p };
        if (target === "schedule") dropPrefix(n, "schedule_map|");          // a new format starts with a clean mapping
        n[opKey(target, key, "add")] = { target, key, field: "", value: "", original: "", op: "add", payload };
        return n;
      }),
      remove: (target, key) => setEdits((p) => {
        const n = { ...p };
        const pendingAdd = !!n[opKey(target, key, "add")];
        const dropRow = (uid: string) => { delete n[opKey("row", uid, "add")]; dropPrefix(n, `row|${uid}|`); };
        if (target === "row") {
          dropPrefix(n, `row|${key}|`);
          if (pendingAdd) delete n[opKey("row", key, "add")]; else n[opKey("row", key, "delete")] = { target, key, field: "", value: "", original: "", op: "delete" };
        } else if (target === "qs") {
          dropPrefix(n, `qs|${key}|`);
          for (const e of Object.values(n)) if (e.target === "row" && e.op === "add" && e.payload?.qs_code === key) dropRow(e.key);
          for (const r of baseRows) if (r.qs_code === key) dropPrefix(n, `row|${r.uid}|`);
          if (pendingAdd) delete n[opKey("qs", key, "add")]; else n[opKey("qs", key, "delete")] = { target, key, field: "", value: "", original: "", op: "delete" };
        } else {
          // overlays, weather activities and the weather setup itself
          dropPrefix(n, `${target}|${key}|`);
          if (target === "weather" && key === "setup") dropPrefix(n, "weather_activity|");
          if (target === "schedule") dropPrefix(n, "schedule_map|");
          if (pendingAdd) delete n[opKey(target, key, "add")]; else n[opKey(target, key, "delete")] = { target, key, field: "", value: "", original: "", op: "delete" };
        }
        return n;
      }),
      undoKey: (k) => setEdits((p) => {
        const e = p[k]; if (!e) return p;
        const n = { ...p };
        if (e.op === "add") { // undoing an add also drops anything that depends on it
          if (e.target === "qs") for (const x of Object.values(n)) if (x.target === "row" && x.op === "add" && x.payload?.qs_code === e.key) { delete n[opKey("row", x.key, "add")]; dropPrefix(n, `row|${x.key}|`); }
          dropPrefix(n, `${e.target}|${e.key}|`);
          if (e.target === "weather" && e.key === "setup") dropPrefix(n, "weather_activity|");
          if (e.target === "schedule") dropPrefix(n, "schedule_map|");
        }
        delete n[k];
        return n;
      }),
    };
  }, [editing, edits, est, curInfo?.has_inputs]);
  const shown = editing && draft ? draft : est;

  const view = (p: TenderPage) => go({ name: "tender", id, page: p, rev });
  const pg: TenderPage = isTenderPage(page) ? page : "overview";
  const label = curInfo?.label ?? "";
  const stale = detail && cur !== detail.latest_rev;

  return (
    <Shell user={user} route={{ name: "tender", id, page: pg, rev }} tenderName={detail?.name} onLogout={onLogout}>
      {/* The bar is exactly as tall as the brand block in the side menu (4rem, border included) so the two lines run straight across; every control in it is 2.25rem tall */}
      <div className="flex min-h-16 items-center border-b bg-background">
        <div className="mx-auto flex w-full max-w-[88rem] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 sm:px-6">
          <div className="min-w-0 flex-1">
            <div className="label">Tender</div>
            <div className="truncate font-heading text-sm font-bold uppercase" title={detail?.name}>{detail?.name ?? "Loading…"}</div>
          </div>
          {detail && (
            <div className="flex flex-wrap items-center gap-2">
              <Select label="Revision" disabled={editing} value={String(cur)} onChange={(v) => go({ name: "tender", id, page: pg, rev: +v === detail.latest_rev ? null : +v })}
                options={detail.revisions.map((r) => ({ value: String(r.n), label: `${r.label}${r.n === detail.latest_rev ? " · latest" : ""}` }))} />
              {est?.controls.cover_release && <Chip bar tone={/HOLD/i.test(est.controls.cover_release) ? "red" : "green"} title="Release status shown in the workbook cover">{est.controls.cover_release}</Chip>}
              {est && (est.reconciled === null
                ? (detail.revisions.find((r) => r.n === cur)?.parent_n == null
                  ? <Chip bar tone="neutral" title="This tender was started in the platform, not from a workbook">Started in platform</Chip>
                  : <Chip bar tone="neutral" title="Changed inside the platform; compare with the revision it was based on">Edited in platform</Chip>)
                : <Chip bar tone={est.reconciled ? "green" : "red"} title="Every figure is recomputed by the platform and compared with the workbook">{est.reconciled ? "Reconciled to workbook" : "Differs from workbook"}</Chip>)}
              {editing
                ? <Chip bar tone="solid">Editing</Chip>
                : <>
                    <button className="btn btn-solid h-9 !py-0" disabled={!est || !curInfo?.has_inputs} onClick={() => setEditing(true)}
                      title={curInfo && !curInfo.has_inputs ? "This revision was saved before editing was available. Upload the workbook again to edit it." : "Change quantities, rates and settings and recalculate"}>Edit</button>
                    <button className="btn btn-ghost h-9 !py-0" onClick={() => setUpload(true)}>New revision</button>
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
        <ErrorBoundary key={pg}>
        {!err && pg === "revisions" && detail && <Revisions detail={detail} current={cur} onAdd={() => setUpload(true)} />}
        {!err && pg !== "revisions" && !shown && <div className="text-sm text-muted-foreground" aria-live="polite">Loading estimate…</div>}
        {!err && shown && pg === "overview" && <Overview est={shown} go={view} />}
        {!err && shown && pg === "consolidated" && <Consolidated est={shown} />}
        {!err && shown && pg === "tender" && <Tender est={shown} />}
        {!err && shown && pg === "qs" && <QSTakeoff est={shown} openRows={(c) => { setCode(c); view("buildup"); }} onRowAdded={(uid, c) => { setCode(c); setFocusUid(uid); view("buildup"); }} />}
        {!err && shown && pg === "buildup" && <BuildUp est={shown} code={code} setCode={setCode} focusUid={focusUid} />}
        {!err && shown && pg === "weather" && <Weather est={shown} />}
        {!err && shown && pg === "risk" && <RiskTruth est={shown} />}
        {!err && shown && pg === "reserve" && <ManagementReserve est={shown} />}
        {!err && shown && pg === "register" && <Register est={shown} />}
        {!err && shown && pg === "programme" && <Programme est={shown} />}
        {!err && shown && pg === "quotes" && <Quotes est={shown} />}
        {!err && pg === "ai" && <AiDraft tenderId={id} />}
        {!err && shown && pg === "takeoff" && <Takeoff est={shown} tenderId={id} goQs={() => view("qs")} />}
        {!err && pg === "drive" && <DriveDocs tenderId={id} />}
        {!err && shown && pg === "outputs" && <Outputs est={shown} tenderId={id} rev={cur} />}
        {!err && shown && pg === "library" && <RateLibrary est={shown} />}
        </ErrorBoundary>
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
                <span className="ml-2">({(() => { const d = Math.round(shown.summary.all_in * 100) / 100 - Math.round(est.summary.all_in * 100) / 100; return `${d >= 0 ? "+" : "-"}${fmtMoney(Math.abs(Math.round(d * 100) / 100))}`; })()})</span>
              </div>
            )}
            {editErr && !calculating && <div role="alert" className="min-w-0 flex-1 text-sm text-red-fg">{editErr}</div>}
            <div className="ml-auto flex gap-2">
              {editList.length > 0 && <button className="btn btn-ghost" onClick={() => setChangesOpen(true)}>View changes</button>}
              <button className="btn btn-ghost" onClick={() => { if (editList.length === 0 || window.confirm("Discard your changes?")) exitEdit(); }}>{editList.length === 0 ? "Cancel" : "Discard"}</button>
              <button className="btn btn-solid" disabled={changes.length === 0 || !!editErr || calculating} onClick={() => setSaveOpen(true)}>Review &amp; save</button>
            </div>
          </div>
        </div>
      )}
      <ChangesDialog open={changesOpen} onClose={() => setChangesOpen(false)} changes={changes} edits={edits} undoKey={ctx.undoKey} />
      <SaveEdits open={saveOpen} onClose={() => setSaveOpen(false)} changes={changes} defaultLabel={`${label}-ed${(detail?.latest_rev ?? 0) + 1}`}
        onSave={async (lab, note) => { await api.saveEdits(id, cur, editList, lab, note); exitEdit(); go({ name: "tender", id, page: "revisions", rev: null }); await loadDetail(); }} />
      <UploadRevision open={upload} onClose={() => setUpload(false)} tenderId={id}
        onDone={() => { setUpload(false); go({ name: "tender", id, page: "revisions", rev: null }); loadDetail(); }} />
    </Shell>
  );
}
