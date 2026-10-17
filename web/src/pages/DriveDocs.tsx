import { useCallback, useEffect, useState } from "react";
import { api, type DriveFile, type DriveListing, type DriveRead, type DriveStatus, type DriveText } from "../lib/api";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { Modal } from "../components/Modal";
import { fmtDate, fmtNum } from "../lib/format";

const fmtSize = (n: number | null) => (n == null ? "—" : n > 1e6 ? `${fmtNum(Math.round(n / 1e5) / 10)} MB` : `${fmtNum(Math.max(1, Math.round(n / 1e3)))} KB`);

function FolderPicker({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (id: string) => void }) {
  const [trail, setTrail] = useState<{ id: string; name: string }[]>([{ id: "root", name: "My Drive" }]);
  const [folders, setFolders] = useState<{ id: string; name: string }[] | null>(null);
  const [err, setErr] = useState("");
  const cur = trail[trail.length - 1];
  useEffect(() => {
    if (!open) return;
    setFolders(null); setErr("");
    api.driveFolders(cur.id).then((r) => setFolders(r.folders)).catch((e) => setErr(e.message));
  }, [open, cur.id]);
  return (
    <Modal open={open} onClose={onClose} title="Choose the tender's Drive folder">
      <div className="space-y-3">
        <div className="text-sm">{trail.map((t, i) => (
          <span key={t.id}>{i > 0 && " / "}<button className="underline underline-offset-4" onClick={() => setTrail(trail.slice(0, i + 1))}>{t.name}</button></span>
        ))}</div>
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        {!folders && !err && <p className="text-sm text-muted-foreground" aria-live="polite">Loading folders…</p>}
        {folders && folders.length === 0 && <p className="text-sm text-muted-foreground">No folders inside here.</p>}
        <ul className="max-h-72 divide-y overflow-auto border">
          {folders?.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <button className="min-w-0 truncate text-left font-medium hover:underline" onClick={() => setTrail([...trail, f])}>{f.name}</button>
              <button className="btn btn-ghost !py-1" onClick={() => onPick(f.id)}>Use this folder</button>
            </li>
          ))}
        </ul>
        {cur.id !== "root" && <button className="btn btn-solid" onClick={() => onPick(cur.id)}>Use “{cur.name}”</button>}
      </div>
    </Modal>
  );
}

const READ_LABEL: Record<DriveRead["status"], { tone: "green" | "amber" | "red" | "neutral"; text: string; tip: string }> = {
  ok: { tone: "green", text: "Read", tip: "Text extracted" },
  partial: { tone: "amber", text: "Part read", tip: "Some pages have no text (drawings or scans)" },
  needs_ocr: { tone: "amber", text: "Needs OCR", tip: "Scanned or drawing-only: no text could be extracted" },
  unsupported: { tone: "neutral", text: "Not supported", tip: "This file type is not read yet" },
  failed: { tone: "red", text: "Failed", tip: "Could not be read" },
};

