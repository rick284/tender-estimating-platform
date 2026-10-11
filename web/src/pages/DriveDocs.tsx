import { useCallback, useEffect, useState } from "react";
import { api, type DriveFile, type DriveListing, type DriveStatus } from "../lib/api";
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

export function DriveDocs({ tenderId }: { tenderId: string }) {
  const [status, setStatus] = useState<DriveStatus | null>(null);
  const [folder, setFolder] = useState<{ id: string; name: string; url: string } | null | undefined>(undefined);
  const [listing, setListing] = useState<DriveListing | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pick, setPick] = useState(false);
  const [onlyLatest, setOnlyLatest] = useState(false);

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

  const files = (listing?.files ?? []).filter((f) => !f.is_folder && (!onlyLatest || f.latest !== false));
  const note = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("drive");

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
            <Chip tone="green">Connected</Chip><span>{status.account || "Google account"} · read-only</span>
            <button className="underline underline-offset-4" onClick={disconnect}>Disconnect</button>
          </div>
          {folder === null && <Empty title="No folder linked to this tender" body="Choose the folder that holds this tender's documents (for example “329 Hobsonville Road”)." />}
          {folder === null && <div className="mt-4"><button className="btn btn-solid" onClick={() => setPick(true)}>Choose folder</button></div>}
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
                  {listing.truncated && <div className="border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">This folder is very large; only part of it was read.</div>}
                  <Panel title="Issued-pack folders (01–07)">
                    <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
                      {listing.structure.map((s) => (
                        <li key={s.number} className="flex items-center gap-2">
                          <Chip tone={s.exact ? "green" : s.found ? "amber" : "neutral"}>{s.exact ? "Found" : s.found ? "Renamed" : "Missing"}</Chip>
                          <span>{s.number} {s.label}{s.found && !s.exact && <span className="text-muted-foreground"> — called “{s.actual}”</span>}</span>
                        </li>
                      ))}
                    </ul>
                  </Panel>
                  <Panel title="Files" flush action={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyLatest} onChange={(e) => setOnlyLatest(e.target.checked)} /> Hide superseded</label>}>
                    {files.length === 0 ? <div className="p-4"><Empty title="No files" body="This folder has no files yet." /></div> : (
                      <div className="overflow-x-auto">
                        <table className="grid-table min-w-[48rem]">
                          <thead><tr><th>File</th><th>Folder</th><th>Revision</th><th>Status</th><th>Modified</th><th className="text-right">Size</th></tr></thead>
                          <tbody>
                            {files.map((f: DriveFile) => (
                              <tr key={f.id}>
                                <td>{f.link ? <a className="underline underline-offset-4" href={f.link} target="_blank" rel="noreferrer">{f.name}</a> : f.name}</td>
                                <td className="text-muted-foreground">{f.path || "(main folder)"}</td>
                                <td>{f.revision ?? "—"}</td>
                                <td>
                                  {f.superseded_by ? <Chip tone="neutral" title={`Superseded by ${f.superseded_by}`}>Superseded</Chip>
                                    : f.in_archive ? <Chip tone="neutral">Archive</Chip>
                                    : f.latest ? <Chip tone={f.ambiguous ? "amber" : "green"} title={f.ambiguous ? "Revision labels mix numbers and letters; check which is newest" : undefined}>{f.ambiguous ? "Check latest" : "Latest"}</Chip> : "—"}
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
      <FolderPicker open={pick} onClose={() => setPick(false)} onPick={link} />
    </div>
  );
}
