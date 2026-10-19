import { useEffect, useState } from "react";
import { api, type BuildStep, type StepDetail, type StepsOverview } from "../lib/api";
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

export function StepPage({ tenderId, stepKey, summary, reload }: { tenderId: string; stepKey: string; summary?: BuildStep; reload: () => void }) {
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
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {busy && !d && <p className="text-sm text-muted-foreground" aria-live="polite">Reading the step files…</p>}
      {d && !d.brief && !d.report && <Empty title="No files for this step yet" body="The step's brief and report appear here once the chat has saved them in the step folder." />}
      {d?.report && <Panel className="mb-4" title={`Report: ${d.report.name}`}><Markdown text={d.report.text} /></Panel>}
      {d?.brief && <Panel title={`Brief: ${d.brief.name}`}><Markdown text={d.brief.text} /></Panel>}
    </>
  );
}
