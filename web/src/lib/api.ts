import type { WeatherCatalog, Change, Diff, Edit, Estimate, RevisionInfo, Stage, Tender, TenderDetail, TenderList, User } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";
const TOKEN_KEY = "tp_token";

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

const LONG = 600_000;           // AI takeoff / drafting runs can take several minutes
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 90_000): Promise<T> {
  const headers = new Headers(init.headers);
  const t = tokenStore.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const reads = (init.method ?? "GET").toUpperCase() === "GET";
  let res: Response | undefined;
  // The free server sleeps when idle and restarts after every update: a read that fails to connect is retried twice before the user sees a message.
  for (let attempt = 0; attempt < (reads ? 3 : 1); attempt++) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try { res = await fetch(`${BASE}${path}`, { ...init, headers, signal: ctl.signal }); break; }
    catch (e) {
      const aborted = e instanceof DOMException && e.name === "AbortError";
      if (!aborted && attempt < 2 && reads) { await sleep(attempt === 0 ? 3000 : 8000); continue; }
      throw new ApiError(0, aborted
        ? `The server took too long to answer (over ${Math.round(timeoutMs / 1000)} seconds). If this was an AI run it may still have finished: open the page again to see its results. Otherwise the server may be waking up; wait a minute and try again.`
        : "Can't reach the server. It may be restarting (it sleeps when idle and restarts after every update), so wait a minute and try again. If it keeps happening, check your internet connection or a VPN / ad blocker.");
    } finally { clearTimeout(timer); }
  }
  if (!res) throw new ApiError(0, "Can't reach the server. Try again in a minute.");
  if (!res.ok) {
    let msg = `The server returned an error (${res.status}).`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail) && j.detail[0]?.msg) msg = `Invalid request: ${j.detail[0].msg}`;
    } catch { /* ignore */ }
    if (res.status === 401 && t) onUnauthorized();
    throw new ApiError(res.status, msg);
  }
  return res.json();
}
const form = (o: Record<string, string | boolean | File>) => {
  const fd = new FormData();
  Object.entries(o).forEach(([k, v]) => fd.append(k, v instanceof File ? v : String(v)));
  return fd;
};

