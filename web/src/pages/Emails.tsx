import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type EmailThread, type EmailThreadFull } from "../lib/api";
import type { Estimate } from "../lib/types";
import { Chip, Empty, PageHeader, Panel } from "../components/ui";

const KIND: Record<string, { page: string; label: string }> = { Q: { page: "quotes", label: "Quotes" }, RFI: { page: "register", label: "Register" }, RT: { page: "risk", label: "Risk Truth" }, SC: { page: "scope", label: "Scope Coverage" }, MR: { page: "reserve", label: "Management Reserve" } };
const kind = (r: string) => r.match(/^[A-Z]+/)?.[0] ?? "";
const fmtDate = (d: string) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" }) : "No date");

/** Email threads that Mason saved as text in the job's Drive folder (04.1 Emails In, 04.2 Emails Out - drafts). Read only: nothing is sent from here. */
export function Emails({ tenderId, est, goPage }: { tenderId: string; est?: Estimate; goPage: (page: string) => void }) {
  const [list, setList] = useState<EmailThread[] | null>(null);
  const [total, setTotal] = useState(0);
  const [refs, setRefs] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [dir, setDir] = useState("");
  const [ref, setRef] = useState("");
  const [open, setOpen] = useState<EmailThreadFull | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const load = useCallback(() => api.emails(tenderId, q, dir, ref).then((r) => { setList(r.threads); setTotal(r.total); setRefs(r.refs); }).catch((e) => setErr((e as Error).message)), [tenderId, q, dir, ref]);
  useEffect(() => { const t = setTimeout(() => void load(), 200); return () => clearTimeout(t); }, [load]);
  const refresh = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const r = await api.emailsRefresh(tenderId);
      setMsg(`${r.found} email file${r.found === 1 ? "" : "s"} found in the job folder, ${r.read} new or changed read.${r.problems.length ? ` Problems: ${r.problems.join(" ")}` : ""}${r.truncated ? " The folder is very large, so some files may not have been checked." : ""}`);
      await load();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const show = (t: EmailThread) => api.emailThread(tenderId, t.file_id).then(setOpen).catch((e) => setErr((e as Error).message));
  const exists = useMemo(() => {
    const s = new Set<string>();
    (est?.quotes ?? []).forEach((x) => s.add(x.ref)); (est?.register ?? []).forEach((x) => s.add(x.ref)); (est?.scope?.items ?? []).forEach((x) => s.add(x.ref));
    return s;
  }, [est]);
  const estHits = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (term.length < 3 || !est) return [];
    const hit = (...f: string[]) => f.join(" ").toLowerCase().includes(term);
    return [
      ...(est.quotes ?? []).filter((x) => hit(x.ref, x.supplier, x.package, x.scope, x.notes)).map((x) => ({ page: "quotes", ref: x.ref, text: `${x.supplier} - ${x.package}` })),
      ...(est.register ?? []).filter((x) => hit(x.ref, x.title, x.detail)).map((x) => ({ page: "register", ref: x.ref, text: x.title })),
      ...(est.scope?.items ?? []).filter((x) => hit(x.ref, x.title, x.detail)).map((x) => ({ page: "scope", ref: x.ref, text: x.title })),
    ].slice(0, 12);
  }, [q, est]);
  const refChip = (r: string, on?: () => void) => {
    const known = exists.has(r), k = KIND[kind(r)];
    return (
      <button key={r} type="button" onClick={on ?? (() => k && known && goPage(k.page))} title={known ? `Open in ${k?.label ?? "the estimate"}` : "Mentioned in the email but not found in this estimate"}
        className={`border px-1.5 py-0.5 font-mono text-2xs ${known ? "border-green-line bg-green-bg text-green-fg" : "border-amber-line bg-amber-bg text-amber-fg"}`}>{r}</button>
    );
  };
  return (
    <div>
      <PageHeader title="Emails" sub="Email threads saved in the job's Drive folder (04.1 Emails In and 04.2 Emails Out - drafts). Read only: nothing is sent, edited or deleted from here."
        actions={<button className="btn btn-ghost" onClick={refresh} disabled={busy}>{busy ? "Reading Drive…" : "Refresh from Drive"}</button>} />
      {err && <div role="alert" className="mb-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      {msg && <div className="mb-4 border px-4 py-3 text-sm" aria-live="polite">{msg}</div>}
      {list && total === 0 && !q && !dir && !ref ? (
        <Empty title="No emails saved yet" body="Ask Mason to save each email thread as a text file in 04.1 Emails In (received) or 04.2 Emails Out - DRAFT ONLY (drafts), then press Refresh from Drive. Each file can hold one thread: who, when, the subject, the messages, attachment names and any references like RFI-06 or Q-03." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap gap-2">
              <input aria-label="Search emails" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search emails, quotes, RFIs, scope" className="h-10 min-w-0 flex-1 border bg-background px-3 text-sm focus:border-primary" />
              <select aria-label="Direction" value={dir} onChange={(e) => setDir(e.target.value)} className="h-10 border bg-background px-2 text-sm"><option value="">All</option><option value="in">Received</option><option value="out">Drafts out</option></select>
            </div>
            {refs.length > 0 && <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs"><span className="text-muted-foreground">Mentions:</span>
              {refs.map((r) => <button key={r} type="button" aria-pressed={ref === r} onClick={() => setRef(ref === r ? "" : r)} className={`border px-1.5 py-0.5 font-mono text-2xs ${ref === r ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>{r}</button>)}</div>}
            {estHits.length > 0 && <Panel title="Also in the estimate" className="mb-3" flush>
              <ul className="divide-y text-sm">{estHits.map((h) => <li key={h.page + h.ref}><button type="button" className="flex w-full gap-2 px-3 py-2 text-left hover:bg-muted" onClick={() => goPage(h.page)}><span className="font-mono text-xs">{h.ref}</span><span className="min-w-0 truncate">{h.text}</span></button></li>)}</ul></Panel>}
            {!list ? <p className="text-sm text-muted-foreground" aria-live="polite">Loading…</p> : list.length === 0 ? <p className="text-sm text-muted-foreground">No email matches.</p> : (
              <ul className="divide-y border" aria-label="Email threads">
                {list.map((t) => (
                  <li key={t.file_id}>
                    <button type="button" onClick={() => void show(t)} aria-current={open?.file_id === t.file_id} className={`block w-full px-3 py-2.5 text-left hover:bg-muted ${open?.file_id === t.file_id ? "bg-muted" : ""}`}>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><span>{fmtDate(t.date)}</span><Chip tone={t.direction === "in" ? "neutral" : "amber"}>{t.direction === "in" ? "Received" : "Draft, not sent"}</Chip>{t.count > 1 && <span>{t.count} messages</span>}</div>
                      <div className="mt-0.5 text-sm font-medium">{t.subject}</div>
                      <div className="text-xs text-muted-foreground">{t.party}</div>
                      {t.hit && <div className="mt-1 text-xs italic text-muted-foreground">{t.hit}</div>}
                      {t.refs.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{t.refs.map((r) => <span key={r} className="border px-1 font-mono text-2xs">{r}</span>)}</div>}
                    </button>
                  </li>))}
              </ul>
            )}
          </div>
          <div className="min-w-0">
            {!open ? <Empty title="Choose an email" body="Pick a thread on the left to read it in full." /> : (
              <Panel title={open.subject} action={open.link ? <a className="btn btn-ghost !py-1.5" href={open.link} target="_blank" rel="noreferrer">Open in Drive</a> : undefined}>
                <div className="mb-3 flex flex-wrap items-center gap-2 text-sm"><Chip tone={open.direction === "in" ? "neutral" : "amber"}>{open.direction === "in" ? "Received" : "Draft, not sent"}</Chip><span>{fmtDate(open.date)}</span><span className="text-muted-foreground">{open.party}</span></div>
                {open.refs.length > 0 && <div className="mb-3 flex flex-wrap items-center gap-1.5 text-xs"><span className="text-muted-foreground">Linked to:</span>{open.refs.map((r) => refChip(r))}</div>}
                {(open.attachments.length > 0 || open.links.length > 0) && <div className="mb-3 text-sm"><div className="label">Attachments and links</div><ul className="list-disc pl-5">
                  {open.attachments.map((a) => <li key={a}>{a}</li>)}{open.links.map((u) => <li key={u}><a className="underline underline-offset-4" href={u} target="_blank" rel="noreferrer">{u.length > 70 ? u.slice(0, 70) + "…" : u}</a></li>)}</ul></div>}
                {open.messages.length > 0 ? open.messages.map((m, i) => (
                  <article key={i} className="mb-3 border-t pt-3 first:border-0 first:pt-0">
                    <div className="mb-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground">{m.from && <span className="font-medium text-foreground">{m.from}</span>}{m.date && <span>{fmtDate(m.date)}</span>}{m.subject && <span>{m.subject}</span>}{m.gmail_id && <span className="font-mono">Gmail {m.gmail_id}</span>}</div>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.body}</p>
                  </article>)) : <p className="whitespace-pre-wrap text-sm">{open.text}</p>}
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
