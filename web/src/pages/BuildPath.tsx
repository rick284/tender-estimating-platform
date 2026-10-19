import { useEffect, useState } from "react";
import { api, type BuildStep, type GoAhead, type StepDetail, type StepOneData, type StepsOverview } from "../lib/api";
import type { Estimate } from "../lib/types";
import { newUid, useEdit } from "../lib/edit";
import { fmtMoney } from "../lib/format";
import { Markdown } from "../components/Markdown";
import { Chip, Empty, PageHeader, Panel } from "../components/ui";
import { go } from "../lib/route";

export const stepTone = (s: string): "green" | "amber" | "red" | "neutral" =>
  s === "APPROVED-LOCKED" ? "green" : s === "DRAFT" || s === "REPORTED" ? "amber" : s === "REOPENED" ? "red" : "neutral";
export const stepLabel = (s: string) =>
  ({ "APPROVED-LOCKED": "Approved, locked", DRAFT: "Draft", REPORTED: "Reported, not yet approved", REOPENED: "Reopened", READY: "Ready to start", "NOT STARTED": "Not started" } as Record<string, string>)[s] ?? s;

function NoData({ tenderId, msg }: { tenderId: string; msg: string }) {
  return (
    <>
      <Empty title="No build path to show yet" body={msg} />
      <div className="mt-4 text-center"><button className="btn btn-solid" onClick={() => go({ name: "tender", id: tenderId, page: "drive", rev: null })}>Open Drive Documents</button></div>
    </>
  );
}

export function JobRecord({ tenderId, data, err, reload, loading }: { tenderId: string; data: StepsOverview | null; err: string; reload: () => void; loading: boolean }) {
  const f = data?.job_record.fields ?? {};
  const open = (k: string) => go({ name: "tender", id: tenderId, page: `step-${k}`, rev: null });
  return (
    <>
      <PageHeader title="Job Record" sub="The index of the job, kept in the job folder by the senior estimator. The app only reads it. Every item keeps the status the estimator gave it."
        actions={<><button className="btn btn-ghost" onClick={reload} disabled={loading}>{loading ? "Reading…" : "Refresh from Drive"}</button>{data?.job_record.link && <a className="btn btn-ghost" href={data.job_record.link} target="_blank" rel="noreferrer">Open in Drive</a>}</>} />
      <GoAheadPanel tenderId={tenderId} />
      {err && <NoData tenderId={tenderId} msg={err} />}
      {!err && loading && !data && <p className="text-sm text-muted-foreground" aria-live="polite">Reading the job folder…</p>}
      {!err && data && !data.job_record.found && <NoData tenderId={tenderId} msg="There is no JOB_RECORD.md in 00 Project Admin of the linked Drive folder yet. It appears when the first step finishes." />}
      {!err && data?.job_record.found && (
        <>
          <Panel className="mb-4">
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
              {([["Revision", "revision"], ["Release status", "release_status"], ["Lifecycle", "lifecycle"], ["Stage reached", "stage"], ["Mode", "mode"], ["Updated", "updated"], ["Price excl. GST", "price"], ["Tender closes", "tender_closes"], ["Last step completed", "step_completed"]] as const)
                .filter(([, k]) => f[k]).map(([l, k]) => <div key={k}><dt className="label">{l}</dt><dd className="mt-0.5 text-sm">{k === "release_status" ? <Chip tone={f[k] === "HOLD" ? "red" : "green"}>{f[k]}</Chip> : f[k]}</dd></div>)}
            </dl>
          </Panel>
          <Panel className="mb-4" title={`Steps (${data.counts.steps})`} flush>
            {data.steps.length === 0 ? <p className="px-4 py-3 text-sm text-muted-foreground">No steps listed yet.</p> : (
              <div className="grid-scroll"><table className="grid-table min-w-[40rem]"><thead><tr><th className="w-16">Step</th><th className="min-w-[14rem]">Name</th><th className="w-44">Status</th><th className="w-28">Workbook</th></tr></thead>
                <tbody>{data.steps.map((s) => (
                  <tr key={s.key} className="cursor-pointer" onClick={() => open(s.key)}>
                    <td className="font-mono text-xs">{s.key}</td><td>{s.name}<div className="text-xs text-muted-foreground">{s.group}</div></td>
                    <td><Chip tone={stepTone(s.status)}>{stepLabel(s.status)}</Chip></td><td className="text-sm">{s.workbook_revision || "—"}</td>
                  </tr>))}</tbody></table></div>
            )}
          </Panel>
          <Panel title="Whole record"><Markdown text={data.job_record.text} /></Panel>
        </>
      )}
    </>
  );
}