/** Download a generated document (needs the sign-in token, so it can't be a plain link). */
async function download(path: string): Promise<void> {
  const t = tokenStore.get();
  const res = await fetch(`${BASE}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (!res.ok) {
    let msg = `The server returned an error (${res.status}).`;
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? "download";
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export interface TimeEntry {
  kind: "session" | "manual"; id: string; date: string; tender_id: string; tender_name: string; start: string; end: string; elapsed_seconds: number; active_seconds: number; note: string; summary: string[]; open: boolean;
}
export interface TimeGroup {
  date: string; tender_id: string; tender_name: string; active_seconds: number; elapsed_seconds: number; sessions: number; work: string[]; billable_minutes: number;
  ai: { seconds: number; runs: number; input_tokens: number; output_tokens: number };
}
export interface Timesheet {
  round_minutes: number; start: string; end: string; groups: TimeGroup[]; entries: TimeEntry[];
  totals: { active_seconds: number; elapsed_seconds: number; billable_minutes: number; ai_seconds: number; ai_runs: number };
}
export interface TimePing { session_id: string; tender_id: string; page: string; active_seconds: number; draft_edits: number; end: boolean }
const tq = (o: Record<string, string>) => new URLSearchParams(Object.entries(o).filter(([, v]) => v)).toString();

export interface DriveStatus { configured: boolean; connected: boolean; account: string; connected_at: string | null; read_only: boolean; can_write?: boolean; job_folders?: string[]; standard_folders: string[] }
export interface DriveFile { id: string; name: string; path: string; mime: string; is_folder: boolean; modified: string; size: number | null; link: string; revision: string | null; latest: boolean | null; superseded_by: string | null; in_archive: boolean; ambiguous?: boolean; read: DriveRead | null }
export interface DriveRead { status: "ok" | "partial" | "needs_ocr" | "unsupported" | "failed"; read_at: string; pages: number; chars: number; stale: boolean; warnings: string[] }
export interface DriveReadResult { file_id: string; name: string; status: DriveRead["status"]; pages: number; warnings: string[] }
export interface DriveText extends DriveReadResult { path: string; revision: string | null; chars: number; pages_text: { n: number; text: string }[] }
export interface DriveListing {
  folder: { id: string; name: string; url: string }; files: DriveFile[]; truncated: boolean;
  structure: { number: string; label: string; found: boolean; actual: string | null; exact: boolean }[];
  counts: { files: number; latest_revisions: number; superseded: number; ambiguous_groups: number; loose_in_root: number };
}

export interface AiProviderInfo { id: string; label: string; available: boolean; default_model: string; key_hint: string }
export interface AiStatus { configured: boolean; enabled: boolean; provider: string; model: string; key_source: "own" | "platform" | null; key_last4: string; providers: AiProviderInfo[]; can_change: boolean; acknowledged_at: string | null; max_files: number; max_pictures: number }
export interface AiEvidence { file_id: string; file: string; page: number; quote: string; verified: boolean }
export interface AiProposal {
  id: string; batch: string; kind: "document" | "rfi" | "assumption" | "exclusion" | "inclusion" | "risk" | "scope"; group?: string; owner?: string; treatment?: string; title: string; detail: string; impact: string; rag: "RED" | "AMBER";
  basis: "quoted" | "gap"; evidence: AiEvidence[]; status: "verified" | "gap" | "unverified" | "duplicate"; problems: string[];
  decision: { decision: "accepted" | "rejected"; reason?: string; edit_key?: string } | null; created_at: string;
}
export interface DriveTextSummary { file_id: string; name: string; path: string; revision: string | null; status: string; pages: number; chars: number }

export interface IntakePart { file_id: string; name: string; page_from: number; page_to: number }
export interface IntakePlan { batches: { index: number; chars: number; parts: IntakePart[] }[]; skipped: { name: string; reason: string }[]; total_chars: number; files: number; max_batches: number }

export interface TakeoffComponent { label: string; value: number; unit: string; doc: string; file: string; sheet: string; page: number; source: string; quote: string; found: boolean | null }
export interface TakeoffLine {
  id: string; run: string; description: string; section: string; unit: string; operation: string; method: "READ" | "COUNTED" | "SCALED" | "CALCULATED"; confidence: "high" | "medium" | "low"; notes: string;
  quantity: number; quantity_claimed: number | null; components: TakeoffComponent[]; status: "verified" | "check" | "unverified"; problems: string[];
  decision: { decision: "accepted" | "rejected"; reason?: string } | null; created_at: string;
}
export interface TakeoffQs { description: string; unit: string; quantity: number; basis: string; source: string; notes: string; section_hint: string }

export interface TakeoffSource { index: number; label: string; value: number; unit: string; source: string; file_id: string; file: string; sheet: string; page: number; quote: string; how: "quote" | "number" | "none"; rects: { x0: number; y0: number; x1: number; y1: number }[]; viewable: boolean; pages?: number }
export interface SheetInfo { page: number; code: string; title: string }

export async function fetchBlobUrl(path: string): Promise<string> {
  const t = tokenStore.get();
  const res = await fetch(`${BASE}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (!res.ok) {
    let msg = `The server returned an error (${res.status}).`;
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return URL.createObjectURL(await res.blob());
}

export interface ProgrammeDoc {
  id: string; name: string; source: string; filename: string | null; start: string; finish: string; status_date: string | null; working_days: boolean[];
  non_working_dates: string[]; hours_per_day: number; task_count: number; needs_schedule?: boolean; revision?: number; updated_at: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tasks: any[];
}

export interface ProgrammeAiProposal {
  id: string; kind: "link" | "remove"; pred_uid: number; succ_uid: number; pred_name: string; succ_name: string; type: string; lag_days: number; reason: string;
  basis: "construction_logic" | "tender_document" | "inference"; confidence: "high" | "medium" | "low"; register_ref: string; pair?: string; status: "ok" | "exists" | "invalid"; problems: string[];
  decision: { decision: "accepted" | "rejected"; reason?: string } | null; created_at: string;
}
export interface ProgrammeAiResult { proposals: ProgrammeAiProposal[]; questions: { question: string; why: string }[]; coverage_notes: string }

export const api = {
  programmeAiPropose: (id: string, pid: string) => request<ProgrammeAiResult>(`/api/tenders/${id}/programmes/${pid}/ai/propose`, { method: "POST" }, LONG),
  programmeAiProposals: (id: string, pid: string) => request<ProgrammeAiResult>(`/api/tenders/${id}/programmes/${pid}/ai/proposals`),
  programmeAiDecision: (id: string, pid: string, accept: string[], reject: { id: string; reason: string }[]) =>
    request<{ accepted: ProgrammeAiProposal[]; rejected: number }>(`/api/tenders/${id}/programmes/${pid}/ai/decision`, { method: "POST", body: JSON.stringify({ accept, reject }) }),
  programmes: (id: string) => request<{ programmes: Omit<ProgrammeDoc, "tasks">[] }>(`/api/tenders/${id}/programmes`),
  programme: (id: string, pid: string) => request<ProgrammeDoc>(`/api/tenders/${id}/programmes/${pid}`),
  programmeUpload: (id: string, file: File) => request<ProgrammeDoc>(`/api/tenders/${id}/programmes/upload`, { method: "POST", body: form({ file }) }, LONG),
  programmeBlank: (id: string, name: string, start: string) => request<ProgrammeDoc>(`/api/tenders/${id}/programmes/blank`, { method: "POST", body: JSON.stringify({ name, start_date: start }) }),
  programmeFromEstimate: (id: string, revision: number, name: string, start: string) =>
    request<ProgrammeDoc>(`/api/tenders/${id}/programmes/from-estimate`, { method: "POST", body: JSON.stringify({ revision, name: name || undefined, start_date: start }) }),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  programmeSave: (id: string, pid: string, body: Record<string, any>) => request<ProgrammeDoc>(`/api/tenders/${id}/programmes/${pid}`, { method: "PUT", body: JSON.stringify(body) }),
  programmeDelete: (id: string, pid: string) => request<{ ok: boolean }>(`/api/tenders/${id}/programmes/${pid}`, { method: "DELETE" }),
  programmeExportXml: (id: string, pid: string) => download(`/api/tenders/${id}/programmes/${pid}/export/xml`),
  takeoffSources: (lid: string) => request<{ line: string; description: string; sources: TakeoffSource[] }>(`/api/takeoff/lines/${lid}/sources`),
  takeoffSheets: (tid: string, fid: string) => request<{ file: string; pages: SheetInfo[]; scale: Record<string, string> }>(`/api/takeoff/tenders/${tid}/files/${encodeURIComponent(fid)}/sheets`, {}, 180_000),
  pageImageUrl: (tid: string, fid: string, page: number) => fetchBlobUrl(`/api/takeoff/tenders/${tid}/files/${encodeURIComponent(fid)}/pages/${page}/image`),
  takeoffRun: (id: string, fileIds: string[], pictures: { file_id: string; page: number }[]) =>
    request<{ run: string; lines: TakeoffLine[]; not_measurable: { what: string; why: string }[]; files_sent: string[]; pictures: number }>(`/api/takeoff/tenders/${id}/run`, { method: "POST", body: JSON.stringify({ file_ids: fileIds, pictures }) }, LONG),
  takeoffLines: (id: string) => request<{ lines: TakeoffLine[] }>(`/api/takeoff/tenders/${id}/lines`),
  takeoffAccept: (lid: string, commit: boolean) => request<{ decision: "accepted" | "pending"; qs: TakeoffQs }>(`/api/takeoff/lines/${lid}/decision`, { method: "POST", body: JSON.stringify({ decision: "accepted", commit }) }),
  takeoffReject: (lid: string, reason: string) => request<{ decision: "rejected" }>(`/api/takeoff/lines/${lid}/decision`, { method: "POST", body: JSON.stringify({ decision: "rejected", reason }) }),
  aiIntakePlan: (id: string) => request<IntakePlan>(`/api/ai/tenders/${id}/intake/plan`),
  aiDraftParts: (id: string, parts: IntakePart[], run: string, mode: "register" | "scope" = "register") => request<{ batch: string; coverage_notes: string; proposals: AiProposal[]; files_sent: string[] }>(`/api/ai/tenders/${id}/draft`, { method: "POST", body: JSON.stringify({ parts, run, mode }) }, LONG),
  driveTexts: (id: string) => request<{ texts: DriveTextSummary[] }>(`/api/drive/tenders/${id}/texts`),
  aiStatus: () => request<AiStatus>("/api/ai/status"),
  aiSettings: (b: { provider?: string; model?: string; api_key?: string; clear_key?: boolean; enabled?: boolean; acknowledged?: boolean }) => request<AiStatus>("/api/ai/settings", { method: "PUT", body: JSON.stringify(b) }),
  aiTest: () => request<{ ok: boolean; model: string }>("/api/ai/test", { method: "POST" }),
  aiDraft: (id: string, fileIds: string[], mode: "register" | "scope" = "register") => request<{ batch: string; coverage_notes: string; proposals: AiProposal[]; files_sent: string[] }>(`/api/ai/tenders/${id}/draft`, { method: "POST", body: JSON.stringify({ file_ids: fileIds, mode }) }, LONG),
  aiProposals: (id: string) => request<{ proposals: AiProposal[] }>(`/api/ai/tenders/${id}/proposals`),
  aiAccept: (pid: string) => request<{ decision: "accepted"; edit: { target: string; op: "add"; key: string; value: Record<string, unknown> } }>(`/api/ai/proposals/${pid}/decision`, { method: "POST", body: JSON.stringify({ decision: "accepted" }) }),
  aiReject: (pid: string, reason: string) => request<{ decision: "rejected" }>(`/api/ai/proposals/${pid}/decision`, { method: "POST", body: JSON.stringify({ decision: "rejected", reason }) }),
  driveStatus: () => request<DriveStatus>("/api/drive/status"),
  driveConnect: (tender: string, write = false) => request<{ url: string }>(`/api/drive/connect?tender=${encodeURIComponent(tender)}${write ? "&write=1" : ""}`),
  driveFolderPlan: (id: string) => request<{ folder: { id: string; name: string }; plan: { number: string; name: string; action: "create" | "exists" | "number_taken"; actual: string | null }[]; can_write: boolean }>(`/api/drive/tenders/${id}/folder-plan`),
  driveSetupFolders: (id: string, where: "linked" | "new") => request<{ created: string[]; folder: { id: string; name: string; url: string } }>(`/api/drive/tenders/${id}/folders`, { method: "POST", body: JSON.stringify({ where }) }),
  driveDisconnect: () => request<{ ok: boolean }>("/api/drive/connection", { method: "DELETE" }),
  driveFolders: (parent: string) => request<{ parent: string; folders: { id: string; name: string }[] }>(`/api/drive/folders?parent=${encodeURIComponent(parent)}`),
  driveTender: (id: string) => request<{ folder: { id: string; name: string; url: string; linked_at: string } | null }>(`/api/drive/tenders/${id}`),
  driveLink: (id: string, folderId: string) => request<{ folder: { id: string; name: string; url: string } }>(`/api/drive/tenders/${id}`, { method: "PUT", body: JSON.stringify({ folder_id: folderId }) }),
  driveUnlink: (id: string) => request<{ ok: boolean }>(`/api/drive/tenders/${id}`, { method: "DELETE" }),
  driveRead: (id: string, fileIds: string[]) => request<{ results: DriveReadResult[] }>(`/api/drive/tenders/${id}/read`, { method: "POST", body: JSON.stringify({ file_ids: fileIds }) }, LONG),
  driveText: (id: string, fileId: string) => request<DriveText>(`/api/drive/tenders/${id}/texts/${fileId}`),
  driveFiles: (id: string) => request<DriveListing>(`/api/drive/tenders/${id}/files`),
  downloadOutput: (id: string, n: number, kind: "report.pdf" | "schedule.pdf" | "pricing.xlsx" | "verification-index.pdf" | "evidence-notes.pdf" | "programme.xlsx") => download(`/api/tenders/${id}/revisions/${n}/outputs/${kind}`),
  authConfig: () => request<{ registration_open: boolean; first_account: boolean }>("/api/auth/config"),
  login: (email: string, password: string) => request<{ token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (b: { email: string; password: string; name: string; company: string }) => request<{ token: string; user: User }>("/api/auth/register", { method: "POST", body: JSON.stringify(b) }),
  me: () => request<User>("/api/auth/me"),
  tenders: () => request<TenderList>("/api/tenders"),
  timePing: (b: TimePing) => {
    const t = tokenStore.get();      // keepalive lets the last ping leave while the tab is closing; a failed ping is simply reported back to the caller
    return fetch(`${BASE}/api/time/ping`, { method: "POST", keepalive: true, headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) }, body: JSON.stringify(b) }).then((r) => r.ok);
  },
  timesheet: (start: string, end: string, tenderId: string) => request<Timesheet>(`/api/time/timesheet?${tq({ start, end, tender_id: tenderId })}`),
  timesheetCsv: (start: string, end: string, tenderId: string, detail: boolean) => download(`/api/time/timesheet.csv?${tq({ start, end, tender_id: tenderId, detail: detail ? "true" : "" })}`),
  timeSettings: () => request<{ round_minutes: number; choices: number[]; can_change: boolean }>("/api/time/settings"),
  timeSetRound: (m: number) => request<{ round_minutes: number }>("/api/time/settings", { method: "PUT", body: JSON.stringify({ round_minutes: m }) }),
  timeAddEntry: (b: { date: string; minutes: number; note: string; tender_id: string }) => request<{ id: string }>("/api/time/entries", { method: "POST", body: JSON.stringify(b) }),
  timeEditEntry: (id: string, b: { date: string; minutes: number; note: string; tender_id: string }) => request<{ ok: boolean }>(`/api/time/entries/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  timeDeleteEntry: (id: string) => request<{ ok: boolean }>(`/api/time/entries/${id}`, { method: "DELETE" }),
  timeSessionNote: (id: string, note: string) => request<{ ok: boolean }>(`/api/time/sessions/${id}`, { method: "PUT", body: JSON.stringify({ note }) }),
  timeSessionDelete: (id: string) => request<{ ok: boolean }>(`/api/time/sessions/${id}`, { method: "DELETE" }),
  createTender: (file: File, client: string) => request<Tender>("/api/tenders", { method: "POST", body: form({ file, client }) }),
  createBlankTender: (name: string, intake: Record<string, string>, templateId: string | null) =>
    request<Tender>("/api/tenders/blank", { method: "POST", body: JSON.stringify({ name, intake, template_tender_id: templateId }) }),
  weatherCatalog: () => request<WeatherCatalog>("/api/weather/catalog"),
  tender: (id: string) => request<TenderDetail>(`/api/tenders/${id}`),
  setStage: (id: string, stage: Stage) => request<Tender>(`/api/tenders/${id}`, { method: "PATCH", body: JSON.stringify({ stage }) }),
  setClient: (id: string, client: string) => request<Tender>(`/api/tenders/${id}`, { method: "PATCH", body: JSON.stringify({ client }) }),
  deleteTender: (id: string) => request<{ deleted: boolean }>(`/api/tenders/${id}`, { method: "DELETE" }),
  addRevision: (id: string, file: File, confirm: boolean) => request<RevisionInfo>(`/api/tenders/${id}/revisions`, { method: "POST", body: form({ file, confirm_different_project: confirm }) }),
  // Revisions saved before rows had permanent ids carry no `uid`; their id back then was the display id, so use that.
  revision: (id: string, n: number) => request<{ tender: Tender; revision: RevisionInfo; estimate: Estimate }>(`/api/tenders/${id}/revisions/${n}`).then((r) => {
    r.estimate.buildup = r.estimate.buildup.map((b) => (b.uid ? b : { ...b, uid: b.row_id }));
    return r;
  }),
  preview: (id: string, n: number, edits: Edit[]) => request<{ estimate: Estimate; changes: Change[]; base: { all_in: number; siteworks_tender: number } }>(`/api/tenders/${id}/revisions/${n}/preview`, { method: "POST", body: JSON.stringify({ edits }) }),
  saveEdits: (id: string, n: number, edits: Edit[], label: string, note: string) => request<RevisionInfo>(`/api/tenders/${id}/revisions/${n}/save`, { method: "POST", body: JSON.stringify({ edits, label, note }) }),
  compare: (id: string, a: number, b: number) => request<{ a: RevisionInfo; b: RevisionInfo; diff: Diff }>(`/api/tenders/${id}/compare?a=${a}&b=${b}`),
};
