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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = tokenStore.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 90_000);
  try { res = await fetch(`${BASE}${path}`, { ...init, headers, signal: ctl.signal }); }
  catch (e) {
    throw new ApiError(0, e instanceof DOMException && e.name === "AbortError"
      ? "The server took too long to answer (over 90 seconds). It may be waking up; wait a minute and try again."
      : "Can't reach the server. Check your connection and try again.");
  } finally { clearTimeout(timer); }
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

export interface DriveStatus { configured: boolean; connected: boolean; account: string; connected_at: string | null; read_only: boolean; standard_folders: string[] }
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
export interface AiStatus { configured: boolean; enabled: boolean; provider: string; model: string; key_source: "own" | "platform" | null; key_last4: string; providers: AiProviderInfo[]; can_change: boolean; acknowledged_at: string | null; max_files: number }
export interface AiEvidence { file_id: string; file: string; page: number; quote: string; verified: boolean }
export interface AiProposal {
  id: string; batch: string; kind: "document" | "rfi" | "assumption" | "exclusion" | "inclusion" | "risk"; title: string; detail: string; impact: string; rag: "RED" | "AMBER";
  basis: "quoted" | "gap"; evidence: AiEvidence[]; status: "verified" | "gap" | "unverified" | "duplicate"; problems: string[];
  decision: { decision: "accepted" | "rejected"; reason?: string; edit_key?: string } | null; created_at: string;
}
export interface DriveTextSummary { file_id: string; name: string; path: string; revision: string | null; status: string; pages: number; chars: number }

export const api = {
  driveTexts: (id: string) => request<{ texts: DriveTextSummary[] }>(`/api/drive/tenders/${id}/texts`),
  aiStatus: () => request<AiStatus>("/api/ai/status"),
  aiSettings: (b: { provider?: string; model?: string; api_key?: string; clear_key?: boolean; enabled?: boolean; acknowledged?: boolean }) => request<AiStatus>("/api/ai/settings", { method: "PUT", body: JSON.stringify(b) }),
  aiTest: () => request<{ ok: boolean; model: string }>("/api/ai/test", { method: "POST" }),
  aiDraft: (id: string, fileIds: string[]) => request<{ batch: string; coverage_notes: string; proposals: AiProposal[]; files_sent: string[] }>(`/api/ai/tenders/${id}/draft`, { method: "POST", body: JSON.stringify({ file_ids: fileIds }) }),
  aiProposals: (id: string) => request<{ proposals: AiProposal[] }>(`/api/ai/tenders/${id}/proposals`),
  aiAccept: (pid: string) => request<{ decision: "accepted"; edit: { target: string; op: "add"; key: string; value: Record<string, unknown> } }>(`/api/ai/proposals/${pid}/decision`, { method: "POST", body: JSON.stringify({ decision: "accepted" }) }),
  aiReject: (pid: string, reason: string) => request<{ decision: "rejected" }>(`/api/ai/proposals/${pid}/decision`, { method: "POST", body: JSON.stringify({ decision: "rejected", reason }) }),
  driveStatus: () => request<DriveStatus>("/api/drive/status"),
  driveConnect: (tender: string) => request<{ url: string }>(`/api/drive/connect?tender=${encodeURIComponent(tender)}`),
  driveDisconnect: () => request<{ ok: boolean }>("/api/drive/connection", { method: "DELETE" }),
  driveFolders: (parent: string) => request<{ parent: string; folders: { id: string; name: string }[] }>(`/api/drive/folders?parent=${encodeURIComponent(parent)}`),
  driveTender: (id: string) => request<{ folder: { id: string; name: string; url: string; linked_at: string } | null }>(`/api/drive/tenders/${id}`),
  driveLink: (id: string, folderId: string) => request<{ folder: { id: string; name: string; url: string } }>(`/api/drive/tenders/${id}`, { method: "PUT", body: JSON.stringify({ folder_id: folderId }) }),
  driveUnlink: (id: string) => request<{ ok: boolean }>(`/api/drive/tenders/${id}`, { method: "DELETE" }),
  driveRead: (id: string, fileIds: string[]) => request<{ results: DriveReadResult[] }>(`/api/drive/tenders/${id}/read`, { method: "POST", body: JSON.stringify({ file_ids: fileIds }) }),
  driveText: (id: string, fileId: string) => request<DriveText>(`/api/drive/tenders/${id}/texts/${fileId}`),
  driveFiles: (id: string) => request<DriveListing>(`/api/drive/tenders/${id}/files`),
  downloadOutput: (id: string, n: number, kind: "report.pdf" | "schedule.pdf" | "pricing.xlsx" | "verification-index.pdf" | "evidence-notes.pdf" | "programme.xlsx") => download(`/api/tenders/${id}/revisions/${n}/outputs/${kind}`),
  authConfig: () => request<{ registration_open: boolean; first_account: boolean }>("/api/auth/config"),
  login: (email: string, password: string) => request<{ token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (b: { email: string; password: string; name: string; company: string }) => request<{ token: string; user: User }>("/api/auth/register", { method: "POST", body: JSON.stringify(b) }),
  me: () => request<User>("/api/auth/me"),
  tenders: () => request<TenderList>("/api/tenders"),
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
