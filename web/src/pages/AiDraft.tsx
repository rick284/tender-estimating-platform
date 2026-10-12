import { useCallback, useEffect, useState } from "react";
import { api, type AiProposal, type AiStatus, type IntakePlan, type DriveTextSummary } from "../lib/api";
import { Chip, Empty, PageHeader, Panel } from "../components/ui";
import { fmtNum } from "../lib/format";
import { useEdit } from "../lib/edit";

const KIND: Record<AiProposal["kind"], string> = { document: "Document", rfi: "RFI", assumption: "Assumption", exclusion: "Exclusion", inclusion: "Inclusion", risk: "Risk" };
const STATUS: Record<AiProposal["status"], { tone: "green" | "amber" | "red" | "neutral"; text: string }> = {
  verified: { tone: "green", text: "Quotes verified" }, gap: { tone: "amber", text: "Information gap" },
  unverified: { tone: "red", text: "Can't accept: quote not found" }, duplicate: { tone: "neutral", text: "Already in the register" },
};

function Card({ p, note, onAccept, onReject }: { p: AiProposal; note?: string; onAccept: (p: AiProposal) => void; onReject: (p: AiProposal, reason: string) => void }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const can = p.status === "verified" || p.status === "gap";
  return (
    <div className="border bg-background p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="neutral">{KIND[p.kind]}</Chip><Chip tone={p.rag === "RED" ? "red" : "amber"}>{p.rag}</Chip><Chip tone={STATUS[p.status].tone}>{STATUS[p.status].text}</Chip>
        <Chip tone="neutral" title="Nothing the AI drafts is verified until you approve it">AI draft</Chip>
      </div>
      <h3 className="mt-2 text-base font-semibold normal-case">{p.title}</h3>
      <p className="mt-1 whitespace-pre-line text-sm">{p.detail}</p>
      {p.impact && <p className="mt-2 whitespace-pre-line text-sm"><span className="label">If unresolved </span>{p.impact}</p>}
      {p.evidence.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {p.evidence.map((e, i) => (
            <li key={i} className="border-l-2 pl-3 text-sm" style={{ borderColor: e.verified ? "hsl(var(--green-line))" : "hsl(var(--red-line))" }}>
              <div className="text-xs text-muted-foreground">{e.file || "(unknown file)"} · page {e.page} · {e.verified ? "found in the document" : "NOT found in the document"}</div>
              <div>“{e.quote}”</div>
            </li>
          ))}
        </ul>
      )}
      {p.problems.length > 0 && <ul className="mt-2 list-inside list-disc text-sm text-red-fg">{p.problems.map((x) => <li key={x}>{x}</li>)}</ul>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {can && <button className="btn btn-solid !py-1.5" onClick={() => onAccept(p)}>Accept into my draft</button>}
        {note && <span role="alert" className="basis-full border border-red-line bg-red-bg px-3 py-2 text-sm text-red-fg">{note}</span>}
        {!rejecting && <button className="btn btn-ghost !py-1.5" onClick={() => setRejecting(true)}>Reject</button>}
        {rejecting && (
          <>
            <input aria-label="Reason for rejecting" className="h-9 min-w-[16rem] flex-1 border bg-background px-3 text-sm focus:border-primary" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why (a few words)" autoFocus />
            <button className="btn btn-solid !py-1.5" onClick={() => reason.trim().length >= 3 && onReject(p, reason.trim())}>Reject</button>
            <button className="btn btn-ghost !py-1.5" onClick={() => setRejecting(false)}>Cancel</button>
          </>
        )}
      </div>
    </div>
  );
}