export function StepPage({ tenderId, stepKey, summary, reload, est }: { tenderId: string; stepKey: string; summary?: BuildStep; reload: () => void; est?: Estimate }) {
  const [d, setD] = useState<StepDetail | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => { setBusy(true); setErr(""); api.stepDetail(tenderId, stepKey).then(setD).catch((e) => { setD(null); setErr((e as Error).message); }).finally(() => setBusy(false)); };
  useEffect(() => { setD(null); load(); }, [tenderId, stepKey]);                                                        // eslint-disable-line react-hooks/exhaustive-deps
  const status = d?.status ?? summary?.status ?? "";
  return (
    <>
      <PageHeader title={`Step ${stepKey}: ${d?.name ?? summary?.name ?? ""}`} sub={d?.chat_title || summary?.chat_title || "Each step runs in its own chat. This page shows what that chat set out to do (the brief) and what it did (the report)."}
        actions={<button className="btn btn-ghost" onClick={() => { load(); reload(); }} disabled={busy}>{busy ? "Reading…" : "Refresh from Drive"}</button>} />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        {status && <Chip tone={stepTone(status)}>{stepLabel(status)}</Chip>}
        {(d?.group || summary?.group) && <Chip tone="neutral">{d?.group ?? summary?.group}</Chip>}
        {(d?.workbook_revision || summary?.workbook_revision) && <Chip tone="neutral">Workbook {d?.workbook_revision || summary?.workbook_revision}</Chip>}
        {status === "APPROVED-LOCKED" && <span className="text-muted-foreground">Locked: later steps build on this result and never redo it. A change needs a change note.</span>}
      </div>
      {stepKey === "01" && <StepOne tenderId={tenderId} est={est} />}
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {busy && !d && <p className="text-sm text-muted-foreground" aria-live="polite">Reading the step files…</p>}
      {d && !d.brief && !d.report && <Empty title="No files for this step yet" body="The step's brief and report appear here once the chat has saved them in the step folder." />}
      {d?.report && <Panel className="mb-4" title={`Report: ${d.report.name}`}><Markdown text={d.report.text} /></Panel>}
      {d?.brief && <Panel title={`Brief: ${d.brief.name}`}><Markdown text={d.brief.text} /></Panel>}
    </>
  );
}

