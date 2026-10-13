import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { api, type AiStatus, type ProgrammeAiProposal, type ProgrammeAiResult } from "../lib/api";
import { Modal } from "../components/Modal";
import { Chip } from "../components/ui";
import { toast } from "../lib/toast";
import { newUid, useEdit } from "../lib/edit";

/* eslint-disable @typescript-eslint/no-explicit-any */
const TYPE_NAME: Record<string, string> = { FS: "finish to start", SS: "start to start", FF: "finish to finish", SF: "start to finish" };
const BASIS: Record<string, string> = { construction_logic: "Construction logic", tender_document: "Tender document", inference: "Inference" };
const CONF_TONE = { high: "green", medium: "amber", low: "red" } as const;
const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

/** What the new predecessor list of one task should be after the accepted proposals (same rule as the server's apply_to_predecessors). */
export function newPredecessors(current: any[], adds: ProgrammeAiProposal[], removes: ProgrammeAiProposal[], idOf: (uid: number) => number | undefined) {
  const gone = new Set(removes.map((r) => r.pred_uid));
  const out = current.filter((p) => !gone.has(p.uid)).map((p) => ({ ...p }));
  for (const a of adds) if (!out.some((p) => p.uid === a.pred_uid)) out.push({ uid: a.pred_uid, id: idOf(a.pred_uid), type: a.type, lag_days: a.lag_days });
  return out;
}