export function AiDraft({ tenderId }: { tenderId: string }) {
  const { editing, add, canEdit, editHint, startEdit } = useEdit();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [texts, setTexts] = useState<DriveTextSummary[]>([]);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [props, setProps] = useState<AiProposal[]>([]);
  const [cardNote, setCardNote] = useState<{ id: string; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [ack, setAck] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [msg, setMsg] = useState("");
  const [plan, setPlan] = useState<IntakePlan | null>(null);
  const [prog, setProg] = useState<{ done: number; total: number; notes: string[]; made: number } | null>(null);

  const load = useCallback(async () => {
    try {
      const st = await api.aiStatus(); setStatus(st); setProvider(st.provider); setModel(st.model);
      setTexts((await api.driveTexts(tenderId)).texts.filter((t) => t.status === "ok" || t.status === "partial"));
      setProps((await api.aiProposals(tenderId)).proposals);
    } catch (e) { setErr((e as Error).message); }
  }, [tenderId]);
  useEffect(() => { load(); }, [load]);

  const toggle = (id: string) => setSel((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else if (n.size < (status?.max_files ?? 12)) n.add(id); return n; });
  const chars = texts.filter((t) => sel.has(t.file_id)).reduce((a, t) => a + t.chars, 0);

  const run = async () => {
    setErr(""); setNote(""); setBusy(true);
    try { const r = await api.aiDraft(tenderId, [...sel]); setNote(r.coverage_notes); setProps((await api.aiProposals(tenderId)).proposals); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const makePlan = async () => { setErr(""); setProg(null); try { setPlan(await api.aiIntakePlan(tenderId)); } catch (e) { setErr((e as Error).message); } };
  const runIntake = async () => {
    if (!plan) return;
    setErr(""); setBusy(true);
    const runId = "intake-" + Date.now().toString(36);
    const notes: string[] = []; let made = 0;
    setProg({ done: 0, total: plan.batches.length, notes, made });
    try {
      for (const b of plan.batches) {
        const r = await api.aiDraftParts(tenderId, b.parts, runId);
        made += r.proposals.filter((p) => p.status === "verified" || p.status === "gap").length;
        if (r.coverage_notes) notes.push(`Part ${b.index + 1}: ${r.coverage_notes}`);
        setProg({ done: b.index + 1, total: plan.batches.length, notes: [...notes], made });
        setProps((await api.aiProposals(tenderId)).proposals);
      }
    } catch (e) { setErr(`${(e as Error).message} (Parts already finished are kept below.)`); }
    finally { setBusy(false); }
  };
  const accept = async (p: AiProposal) => {
    setErr(""); setCardNote(null);
    if (!editing) {
      if (!canEdit) return setCardNote({ id: p.id, text: editHint || "This revision can't be edited, so nothing can be added to a draft. Open the latest revision and try again." });
      startEdit();                       // accepting needs edit mode: switch it on from here
    }
    try { const r = await api.aiAccept(p.id); add("register", r.edit.key, r.edit.value); setProps((await api.aiProposals(tenderId)).proposals); }
    catch (e) { setErr((e as Error).message); }
  };
  const reject = async (p: AiProposal, reason: string) => {
    setErr("");
    try { await api.aiReject(p.id, reason); setProps((await api.aiProposals(tenderId)).proposals); } catch (e) { setErr((e as Error).message); }
  };
  const call = async (fn: () => Promise<AiStatus>) => { setErr(""); setMsg(""); try { const st = await fn(); setStatus(st); setProvider(st.provider); setModel(st.model); setKey(""); } catch (e) { setErr((e as Error).message); } };
  const setOn = (on: boolean) => call(() => api.aiSettings({ enabled: on, acknowledged: on ? ack || !!status?.acknowledged_at : false }));
  const save = () => call(() => api.aiSettings({ provider, model: model.trim(), ...(key.trim() ? { api_key: key.trim() } : {}) }));
  const test = async () => { setErr(""); setMsg(""); try { const r = await api.aiTest(); setMsg(`Connected. Model found: ${r.model}.`); } catch (e) { setErr((e as Error).message); } };
  const open = props.filter((p) => !p.decision);
  const decided = props.filter((p) => p.decision);

  return (
    <div>
      <PageHeader title="AI Drafting" sub="The AI reads the documents you choose and proposes register items: documents, RFIs, assumptions, exclusions, inclusions and risks. It drafts only. Every proposal must quote the document, and the platform checks each quote. Nothing enters the estimate until you accept it into your draft and save a revision." />
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {status && status.can_change && (
        <Panel title="AI provider for this company" className="mb-4">
          <div className="grid gap-4 text-sm sm:grid-cols-3">
            <label className="block"><span className="label">Provider</span>
              <select className="mt-1 h-10 w-full border bg-background px-3 focus:border-primary" value={provider} onChange={(e) => { setProvider(e.target.value); const p = status.providers.find((x) => x.id === e.target.value); setModel(p?.default_model ?? ""); }}>
                {status.providers.map((p) => <option key={p.id} value={p.id} disabled={!p.available}>{p.label}{p.available ? "" : " (coming)"}</option>)}
              </select></label>
            <label className="block"><span className="label">Model</span><input className="mt-1 h-10 w-full border bg-background px-3 focus:border-primary" value={model} onChange={(e) => setModel(e.target.value)} maxLength={80} /></label>
            <label className="block"><span className="label">{status.key_last4 ? `API key (saved, ends ${status.key_last4}; paste to replace)` : "API key"}</span>
              <input type="password" autoComplete="off" className="mt-1 h-10 w-full border bg-background px-3 focus:border-primary" value={key} onChange={(e) => setKey(e.target.value)} placeholder={status.key_last4 ? "••••••••••••" : "sk-ant-…"} /></label>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{status.providers.find((p) => p.id === provider)?.key_hint} The key is stored encrypted, is never shown again, and is used only for this company.{status.key_source === "platform" && " This company is currently using the platform's key."}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button className="btn btn-solid" onClick={save} disabled={!key.trim() && provider === status.provider && model === status.model}>Save</button>
            <button className="btn btn-ghost" onClick={test} disabled={!status.configured}>Test connection</button>
            {status.key_source === "own" && <button className="underline underline-offset-4 text-sm" onClick={() => call(() => api.aiSettings({ clear_key: true }))}>Remove key</button>}
            {msg && <span className="text-sm text-green-fg">{msg}</span>}
          </div>
        </Panel>
      )}
      {status && !status.configured && !status.can_change && <Empty title="AI drafting is not set up for your company" body="The company owner needs to add an AI provider key." />}
      {status && status.configured && !status.enabled && (
        <Panel title="Switch on AI drafting" className="mb-4">
          <p className="mb-3 text-sm">When you run a draft, the <strong>text of the documents you select</strong> is sent to {status.providers.find((p) => p.id === status.provider)?.label} (model {status.model}) to be read. Nothing is sent until you press Draft, and only the documents you tick. Nothing it proposes changes the estimate without your approval.</p>
          {status.can_change ? (
            <>
              {!status.acknowledged_at && <label className="mb-3 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I understand that the text of the documents I select will be sent to this provider for drafting.</label>}
              <button className="btn btn-solid" disabled={!ack && !status.acknowledged_at} onClick={() => setOn(true)}>Switch on</button>
            </>
          ) : <p className="text-sm text-muted-foreground">Only the company owner can switch this on.</p>}
        </Panel>
      )}
      {status?.configured && status.enabled && (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
            <Chip tone="green">On</Chip><span>{status.providers.find((p) => p.id === status.provider)?.label} · model {status.model}</span>
            {status.can_change && <button className="underline underline-offset-4" onClick={() => setOn(false)}>Switch off</button>}
          </div>
          <Panel title="Whole-folder intake" className="mb-4">
            <p className="mb-3 text-sm">One run over every document already read from the Drive folder: latest revisions only, archive and superseded files left out. It is sent to the AI in several parts. Each part is told what the earlier parts found, so the same item is not proposed twice.</p>
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn btn-ghost" disabled={busy} onClick={makePlan}>Plan the run</button>
              {plan && plan.batches.length > 0 && plan.batches.length <= plan.max_batches && <button className="btn btn-solid" disabled={busy} onClick={runIntake}>{busy ? "Running…" : `Run intake (${plan.batches.length} ${plan.batches.length === 1 ? "part" : "parts"})`}</button>}
            </div>
            {plan && (
              <div className="mt-3 text-sm">
                <p>{plan.files} documents, {fmtNum(plan.total_chars)} characters, {plan.batches.length} {plan.batches.length === 1 ? "part" : "parts"} to be sent to {status.providers.find((p) => p.id === status.provider)?.label}.</p>
                {plan.batches.length > plan.max_batches && <p className="mt-1 text-red-fg">That is more than {plan.max_batches} parts. Read fewer files, or use the document picker below.</p>}
                {plan.batches.length === 0 && <p className="mt-1 text-muted-foreground">No readable, current documents yet. Read them on Drive Documents first.</p>}
                {plan.skipped.length > 0 && (
                  <details className="mt-2"><summary className="cursor-pointer">Not sent, or only partly readable ({plan.skipped.length})</summary>
                    <ul className="mt-1 list-inside list-disc text-muted-foreground">{plan.skipped.map((s, i) => <li key={i}>{s.name}: {s.reason}</li>)}</ul></details>
                )}
              </div>
            )}
            {prog && (
              <div className="mt-3 text-sm" role="status">
                <p>Part {prog.done} of {prog.total} done · {prog.made} new proposals so far{prog.done === prog.total && !busy ? ". Finished. Review them below." : ""}</p>
                {prog.notes.length > 0 && <ul className="mt-1 list-inside list-disc text-muted-foreground">{prog.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
              </div>
            )}
          </Panel>
          <Panel title="Or choose documents yourself (already read from Drive)" className="mb-4">
            {texts.length === 0 ? <p className="text-sm text-muted-foreground">No documents have been read yet. On Drive Documents, tick files and press Read.</p> : (
              <ul className="max-h-72 divide-y overflow-auto border">
                {texts.map((t) => (
                  <li key={t.file_id} className="flex items-center gap-3 px-3 py-2 text-sm">
                    <input type="checkbox" aria-label={`Select ${t.name}`} checked={sel.has(t.file_id)} onChange={() => toggle(t.file_id)} />
                    <span className="min-w-0 flex-1 truncate">{t.name}</span>
                    <span className="text-xs text-muted-foreground">{t.path || "main folder"} · {t.pages} p · {fmtNum(t.chars)} chars</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button className="btn btn-solid" disabled={busy || sel.size === 0} onClick={run}>{busy ? "Drafting… this can take a minute" : `Draft register items (${sel.size})`}</button>
              <span className="text-xs text-muted-foreground">{sel.size > 0 ? `About ${fmtNum(chars)} characters will be sent to Anthropic.` : `Up to ${status.max_files} documents per run.`}</span>
            </div>
            {note && <p className="mt-3 text-sm text-muted-foreground">AI note: {note}</p>}
          </Panel>
          <h2 className="mb-2 text-sm tracking-wider">2. Review the proposals ({open.length})</h2>
          {open.length === 0 ? <Empty title="Nothing waiting for review" body="Choose documents and press Draft. Proposals appear here for you to accept or reject." /> : (
            <div className="space-y-3">{open.map((p) => <Card key={p.id} p={p} note={cardNote?.id === p.id ? cardNote.text : undefined} onAccept={accept} onReject={reject} />)}</div>
          )}
          {decided.length > 0 && (
            <details className="mt-6">
              <summary className="cursor-pointer text-sm">Decided ({decided.length})</summary>
              <ul className="mt-2 divide-y border text-sm">
                {decided.map((p) => <li key={p.id} className="flex flex-wrap items-center gap-2 px-3 py-2"><Chip tone={p.decision?.decision === "accepted" ? "green" : "neutral"}>{p.decision?.decision}</Chip><span>{KIND[p.kind]}: {p.title}</span>{p.decision?.reason && <span className="text-muted-foreground">— {p.decision.reason}</span>}</li>)}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}