// ---- Go-ahead checkpoint (Mason: stop after steps 01 and 02 until the client's go-ahead is recorded) ----
export function GoAheadPanel({ tenderId, initial }: { tenderId: string; initial?: GoAhead | null }) {
  const [g, setG] = useState<GoAhead | null | undefined>(initial);
  const [mode, setMode] = useState<"client_go" | "proceed_anyway">("client_go");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { if (initial !== undefined) setG(initial); }, [initial]);
  useEffect(() => { if (initial === undefined) api.stepOne(tenderId).then((d) => setG(d.go_ahead)).catch(() => setG(null)); }, [tenderId, initial]);
  const save = async () => { setErr(""); try { setG((await api.setGoAhead(tenderId, mode, note)).go_ahead); setNote(""); } catch (e) { setErr((e as Error).message); } };
  const clear = async () => { setErr(""); try { await api.clearGoAhead(tenderId); setG(null); } catch (e) { setErr((e as Error).message); } };
  return (
    <Panel title="Go-ahead checkpoint" className="mb-4">
      <p className="mb-3 text-sm">After the scope of work and the production programme, the actual work (takeoff, quotes, build-up, pricing) waits for the client's go-ahead. Recording it is yours alone.</p>
      {g ? (
        <div className="flex flex-wrap items-center gap-3 text-sm" role="status">
          <Chip tone={g.mode === "client_go" ? "green" : "amber"}>{g.mode === "client_go" ? "Client go-ahead recorded" : "Proceeding without go-ahead"}</Chip>
          <span>{new Date(g.at).toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" })}{g.by && ` by ${g.by}`}{g.note && `: ${g.note}`}</span>
          <button className="underline underline-offset-4" onClick={clear}>Clear</button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-[auto_1fr_auto] sm:items-end">
          <label className="block"><span className="label">What happened</span>
            <select className="mt-1 h-10 w-full border bg-background px-3 text-sm" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="client_go">The client has given the go-ahead</option><option value="proceed_anyway">Proceed anyway (scope stays subject to client confirmation)</option></select></label>
          <label className="block"><span className="label">Note (who, when, how)</span><input className="mt-1 h-10 w-full border bg-background px-3 text-sm" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="e.g. Dave replied by email 20 Oct" /></label>
          <button className="btn btn-solid" onClick={save}>Record</button>
        </div>
      )}
      {err && <div role="alert" className="mt-3 border border-red-line bg-red-bg px-3 py-2 text-sm text-red-fg">{err}</div>}
    </Panel>
  );
}

const groupFor = (title: string): string => {
  const t = title.toUpperCase();
  if (/PRELIM/.test(t)) return "Preliminaries and management";
  if (/ACCESS|TRAFFIC|CONSENT|SURVEY|EROSION|SEDIMENT/.test(t)) return "Access and site establishment";
  if (/LANDSCAPE|FENCING|BUILDING AND FIT|INTERFACE|UNDER-SLAB/.test(t)) return "Interface with others";
  if (/TEST|HANDOVER|COMPLIANCE/.test(t)) return "Reinstatement and handover";
  if (/CLEARING|DEWATER|UNSUITABLE/.test(t)) return "Enabling works";
  return "Permanent works";
};
const propTone = (p: string): "green" | "amber" | "red" | "neutral" => (/confirm/i.test(p) ? "amber" : /excluded|others/i.test(p) ? "neutral" : "green");