export function AiLogicDialog({ open, onClose, tenderId, programmeId, dirty, save, tasks, apply }: {
  open: boolean; onClose: () => void; tenderId: string; programmeId: string; dirty: boolean; save: () => Promise<boolean>; tasks: any[]; apply: (uid: number, preds: any[]) => void;
}) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [res, setRes] = useState<ProgrammeAiResult | null>(null);
  const [pick, setPick] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [rfis, setRfis] = useState<Record<number, boolean>>({});
  const [qNote, setQNote] = useState<{ i: number; text: string } | null>(null);
  const { editing, canEdit, editHint, startEdit, add } = useEdit();

  useEffect(() => {
    if (!open) return;
    setErr("");
    api.aiStatus().then(setStatus).catch((e) => setErr(msg(e)));
    api.programmeAiProposals(tenderId, programmeId).then((r) => {
      const pending = r.proposals.filter((p) => !p.decision);
      setRes({ ...r, proposals: pending });
      setPick(Object.fromEntries(pending.map((p) => [p.id, p.status === "ok" && p.confidence !== "low"])));
    }).catch(() => undefined);
  }, [open, tenderId, programmeId]);

  const propose = async () => {
    setBusy(true); setErr("");
    try {
      if (dirty && !(await save())) return;
      const r = await api.programmeAiPropose(tenderId, programmeId);
      setRes(r);
      setPick(Object.fromEntries(r.proposals.map((p) => [p.id, p.status === "ok" && p.confidence !== "low"])));
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  };

  const makeRfi = (i: number, q: { question: string; why: string }) => {
    setQNote(null);
    if (!editing) {
      if (!canEdit) return setQNote({ i, text: editHint || "This revision can't be edited, so nothing can be added to the register. Open the latest revision and try again." });
      startEdit();
    }
    add("register", newUid(), { kind: "rfi", title: q.question.replace(/\?$/, "").slice(0, 120), detail: `Raised from the AI programme logic review. ${q.question}`, action: q.why, rag: "AMBER", status: "OPEN" });
    setRfis((r) => ({ ...r, [i]: true }));
    toast.success("RFI added to your register draft. Save the revision to keep it.");
  };
  const togglePick = (p: ProgrammeAiProposal, on: boolean) =>
    setPick((cur) => { const n = { ...cur, [p.id]: on }; if (p.pair) (res?.proposals ?? []).forEach((o) => { if (o.pair === p.pair) n[o.id] = on; }); return n; });

  const chosen = (res?.proposals ?? []).filter((p) => pick[p.id] && p.status === "ok");
  const applyChosen = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api.programmeAiDecision(tenderId, programmeId, chosen.map((p) => p.id), []);
      const idOf = (uid: number) => tasks.find((t) => t.uid === uid)?.id;
      const bySucc = new Map<number, ProgrammeAiProposal[]>();
      r.accepted.forEach((p) => bySucc.set(p.succ_uid, [...(bySucc.get(p.succ_uid) ?? []), p]));
      bySucc.forEach((ps, uid) => {
        const t = tasks.find((x) => x.uid === uid);
        if (t) apply(uid, newPredecessors(t.predecessors || [], ps.filter((p) => p.kind === "link"), ps.filter((p) => p.kind === "remove"), idOf));
      });
      setRes((cur) => (cur ? { ...cur, proposals: cur.proposals.filter((p) => !r.accepted.some((a) => a.id === p.id)) } : cur));
      toast.success(`Applied ${r.accepted.length} change${r.accepted.length === 1 ? "" : "s"} to your programme. Press Save to keep them.`);
      onClose();
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  };
  const rejectChosen = async () => {
    setBusy(true); setErr("");
    try {
      await api.programmeAiDecision(tenderId, programmeId, [], chosen.map((p) => ({ id: p.id, reason })));
      setRes((cur) => (cur ? { ...cur, proposals: cur.proposals.filter((p) => !chosen.some((c) => c.id === p.id)) } : cur));
      setReason("");
    } catch (e) { setErr(msg(e)); } finally { setBusy(false); }
  };

  const notReady = status && (!status.configured || !status.enabled);
  const rows = (kind: "link" | "remove") => (res?.proposals ?? []).filter((p) => p.kind === kind);
  const Row = ({ p }: { p: ProgrammeAiProposal }) => (
    <li className={`flex gap-3 border-b px-3 py-3 last:border-b-0 ${p.status === "ok" ? "" : "bg-muted/50 text-muted-foreground"}`} data-testid="ai-proposal">
      <input type="checkbox" className="mt-1 h-4 w-4 accent-black" disabled={p.status !== "ok"} checked={!!pick[p.id] && p.status === "ok"} onChange={(e) => togglePick(p, e.target.checked)} aria-label={`Select ${p.pred_name} to ${p.succ_name}`} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium leading-snug">{p.pred_name || `Task ${p.pred_uid}`} <span aria-label="then" className="text-muted-foreground">→</span> {p.succ_name || `Task ${p.succ_uid}`}</div>
        {p.kind === "link" && <div className="mt-0.5 text-xs text-muted-foreground">{TYPE_NAME[p.type] ?? p.type}{p.lag_days ? `, ${p.lag_days > 0 ? "lag" : "lead"} ${Math.abs(p.lag_days)} day${Math.abs(p.lag_days) === 1 ? "" : "s"}` : ""}</div>}
        <p className="mt-1 text-sm leading-snug">{p.reason}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <Chip tone={CONF_TONE[p.confidence]}>{p.confidence} confidence</Chip><Chip tone="neutral">{BASIS[p.basis]}{p.register_ref ? ` ${p.register_ref}` : ""}</Chip>
          {p.pair && <Chip tone="neutral">{p.kind === "remove" ? "Replaced by a different link (selected together)" : "Replaces a removed link (selected together)"}</Chip>}
          {p.status === "exists" && <Chip tone="neutral">Already in the programme</Chip>}
          {p.status === "invalid" && <Chip tone="red">Can't be used</Chip>}
        </div>
        {p.problems.length > 0 && <p className="mt-1 text-xs text-red-fg">{p.problems.join(" ")}</p>}
      </div>
    </li>
  );

  return (
    <Modal open={open} onClose={onClose} title="AI programme logic" huge>
      <div data-testid="ai-logic-dialog">
        <p className="mb-3 max-w-3xl text-sm text-muted-foreground">The AI looks at your tasks (names, durations, resources) and the assumptions, exclusions and open RFIs recorded for this tender, and proposes which task depends on which. It never changes a duration or a date: those come from your estimate. You choose which proposals to apply; they go into your programme draft and nothing is kept until you press Save.</p>
        {notReady && <div className="mb-3 border border-amber-line bg-amber-bg px-4 py-3 text-sm text-amber-fg">AI is not switched on for your company yet. The owner adds a key and switches it on in the AI Drafting page.</div>}
        {err && <div role="alert" className="mb-3 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button className="btn btn-solid" onClick={propose} disabled={busy || !!notReady} data-testid="ai-propose">{busy ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Sparkles size={14} aria-hidden />}{res?.proposals.length ? "Ask again" : "Propose logic"}</button>
          {dirty && <span className="text-xs text-muted-foreground">Your unsaved changes are saved first, so the AI sees what you see.</span>}
          {busy && <span className="text-sm text-muted-foreground" aria-live="polite">Asking the AI. This can take a minute…</span>}
        </div>

        {res && res.questions.length > 0 && (
          <section className="mb-4 border"><h3 className="border-b bg-muted px-3 py-2 text-xs tracking-wider">Questions to confirm</h3>
            <ul className="divide-y">{res.questions.map((q, i) => <li key={i} className="flex flex-wrap items-start gap-3 px-3 py-2 text-sm"><div className="min-w-0 flex-1"><span className="font-medium">{q.question}</span><span className="block text-xs text-muted-foreground">{q.why}</span>{qNote?.i === i && <span role="alert" className="mt-1 block border border-red-line bg-red-bg px-2 py-1 text-xs text-red-fg">{qNote.text}</span>}</div>
              <button className="btn btn-ghost shrink-0" disabled={!!rfis[i]} onClick={() => makeRfi(i, q)} data-testid="question-to-rfi">{rfis[i] ? "RFI added" : "Make this an RFI"}</button></li>)}</ul>
          </section>
        )}
        {res && rows("link").length > 0 && <section className="mb-4 border"><h3 className="border-b bg-muted px-3 py-2 text-xs tracking-wider">Links to add ({rows("link").length})</h3><ul>{rows("link").map((p) => <Row key={p.id} p={p} />)}</ul></section>}
        {res && rows("remove").length > 0 && <section className="mb-4 border"><h3 className="border-b bg-muted px-3 py-2 text-xs tracking-wider">Links to remove ({rows("remove").length})</h3><ul>{rows("remove").map((p) => <Row key={p.id} p={p} />)}</ul></section>}
        {res && res.proposals.length === 0 && !busy && <p className="text-sm text-muted-foreground">No proposals waiting. Press Propose logic.</p>}
        {res?.coverage_notes && <p className="mb-4 text-xs text-muted-foreground">AI note: {res.coverage_notes}</p>}

        {res && res.proposals.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-4">
            <button className="btn btn-solid" onClick={applyChosen} disabled={busy || chosen.length === 0} data-testid="ai-apply">Apply {chosen.length} selected to my programme</button>
            <input className="h-10 min-w-[14rem] flex-1 border bg-background px-3 text-sm" placeholder="Why reject? (a few words)" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason for rejecting the selected proposals" />
            <button className="btn btn-ghost" onClick={rejectChosen} disabled={busy || chosen.length === 0 || reason.trim().length < 5} data-testid="ai-reject">Reject selected</button>
          </div>
        )}
      </div>
    </Modal>
  );
}