function TextDialog({ tenderId, file, onClose }: { tenderId: string; file: DriveFile | null; onClose: () => void }) {
  const [t, setT] = useState<DriveText | null>(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    setT(null); setErr(""); setQ("");
    if (file) api.driveText(tenderId, file.id).then(setT).catch((e) => setErr(e.message));
  }, [tenderId, file]);
  const pages = (t?.pages_text ?? []).filter((p) => !q.trim() || p.text.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <Modal open={!!file} onClose={onClose} title={file ? `Text of ${file.name}` : ""}>
      <div className="space-y-3">
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        {!t && !err && <p className="text-sm text-muted-foreground" aria-live="polite">Loading…</p>}
        {t && (
          <>
            <p className="text-sm text-muted-foreground">{t.pages} page(s), {fmtNum(t.chars)} characters. Each page keeps its number so quantities can cite it.</p>
            {t.warnings.map((w) => <div key={w} className="border border-amber-line bg-amber-bg px-3 py-2 text-sm text-amber-fg">{w}</div>)}
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search within this file" aria-label="Search within this file" className="h-9 w-full border bg-background px-3 text-sm focus:border-primary" />
            <div className="max-h-[50vh] space-y-3 overflow-auto">
              {pages.length === 0 && <p className="text-sm text-muted-foreground">No pages match.</p>}
              {pages.map((p) => (
                <div key={p.n} className="border">
                  <div className="label border-b bg-muted px-3 py-1">Page {p.n}</div>
                  <pre className="whitespace-pre-wrap px-3 py-2 font-mono text-xs leading-5">{p.text || "(no text on this page)"}</pre>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function JobFolders({ tenderId, status, onDone, setErr }: { tenderId: string; status: DriveStatus; onDone: () => void; setErr: (s: string) => void }) {
  const [plan, setPlan] = useState<Awaited<ReturnType<typeof api.driveFolderPlan>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  useEffect(() => { api.driveFolderPlan(tenderId).then(setPlan).catch(() => setPlan(null)); }, [tenderId, status.can_write]);
  if (!plan) return null;
  const missing = plan.plan.filter((p) => p.action === "create");
  const allow = async () => { try { window.location.href = (await api.driveConnect(tenderId, true)).url; } catch (e) { setErr((e as Error).message); } };
  const run = async (where: "linked" | "new") => {
    setErr(""); setDone(""); setBusy(true);
    try { const r = await api.driveSetupFolders(tenderId, where); setDone(`Created ${r.created.length} folder${r.created.length === 1 ? "" : "s"}.`); await onDone(); setPlan(await api.driveFolderPlan(tenderId)); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  return (
    <Panel title="Set up job folders">
      <p className="mb-3 text-sm">The platform can add the standard job folders (00 Project Admin to 07 Superseded and Archive) inside this folder. It only ever <strong>creates new, empty folders</strong>: nothing is renamed, moved, overwritten or deleted, and a number already used by a differently named folder is left alone.</p>
      <ul className="mb-3 grid gap-1.5 text-sm sm:grid-cols-2">
        {plan.plan.map((p) => (
          <li key={p.number} className="flex items-center gap-2">
            <Chip tone={p.action === "exists" ? "green" : p.action === "create" ? "neutral" : "amber"}>{p.action === "exists" ? "Already there" : p.action === "create" ? "Will be created" : "Number in use"}</Chip>
            <span>{p.name}{p.action === "number_taken" && <span className="text-muted-foreground"> — “{p.actual}” is already {p.number}</span>}</span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        {!plan.can_write && <button className="btn btn-solid" onClick={allow}>Allow Drive to add folders…</button>}
        {plan.can_write && missing.length > 0 && <button className="btn btn-solid" disabled={busy} onClick={() => run("linked")}>{busy ? "Creating…" : `Add ${missing.length} missing folder${missing.length === 1 ? "" : "s"}`}</button>}
        {plan.can_write && missing.length > 0 && <button className="btn btn-ghost" disabled={busy} onClick={() => run("new")}>Create a new job folder in My Drive instead</button>}
        {missing.length === 0 && <span className="text-sm text-muted-foreground">Nothing to add.</span>}
        {done && <span role="status" className="text-sm text-green-fg">{done}</span>}
      </div>
      {!plan.can_write && <p className="mt-2 text-xs text-muted-foreground">This asks Google for one extra, narrow permission (“add files and folders this app creates”). It cannot see, change or delete your other files. You can remove it any time at myaccount.google.com/permissions.</p>}
    </Panel>
  );
}

export function DriveDocs({ tenderId }: { tenderId: string }) {
  const [status, setStatus] = useState<DriveStatus | null>(null);
  const [folder, setFolder] = useState<{ id: string; name: string; url: string } | null | undefined>(undefined);
  const [listing, setListing] = useState<DriveListing | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pick, setPick] = useState(false);
  const [onlyLatest, setOnlyLatest] = useState(false);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [reading, setReading] = useState("");
  const [view, setView] = useState<DriveFile | null>(null);

  const load = useCallback(async () => {
    setErr("");
    try {
      const s = await api.driveStatus(); setStatus(s);
      if (!s.connected) { setFolder(null); return; }
      const t = await api.driveTender(tenderId); setFolder(t.folder);
      if (t.folder) { setBusy(true); setListing(await api.driveFiles(tenderId)); }
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  }, [tenderId]);
  useEffect(() => { load(); }, [load]);

  const connect = async () => {
    try { window.location.href = (await api.driveConnect(tenderId)).url; } catch (e) { setErr((e as Error).message); }
  };
  const link = async (id: string) => {
    setPick(false);
    try { const r = await api.driveLink(tenderId, id); setFolder(r.folder); setListing(null); await load(); } catch (e) { setErr((e as Error).message); }
  };
  const disconnect = async () => {
    if (!confirm("Disconnect Google Drive for your whole company? Tenders keep their records but lose their folder links.")) return;
    try { await api.driveDisconnect(); setListing(null); await load(); } catch (e) { setErr((e as Error).message); }
  };

  const readFiles = async (ids: string[]) => {
    if (!ids.length) return;
    setErr("");
    try {
      for (let i = 0; i < ids.length; i += 25) {
        setReading(`Reading files ${Math.min(i + 25, ids.length)} of ${ids.length}…`);
        await api.driveRead(tenderId, ids.slice(i, i + 25));
      }
      setSel(new Set()); setListing(await api.driveFiles(tenderId));
    } catch (e) { setErr((e as Error).message); }
    finally { setReading(""); }
  };
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const files = (listing?.files ?? []).filter((f) => !f.is_folder && (!onlyLatest || f.latest !== false));
  const note = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("drive");

  const unread = files.filter((f) => f.latest !== false && !f.in_archive && (!f.read || f.read.stale)).map((f) => f.id);
  return (
    <div>
      <PageHeader title="Drive Documents" sub="The tender's Google Drive folder, read-only. The platform can look at the files but never change, move or delete them." />
      {note && note !== "connected" && <div role="alert" className="mb-4 border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">Google Drive was not connected ({note}). Try again.</div>}
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {status && !status.configured && <Empty title="Drive is not switched on yet" body="The Google connection has not been set up on this server. Once the Google client ID and secret are added, a Connect button will appear here." />}
      {status?.configured && !status.connected && (
        <Panel title="Connect Google Drive">
          <p className="mb-3 text-sm text-muted-foreground">You'll be sent to Google to approve <strong>read-only</strong> access, then brought straight back here.</p>
          <button className="btn btn-solid" onClick={connect}>Connect Google Drive</button>
        </Panel>
      )}
      {status?.connected && (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
            <Chip tone="green">Connected</Chip><span>{status.account || "Google account"} · {status.can_write ? "can add new folders (cannot change or delete anything)" : "read-only"}</span>
            <button className="underline underline-offset-4" onClick={disconnect}>Disconnect</button>
          </div>
          {folder === null && <Empty title="No folder linked to this tender" body="Choose the folder that holds this tender's documents (the job folder, not the folder above it)." />}
          {folder === null && <div className="mt-4 flex flex-wrap gap-3"><button className="btn btn-solid" onClick={() => setPick(true)}>Choose folder</button>
            {status.can_write ? <button className="btn btn-ghost" onClick={async () => { try { await api.driveSetupFolders(tenderId, "new"); await load(); } catch (e) { setErr((e as Error).message); } }}>Create a new job folder in My Drive</button>
              : <button className="btn btn-ghost" onClick={async () => { try { window.location.href = (await api.driveConnect(tenderId, true)).url; } catch (e) { setErr((e as Error).message); } }}>Allow Drive to add folders…</button>}</div>}
          {folder && (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-medium">{folder.name}</span>
                {folder.url && <a className="underline underline-offset-4" href={folder.url} target="_blank" rel="noreferrer">Open in Drive</a>}
                <button className="underline underline-offset-4" onClick={() => setPick(true)}>Change folder</button>
                <button className="underline underline-offset-4" onClick={load} disabled={busy}>{busy ? "Reading…" : "Refresh"}</button>
              </div>
              {busy && !listing && <p className="text-sm text-muted-foreground" aria-live="polite">Reading the folder…</p>}
              {listing && (
                <>
                  <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
                    <Stat label="Files" value={fmtNum(listing.counts.files)} />
                    <Stat label="Latest revisions" value={fmtNum(listing.counts.latest_revisions)} />
                    <Stat label="Superseded" value={fmtNum(listing.counts.superseded)} sub="a newer revision sits beside it" />
                    <Stat label="Loose in main folder" value={fmtNum(listing.counts.loose_in_root)} sub="not filed in 01–07" />
                  </div>
                  {listing.truncated && <div className="border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">Some deeper subfolders were not read (the folder is very large or nested more than six levels).</div>}
                  <Panel title="Job folder structure">
                    <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
                      {listing.structure.map((s) => (
                        <li key={s.number} className="flex items-center gap-2">
                          <Chip tone={s.exact ? "green" : s.found ? "amber" : "neutral"}>{s.exact ? "Found" : s.found ? "Renamed" : "Missing"}</Chip>
                          <span>{s.number} {s.label}{s.found && !s.exact && <span className="text-muted-foreground"> — called “{s.actual}”</span>}</span>
                        </li>
                      ))}
                    </ul>
                  </Panel>
                  <JobFolders tenderId={tenderId} status={status} onDone={load} setErr={setErr} />
                  <Panel title="Files" flush action={
                    <div className="flex flex-wrap items-center gap-3 text-sm">
                      <label className="flex items-center gap-2"><input type="checkbox" checked={onlyLatest} onChange={(e) => setOnlyLatest(e.target.checked)} /> Hide superseded</label>
                      <button className="btn btn-ghost !py-1" disabled={!!reading || sel.size === 0} onClick={() => readFiles([...sel])}>Read selected ({sel.size})</button>
                      <button className="btn btn-solid !py-1" disabled={!!reading || unread.length === 0} onClick={() => readFiles(unread)} title="Latest files not yet read, or changed since they were read">Read all latest ({unread.length})</button>
                    </div>}>
                    {reading && <div className="border-b bg-muted px-4 py-2 text-sm" aria-live="polite">{reading}</div>}
                    {files.length === 0 ? <div className="p-4"><Empty title="No files" body="This folder has no files yet." /></div> : (
                      <div className="grid-scroll">
                        <table className="grid-table min-w-[56rem]">
                          <thead><tr><th className="w-8"></th><th>File</th><th>Folder</th><th>Revision</th><th>Status</th><th>Text</th><th>Modified</th><th className="text-right">Size</th></tr></thead>
                          <tbody>
                            {files.map((f: DriveFile) => (
                              <tr key={f.id}>
                                <td><input type="checkbox" aria-label={`Select ${f.name}`} checked={sel.has(f.id)} onChange={() => toggle(f.id)} /></td>
                                <td>{f.link ? <a className="underline underline-offset-4" href={f.link} target="_blank" rel="noreferrer">{f.name}</a> : f.name}</td>
                                <td className="text-muted-foreground">{f.path || "(main folder)"}</td>
                                <td>{f.revision ?? "—"}</td>
                                <td>
                                  {f.superseded_by ? <Chip tone="neutral" title={`Superseded by ${f.superseded_by}`}>Superseded</Chip>
                                    : f.in_archive ? <Chip tone="neutral">Archive</Chip>
                                    : f.latest ? <Chip tone={f.ambiguous ? "amber" : "green"} title={f.ambiguous ? "Revision labels mix numbers and letters; check which is newest" : undefined}>{f.ambiguous ? "Check latest" : "Latest"}</Chip> : "—"}
                                </td>
                                <td>
                                  {f.read ? (
                                    <button className="inline-flex items-center gap-1.5" onClick={() => setView(f)} title={`${READ_LABEL[f.read.status].tip}. Click to view the text.`}>
                                      <Chip tone={READ_LABEL[f.read.status].tone}>{READ_LABEL[f.read.status].text}</Chip>{f.read.stale && <Chip tone="amber" title="The file changed in Drive after it was read">Changed</Chip>}
                                    </button>
                                  ) : <span className="text-muted-foreground">—</span>}
                                </td>
                                <td>{fmtDate(f.modified)}</td>
                                <td className="text-right">{fmtSize(f.size)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Panel>
                </>
              )}
            </div>
          )}
        </>
      )}
      <TextDialog tenderId={tenderId} file={view} onClose={() => setView(null)} />
      <FolderPicker open={pick} onClose={() => setPick(false)} onPick={link} />
    </div>
  );
}