export function StepOne({ tenderId, est }: { tenderId: string; est?: Estimate }) {
  const { editing, add, canEdit, editHint, startEdit } = useEdit();
  const [d, setD] = useState<StepOneData | null>(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => { api.stepOne(tenderId).then(setD).catch((e) => setErr((e as Error).message)); }, [tenderId]);
  if (err) return <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>;
  if (!d) return <p className="mb-4 text-sm text-muted-foreground" aria-live="polite">Reading the Step 01 files…</p>;
  const have = new Set((est?.scope?.items ?? []).map((i) => i.ref));
  const rows = (d.scope?.rows ?? []).filter((r) => !have.has(`SC-${r.ref.padStart(3, "0")}`));
  const haveRfi = new Set((est?.register ?? []).filter((r) => r.kind === "rfi").map((r) => r.title));
  const qs = (d.scope?.questions ?? []).filter((q) => !haveRfi.has(`${q.ref}: ${q.title}`));
  const ready = (): boolean => {
    setNote("");
    if (!editing) { if (!canEdit) { setNote(editHint || "This revision can't be edited. Open the latest revision first."); return false; } startEdit(); }
    return true;
  };
  const addRows = () => { if (!ready()) return; for (const r of rows) add("scope", "C-" + newUid().slice(2), { ref: `SC-${r.ref.padStart(3, "0")}`, group: groupFor(r.title), title: r.title.charAt(0) + r.title.slice(1).toLowerCase(), detail: `Proposed: ${r.proposal}. ${r.detail}`.slice(0, 3000), source: r.source, owner: r.owner, treatment: r.treatment, action: "Client response to the Scope Confirmation: pending" }); };
  const addRfis = () => { if (!ready()) return; for (const q of qs) add("register", newUid(), { kind: "rfi", title: `${q.ref}: ${q.title}`, detail: q.question, rag: "AMBER", status: "OPEN", action: "Written answer requested from the client (Scope Confirmation)" }); };
  const p = d.proposal;
  return (
    <>
      <GoAheadPanel tenderId={tenderId} initial={d.go_ahead} />
      {!d.scope && !p && !d.card && <Empty title="No Step 01 files found yet" body="Save the Scope Confirmation and Estimating Proposal (Word files) anywhere in the linked job folder, then refresh." />}
      {p && p.cases.length > 0 && (
        <Panel title={`Estimating proposal${p.revision ? ` Rev ${p.revision}` : ""}: the estimating service, not the construction price`} className="mb-4">
          <div className="mb-3 flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <div><div className="label">Indicative fee window (excl. GST)</div><div className="font-mono text-2xl font-bold">{fmtMoney(p.low_fee ?? 0)} to {fmtMoney(p.high_fee ?? 0)}</div></div>
            <div className="text-sm text-muted-foreground">{p.low_hours} to {p.high_hours} estimator hours{p.rate ? ` at ${fmtMoney(p.rate)} an hour` : ""}</div>
          </div>
          <table className="grid-table"><thead><tr><th>Case</th><th className="text-right">Hours</th><th className="text-right">Rate</th><th className="text-right">Fee</th></tr></thead>
            <tbody>{p.cases.map((c) => <tr key={c.label}><td>{c.label}</td><td className="num">{c.hours}</td><td className="num">{c.rate ? fmtMoney(c.rate) : "—"}</td><td className="num">{fmtMoney(c.fee)}</td></tr>)}</tbody></table>
        </Panel>
      )}
      {d.scope && (
        <Panel title={`Scope Confirmation (${d.scope.rows.length} items)`} className="mb-4" flush
          action={<button className="btn btn-solid !py-1.5" disabled={rows.length === 0} onClick={addRows}>{rows.length === 0 ? "All in Scope Coverage" : `Add ${rows.length} to Scope Coverage`}</button>}>
          <div className="grid-scroll"><table className="grid-table min-w-[42rem]"><thead><tr><th className="w-14">Ref</th><th className="min-w-[16rem]">Work item</th><th className="w-44">Our proposal</th><th className="min-w-[10rem]">Source</th></tr></thead>
            <tbody>{d.scope.rows.map((r) => (
              <tr key={r.ref}><td className="font-mono text-xs">{r.ref}</td><td>{r.title}<div className="text-xs text-muted-foreground">{r.detail}</div></td><td><Chip tone={propTone(r.proposal)}>{r.proposal}</Chip></td><td className="text-xs text-muted-foreground">{r.source}</td></tr>))}</tbody></table></div>
          <p className="border-t px-4 py-3 text-xs text-muted-foreground">Nothing here is priced. Adding the rows puts them in your edit draft as unresolved scope (owner and treatment suggested from the proposal); they only enter the estimate when you save a revision.</p>
        </Panel>
      )}
      {d.scope && d.scope.questions.length > 0 && (
        <Panel title={`Written answers wanted from the client (${d.scope.questions.length})`} className="mb-4" flush
          action={<button className="btn btn-ghost !py-1.5" disabled={qs.length === 0} onClick={addRfis}>{qs.length === 0 ? "All in the Register" : `Add ${qs.length} to the Register as RFIs`}</button>}>
          <table className="grid-table"><tbody>{d.scope.questions.map((q) => <tr key={q.ref}><td className="w-14 font-mono text-xs">{q.ref}</td><td className="w-64 font-medium">{q.title}</td><td>{q.question}</td></tr>)}</tbody></table>
        </Panel>
      )}
      {note && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{note}</div>}
      {d.card && <Panel title="Internal effort and decision card (internal only)" className="mb-4"><Markdown text={d.card} /></Panel>}
    </>
  );
}
