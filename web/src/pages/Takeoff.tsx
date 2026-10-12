import { useCallback, useEffect, useState } from "react";
import { api, type AiStatus, type DriveTextSummary, type SheetInfo, type TakeoffLine, type TakeoffQs } from "../lib/api";
import type { Estimate } from "../lib/types";
import { Chip, Empty, PageHeader, Panel } from "../components/ui";
import { AddQsDialog } from "../components/AddDialogs";
import { SourceViewer } from "../components/SourceViewer";
import { fmtNum } from "../lib/format";
import { newUid, useEdit } from "../lib/edit";

const STATUS: Record<TakeoffLine["status"], { tone: "green" | "amber" | "red"; text: string }> = {
  verified: { tone: "green", text: "Numbers found in the documents" },
  check: { tone: "amber", text: "Scaled or counted: check on the drawing" },
  unverified: { tone: "red", text: "Can't accept: a number isn't where it says" },
};
const METHOD: Record<TakeoffLine["method"], string> = { READ: "Read from the documents", COUNTED: "Counted", SCALED: "Scaled off the drawing", CALCULATED: "Calculated" };
// Which estimate section a takeoff section most likely belongs in (the estimator can change it in the dialog).
const SECTION_HINT: Record<string, RegExp> = {
  earthworks: /earth/i, pavements: /pavement|concrete/i, retaining: /retain/i, kerbs_external: /kerb|external/i, drainage: /drain|storm/i, parking: /pavement|marking/i, esc: /erosion|sediment/i,
};

function Line({ l, note, onAccept, onReject, onView }: { l: TakeoffLine; note?: string; onAccept: (l: TakeoffLine) => void; onReject: (l: TakeoffLine, reason: string) => void; onView: (l: TakeoffLine, i: number) => void }) {
  const [open, setOpen] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const can = l.status !== "unverified";
  return (
    <div className="border bg-background p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={STATUS[l.status].tone}>{STATUS[l.status].text}</Chip><Chip tone="neutral">{METHOD[l.method]}</Chip><Chip tone="neutral">{l.confidence} confidence</Chip>
        <Chip tone="neutral" title="Nothing the AI proposes is verified until you approve it">AI proposal</Chip>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold normal-case">{l.description}</h3>
        <div className="num text-base font-semibold">{fmtNum(l.quantity)} {l.unit}</div>
      </div>
      {l.quantity_claimed !== null && Math.abs(l.quantity_claimed - l.quantity) > 0.005 * Math.max(1, Math.abs(l.quantity)) && (
        <p className="mt-1 text-xs text-red-fg">The AI stated {fmtNum(l.quantity_claimed)}; the platform's arithmetic gives {fmtNum(l.quantity)}.</p>
      )}
      {l.notes && <p className="mt-1 whitespace-pre-line text-sm text-muted-foreground">{l.notes}</p>}
      <button className="mt-2 text-sm underline underline-offset-4" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} where the numbers come from ({l.components.length})</button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {l.components.map((c, i) => (
            <li key={i} className="border-l-2 pl-3 text-sm" style={{ borderColor: c.found === false ? "hsl(var(--red-line))" : c.found ? "hsl(var(--green-line))" : "hsl(var(--amber-line, var(--border)))" }}>
              <div><span className="num">{fmtNum(c.value)} {c.unit}</span> · {c.label}</div>
              <div className="text-xs text-muted-foreground">{c.file || c.doc} · {c.sheet} · page {c.page} · {c.source.replace("_", " ")}{c.found === true ? " · found on the page" : c.found === false ? " · NOT found on the page" : ""}</div>
              {c.quote && <div className="text-sm">“{c.quote}”</div>}
              {c.file && <button className="mt-1 text-sm underline underline-offset-4" onClick={() => onView(l, i)}>View source on the drawing</button>}
            </li>
          ))}
          <li className="text-xs text-muted-foreground">Operation: {l.operation}. The platform does this arithmetic from the numbers above.</li>
        </ul>
      )}
      {l.problems.length > 0 && <ul className="mt-2 list-inside list-disc text-sm text-red-fg">{l.problems.map((x) => <li key={x}>{x}</li>)}</ul>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {can && <button className="btn btn-solid !py-1.5" onClick={() => onAccept(l)}>Add to my QS draft</button>}
        {note && <span role="alert" className="basis-full border border-red-line bg-red-bg px-3 py-2 text-sm text-red-fg">{note}</span>}
        {!rejecting && <button className="btn btn-ghost !py-1.5" onClick={() => setRejecting(true)}>Reject</button>}
        {rejecting && (
          <>
            <input aria-label="Reason for rejecting" className="h-9 min-w-[16rem] flex-1 border bg-background px-3 text-sm focus:border-primary" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why (a few words)" autoFocus />
            <button className="btn btn-solid !py-1.5" onClick={() => reason.trim().length >= 3 && onReject(l, reason.trim())}>Reject</button>
            <button className="btn btn-ghost !py-1.5" onClick={() => setRejecting(false)}>Cancel</button>
          </>
        )}
      </div>
    </div>
  );
}

