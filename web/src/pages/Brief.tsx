import type { Estimate } from "../lib/types";
import { EditField } from "../components/EditCells";
import { PageHeader, Panel } from "../components/ui";
import { useEdit } from "../lib/edit";
import { TENDER_LEVELS } from "../lib/intake";
import { briefFromScope } from "../lib/briefFromScope";
import { useState } from "react";

// Keys and limits match engine/tender_engine/brief.py
type F = { key: string; label: string; hint: string; long?: boolean };
const GROUPS: { title: string; sub: string; fields: F[] }[] = [
  { title: "The job", sub: "What is being built and why we are pricing it.", fields: [
    { key: "job_summary", label: "What the job is", hint: "A few sentences: what is being built, where, how big, what stage the design is at", long: true },
    { key: "location", label: "Location / site address", hint: "Site address or suburb" },
    { key: "tender_level", label: "Estimate level", hint: "" },
    { key: "purpose", label: "Purpose of this estimate", hint: "e.g. competitive tender, budget for the client, variation" },
  ] },
  { title: "Who", sub: "Who owns it, who we are pricing for and who else is involved.", fields: [
    { key: "client", label: "Client or head contractor", hint: "Who we are pricing for" },
    { key: "owner", label: "Project owner / developer", hint: "Who the building is for, if different" },
    { key: "consultants", label: "Designers and consultants", hint: "Architect, engineer, geotech, planner ...", long: true },
    { key: "contacts", label: "Key contacts", hint: "Name, role, email / phone, one per line", long: true },
  ] },
  { title: "Commercial", sub: "How the job is bought and when it is due.", fields: [
    { key: "contract_type", label: "Contract type", hint: "e.g. NZS 3910, lump sum" },
    { key: "pricing_basis", label: "Pricing basis", hint: "e.g. lump sum with provisional quantities" },
    { key: "tender_due", label: "Tender due", hint: "Date and time" },
    { key: "submission", label: "How and where to submit", hint: "Portal, email address, hard copy ...", long: true },
    { key: "validity", label: "Price validity, start and completion", hint: "e.g. 60 days; start Feb 2027", long: true },
  ] },
  { title: "What we know", sub: "Plain notes. Anything missing that matters becomes an RFI on the Register.", fields: [
    { key: "history", label: "History with this client / job", hint: "Past jobs, how they pay, who decides", long: true },
    { key: "known", label: "What we know so far", hint: "Facts and site knowledge, and where they came from", long: true },
    { key: "unknown", label: "What we do not know yet", hint: "Questions to ask, documents still to arrive", long: true },
  ] },
];

export function Brief({ est, recordFields }: { est: Estimate; recordFields?: Record<string, string> }) {
  const { editing, set, canEdit, editHint, startEdit } = useEdit();
  const meta = est.meta as Record<string, string>;
  const [msg, setMsg] = useState("");
  const fill = () => {
    if (!editing) { if (!canEdit) { setMsg(editHint || "This revision can't be edited. Open the latest revision first."); return; } startEdit(); }
    const data = briefFromScope(est, recordFields);
    const empty = Object.entries(data).filter(([k]) => !String(meta[k] ?? "").trim());
    if (Object.keys(data).length === 0) { setMsg("There is no scope yet. Add the scope items first (Step 01, or Scope Coverage)."); return; }
    empty.forEach(([k, v]) => set({ target: "brief", key: k, field: k, value: v, original: "" }));
    setMsg(empty.length ? `Filled ${empty.length} empty field${empty.length === 1 ? "" : "s"} from the scope (${empty.map(([k]) => GROUPS.flatMap((g) => g.fields).find((f) => f.key === k)?.label ?? k).join(", ")}). Review and edit, then save a revision. Fields you already wrote were left alone.` : "Nothing to fill: the overview fields already have your wording.");
  };
  return (
    <>
      <PageHeader title="Project brief" sub="What the job is, who owns it, who is involved and what we know about it. Written notes only: nothing here is priced."
        actions={<button className="btn btn-ghost" onClick={fill}>Fill empty fields from the scope</button>} />
      {msg && <div role="status" className="mb-4 border px-4 py-3 text-sm">{msg}</div>}
      {GROUPS.map((g) => (
        <Panel key={g.title} className="mb-4" title={g.title}>
          <p className="mb-3 text-sm text-muted-foreground">{g.sub}</p>
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {g.fields.map((f) => {
              const v = String(meta[f.key] ?? "");
              return (
                <div key={f.key} className={f.long ? "sm:col-span-2" : ""}>
                  <dt className="label">{f.label}</dt>
                  <dd className="mt-1 whitespace-pre-line text-sm leading-snug">
                    {f.key === "tender_level" ? (
                      <EditField target="brief" id={f.key} field={f.key} value={v} label={f.label} kind="select" width="w-48"
                        options={[{ value: "", label: "Not set" }, ...TENDER_LEVELS.map((l) => ({ value: l, label: l }))]} display={v || <span className="text-muted-foreground">Not recorded</span>} />
                    ) : (
                      <EditField target="brief" id={f.key} field={f.key} value={v} label={f.label} kind={f.long ? "textarea" : "text"} rows={f.key === "job_summary" || f.key === "known" || f.key === "unknown" ? 5 : 3}
                        width="w-full" placeholder={f.hint} display={v || <span className="text-muted-foreground">{editing ? "" : "Not recorded"}</span>} />
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>
        </Panel>
      ))}
    </>
  );
}