export function Takeoff({ est, tenderId, goQs }: { est: Estimate; tenderId: string; goQs: () => void }) {
  const { editing, add, set, canEdit, editHint, startEdit } = useEdit();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [texts, setTexts] = useState<DriveTextSummary[]>([]);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [pics, setPics] = useState<Record<string, string>>({});
  const [lines, setLines] = useState<TakeoffLine[]>([]);
  const [gaps, setGaps] = useState<{ what: string; why: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState<{ id: string; qs: TakeoffQs } | null>(null);
  const [note, setNote] = useState<{ id: string; text: string } | null>(null);
  const [viewing, setViewing] = useState<{ l: TakeoffLine; i: number } | null>(null);
  const [sheets, setSheets] = useState<Record<string, SheetInfo[] | "loading">>({});

  const load = useCallback(async () => {
    try {
      setStatus(await api.aiStatus());
      setTexts((await api.driveTexts(tenderId)).texts.filter((t) => t.status === "ok" || t.status === "partial"));
      setLines((await api.takeoffLines(tenderId)).lines);
    } catch (e) { setErr((e as Error).message); }
  }, [tenderId]);
  useEffect(() => { load(); }, [load]);

  const maxPics = status?.max_pictures ?? 20;
  const picked = (fid: string) => new Set((pics[fid] ?? "").split(/[ ,]+/).map(Number).filter((n) => Number.isInteger(n) && n > 0));
  const togglePage = (fid: string, page: number) => { const n = picked(fid); if (n.has(page)) n.delete(page); else n.add(page); setPics({ ...pics, [fid]: [...n].sort((a, b) => a - b).join(", ") }); };
  const loadSheets = (fid: string) => {
    if (sheets[fid]) return setSheets({ ...sheets, [fid]: undefined as never });
    setSheets({ ...sheets, [fid]: "loading" });
    api.takeoffSheets(tenderId, fid).then((r) => setSheets((x) => ({ ...x, [fid]: r.pages }))).catch((e) => { setErr((e as Error).message); setSheets((x) => ({ ...x, [fid]: undefined as never })); });
  };
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else if (n.size < 8) n.add(id); return n; });
  const chars = texts.filter((t) => sel.has(t.file_id)).reduce((a, t) => a + t.chars, 0);
  const pictures = [...sel].flatMap((fid) => (pics[fid] ?? "").split(/[ ,]+/).map((x) => Number(x)).filter((n) => Number.isInteger(n) && n > 0).map((page) => ({ file_id: fid, page })));

  const run = async () => {
    setErr(""); setMsg(""); setBusy(true);
    try { const r = await api.takeoffRun(tenderId, [...sel], pictures); setGaps(r.not_measurable); setLines((await api.takeoffLines(tenderId)).lines); setMsg(`${r.lines.length} ${r.lines.length === 1 ? "line" : "lines"} proposed from ${r.files_sent.length} ${r.files_sent.length === 1 ? "document" : "documents"}${r.pictures ? ` and ${r.pictures} page ${r.pictures === 1 ? "picture" : "pictures"}` : ""}.`); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const accept = async (l: TakeoffLine) => {
    setErr(""); setMsg(""); setNote(null);
    if (!editing) {
      // Adding to the draft needs edit mode: switch it on from here, unless this revision can't be edited at all (then say why, next to the button)
      if (!canEdit) return setNote({ id: l.id, text: editHint || "This revision can't be edited, so nothing can be added to a draft. Open the latest revision and try again." });
      startEdit();
    }
    try { const r = await api.takeoffAccept(l.id, false); setAdding({ id: l.id, qs: r.qs }); } catch (e) { setErr((e as Error).message); }
  };
  const reject = async (l: TakeoffLine, reason: string) => {
    setErr("");
    try { await api.takeoffReject(l.id, reason); setLines((await api.takeoffLines(tenderId)).lines); } catch (e) { setErr((e as Error).message); }
  };
  const hint = adding ? est.sections.map((s) => s.section).find((s) => SECTION_HINT[adding.qs.section_hint]?.test(s)) : undefined;
  const open = lines.filter((l) => !l.decision);
  const decided = lines.filter((l) => l.decision);
  const ready = status?.configured && status.enabled;

  return (
    <div>
      <PageHeader title="AI Takeoff" sub="The AI reads the drawings and reports you choose and proposes quantity lines. For each line it lists the numbers it used and where they came from; the platform checks that every number it says it read is on the page it cites, and does the arithmetic itself. Anything scaled or counted by eye is marked for you to check. Nothing enters the estimate until you add it to your draft and save a revision." />
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {msg && <div role="status" className="mb-4 border bg-muted/50 px-4 py-3 text-sm">{msg}</div>}
      {status && !ready && <Empty title="AI is not switched on for your company" body="The company owner sets up the AI provider and key on the AI Drafting page, then switches it on." />}
      {ready && (
        <>
          <Panel title="1. Choose drawings and reports (already read from Drive)" className="mb-4">
            {texts.length === 0 ? <p className="text-sm text-muted-foreground">No documents have been read yet. On Drive Documents, tick files and press Read.</p> : (
              <ul className="max-h-80 divide-y overflow-auto border">
                {texts.map((t) => (
                  <li key={t.file_id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                    <input type="checkbox" aria-label={`Select ${t.name}`} checked={sel.has(t.file_id)} onChange={() => toggle(t.file_id)} />
                    <span className="min-w-0 flex-1 truncate">{t.name}</span>
                    <span className="text-xs text-muted-foreground">{t.pages} p · {fmtNum(t.chars)} chars</span>
                    {sel.has(t.file_id) && t.name.toLowerCase().endsWith(".pdf") && (
                      <div className="flex items-center gap-2 text-xs">
                        <label className="flex items-center gap-2"><span className="label">Show pages as pictures</span>
                          <input aria-label={`Picture pages for ${t.name}`} className="h-8 w-32 border bg-background px-2 text-sm focus:border-primary" value={pics[t.file_id] ?? ""} onChange={(e) => setPics({ ...pics, [t.file_id]: e.target.value })} placeholder="e.g. 3, 4" /></label>
                        <button className="underline underline-offset-4" onClick={() => loadSheets(t.file_id)}>{sheets[t.file_id] ? "Hide sheets" : "Choose from sheet list"}</button>
                      </div>
                    )}
                    {sel.has(t.file_id) && sheets[t.file_id] && (
                      <div className="basis-full">
                        {sheets[t.file_id] === "loading" ? <p className="text-xs text-muted-foreground">Reading the drawing set…</p> : (
                          <ul className="mt-1 grid max-h-56 gap-x-4 overflow-auto border p-2 sm:grid-cols-2 lg:grid-cols-3">
                            {(sheets[t.file_id] as SheetInfo[]).map((sh) => (
                              <li key={sh.page}><label className="flex items-start gap-2 py-0.5 text-xs">
                                <input type="checkbox" className="mt-0.5" aria-label={`Page ${sh.page}`} checked={picked(t.file_id).has(sh.page)} onChange={() => togglePage(t.file_id, sh.page)} />
                                <span><span className="num">p{sh.page}</span> {sh.code && <strong>{sh.code}</strong>} {sh.title}</span></label></li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted-foreground">Text is always sent. Pictures are optional (up to {maxPics} pages per run) and help the AI measure from the drawing; pick the site plan, earthworks plan and foundation plan pages. Every page you tick is still read as text; for a large set, run the takeoff again for further pages and earlier lines are not repeated.</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button className="btn btn-solid" disabled={busy || sel.size === 0 || pictures.length > maxPics} onClick={run}>{busy ? "Working… this can take a few minutes" : `Take off (${sel.size} ${sel.size === 1 ? "document" : "documents"})`}</button>
              <span className="text-xs text-muted-foreground">{sel.size > 0 ? `About ${fmtNum(chars)} characters${pictures.length ? ` and ${pictures.length} page pictures` : ""} will be sent to ${status?.providers.find((p) => p.id === status.provider)?.label}.` : "Up to 8 documents per run."}</span>
            </div>
            {pictures.length > maxPics && <p className="mt-2 text-sm text-red-fg">That is {pictures.length} pictures; the limit for one run is {maxPics}. Run the takeoff again for the rest.</p>}
          </Panel>
          {gaps.length > 0 && (
            <Panel title="What the AI could not establish" className="mb-4">
              <ul className="list-inside list-disc text-sm">{gaps.map((g, i) => <li key={i}><strong>{g.what}</strong>: {g.why}</li>)}</ul>
            </Panel>
          )}
          <h2 className="mb-2 text-sm tracking-wider">2. Review the proposed lines ({open.length})</h2>
          {open.length === 0 ? <Empty title="Nothing waiting for review" body="Choose documents and press Take off. Proposed lines appear here for you to add to your draft or reject." /> : (
            <div className="space-y-3">{open.map((l) => <Line key={l.id} l={l} note={note?.id === l.id ? note.text : undefined} onAccept={accept} onReject={reject} onView={(ln, i) => setViewing({ l: ln, i })} />)}</div>
          )}
          {decided.length > 0 && (
            <details className="mt-6">
              <summary className="cursor-pointer text-sm">Decided ({decided.length})</summary>
              <ul className="mt-2 divide-y border text-sm">
                {decided.map((l) => <li key={l.id} className="flex flex-wrap items-center gap-2 px-3 py-2"><Chip tone={l.decision?.decision === "accepted" ? "green" : "neutral"}>{l.decision?.decision}</Chip><span>{l.description}: {fmtNum(l.quantity)} {l.unit}</span>{l.decision?.reason && <span className="text-muted-foreground">— {l.decision.reason}</span>}</li>)}
              </ul>
            </details>
          )}
        </>
      )}
      {viewing && <SourceViewer tenderId={tenderId} lineId={viewing.l.id} title={viewing.l.description} start={viewing.i} onClose={() => setViewing(null)} />}
      <AddQsDialog open={adding !== null} onClose={() => setAdding(null)} sections={est.sections} usedCodes={new Set(est.qs.map((x) => x.code))}
        initial={adding ? { section: hint, description: adding.qs.description, unit: adding.qs.unit, quantity: String(adding.qs.quantity), basis: adding.qs.basis, source: adding.qs.source } : undefined}
        onAdd={(code, payload, lump) => {
          add("qs", code, { ...payload, notes: adding?.qs.notes ?? "" });
          if (lump !== "") {
            const uid = newUid();
            add("row", uid, { qs_code: code, mode: "Lump Sum / Quote", resource_code: "", task: String(payload.description) });
            set({ target: "row", key: uid, field: "manual_qty", value: "1", original: "" });
            set({ target: "row", key: uid, field: "job_rate_override", value: lump, original: "" });
          }
          const id = adding?.id;
          setMsg(`${code} added to your draft (AMBER, not verified).${lump === "" ? " Price it on QS Takeoff." : ""}`);
          setAdding(null);
          if (id) api.takeoffAccept(id, true).then(() => api.takeoffLines(tenderId)).then((r) => setLines(r.lines)).catch((e) => setErr((e as Error).message));
        }} />
      {msg.includes("added to your draft") && <p className="mt-3 text-sm"><button className="underline underline-offset-4" onClick={goQs}>Go to QS Takeoff</button></p>}
    </div>
  );
}
