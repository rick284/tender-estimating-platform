import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, type LabourCalc } from "../lib/api";
import { Modal } from "./Modal";
import { Chip } from "./ui";
import { fmtMoney } from "../lib/format";

const EVIDENCE = [
  { value: "company actual", label: "Company actual: this person's real payroll cost" },
  { value: "company historical", label: "Company historical: reviewed past actual" },
  { value: "comparable contractor", label: "Comparable contractor (reviewed)" },
  { value: "market normalised", label: "Market rate, converted to true cost" },
  { value: "raw wage", label: "Raw advertised wage (not a true-cost rate)" },
];
// percentages are typed as % and sent as fractions
const PCT = ["kiwisaver_pct", "levy_pct", "redundancy_pct", "supervision_pct"];
const BLANK: Record<string, string> = {
  role: "", jurisdiction: "NZ", employment_basis: "", source_date: "", evidence: "market normalised", source_note: "", reviewer: "",
  hourly_rate: "", paid_hours_week: "", productive_hours_week: "", kiwisaver_pct: "3", annual_leave_days: "20", stat_days: "11", sick_days: "5", other_paid_days: "0",
  days_per_week: "5", levy_pct: "", redundancy_pct: "0", weekly_allowance: "0", supervision_pct: "0",
};
const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary h-10";
const tone = { GREEN: "green", AMBER: "amber", RED: "red" } as const;

function toApi(f: Record<string, string>, check: boolean) {
  const o: Record<string, unknown> = { ...f, independent_check: check };
  for (const k of PCT) o[k] = f[k] === "" ? "" : String(Number((Number(f[k]) / 100).toFixed(8)));
  return o;
}
function fromInputs(i: Record<string, string | boolean>): Record<string, string> {
  const f = { ...BLANK };
  for (const k of Object.keys(BLANK)) if (i[k] !== undefined) f[k] = PCT.includes(k) ? String(Number((Number(i[k]) * 100).toFixed(6))) : String(i[k]);
  return f;
}

export function LabourBuilder({ open, onClose, existing, build, onSave, editing }: {
  open: boolean; onClose: () => void; existing: string[]; build?: { code: string; calc: LabourCalc }; onSave: (code: string, inputs: Record<string, unknown>) => void; editing: boolean;
}) {
  const [code, setCode] = useState("");
  const [f, setF] = useState<Record<string, string>>(BLANK);
  const [check, setCheck] = useState(false);
  const [calc, setCalc] = useState<LabourCalc | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!open) return;
    setErr(""); setCalc(null);
    if (build) { setCode(build.code); setF(fromInputs(build.calc.inputs)); setCheck(!!build.calc.inputs.independent_check); setCalc(build.calc); }
    else { setCode(""); setF(BLANK); setCheck(false); }
  }, [open, build]);
  const body = useMemo(() => toApi(f, check), [f, check]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    const t = setTimeout(() => { api.labourCalc(body).then((r) => { if (live) { setCalc(r); setErr(""); } }).catch((e) => { if (live) { setCalc(null); setErr(e instanceof Error ? e.message : "Couldn't calculate."); } }); }, 350);
    return () => { live = false; clearTimeout(t); };
  }, [body, open]);
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const ro = !editing;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const c = code.trim().toUpperCase();
    if (!build && (!c || existing.includes(c))) return setErr(!c ? "Give the rate a code, for example LAB-CARP." : `${c} already exists.`);
    if (!calc) return;
    onSave(build ? build.code : c, body); onClose();
  };
  const num = (k: string, label: string, hint?: string, suffix?: string) => (
    <label className="block"><span className="label">{label}</span>
      <div className="flex items-center gap-1"><input className={field} inputMode="decimal" value={f[k]} onChange={set(k)} readOnly={ro} aria-label={label} />{suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}</div>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}</label>
  );
  return (
    <Modal open={open} onClose={onClose} title={build ? `Labour rate ${build.code}` : "Build a labour rate"} huge>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">The true direct cost of having a person available for productive work, per productive hour. It excludes overhead, profit, vehicles and preliminaries. PAYE is not an employer cost. Every percentage is your own; nothing is assumed.</p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {!build && <label className="block"><span className="label">Rate code</span><input className={field} value={code} onChange={(e) => setCode(e.target.value)} placeholder="LAB-CARP" maxLength={20} /></label>}
              <label className="block"><span className="label">Role</span><input className={field} value={f.role} onChange={set("role")} readOnly={ro} placeholder="Carpenter" maxLength={80} /></label>
            </div>
            <label className="block"><span className="label">Where the numbers come from</span>
              <select className={field} value={f.evidence} onChange={set("evidence")} disabled={ro}>{EVIDENCE.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="label">Employment basis</span><input className={field} value={f.employment_basis} onChange={set("employment_basis")} readOnly={ro} placeholder="Permanent, full time" /></label>
              <label className="block"><span className="label">Source date</span><input className={field} value={f.source_date} onChange={set("source_date")} readOnly={ro} placeholder="Oct 2026" /></label>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {num("hourly_rate", "Gross hourly rate", "Before tax", "$/h")}
              {num("paid_hours_week", "Paid hours a week", "e.g. 45", "h")}
              {num("productive_hours_week", "Productive hours", "Left after breaks and travel", "h")}
            </div>
            <div className="grid grid-cols-4 gap-3">
              {num("kiwisaver_pct", "KiwiSaver", "Employer", "%")}
              {num("levy_pct", "Insurance and ACC levies", "Your current rate", "%")}
              {num("redundancy_pct", "Redundancy provision", "Optional", "%")}
              {num("supervision_pct", "Leading-hand loading", "Optional", "%")}
            </div>
            <div className="grid grid-cols-5 gap-3">
              {num("annual_leave_days", "Annual leave", undefined, "days")}
              {num("stat_days", "Public holidays", undefined, "days")}
              {num("sick_days", "Sick leave used", "Real use", "days")}
              {num("other_paid_days", "Other paid days", undefined, "days")}
              {num("days_per_week", "Days a week", undefined, "")}
            </div>
            {num("weekly_allowance", "Weekly allowances (tools, clothing, phone)", "Only if not priced elsewhere", "$/week")}
            <label className="block"><span className="label">Reviewed by</span><input className={field} value={f.reviewer} onChange={set("reviewer")} readOnly={ro} /></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={check} disabled={ro} onChange={(e) => setCheck(e.target.checked)} /> An independent check of this build-up has been done (needed for GREEN with a company actual).</label>
          </div>
          <div>
            {err && <div role="alert" className="mb-3 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
            {calc && (
              <div aria-live="polite">
                <table className="grid-table"><thead><tr><th>Step (one week)</th><th className="text-right">Amount</th><th className="text-right">Running</th></tr></thead>
                  <tbody>{calc.steps.map((s) => <tr key={s.label}><td>{s.label}<div className="text-xs text-muted-foreground">{s.basis}</div></td><td className="num">{fmtMoney(s.amount)}</td><td className="num">{fmtMoney(s.running)}</td></tr>)}</tbody></table>
                <div className="mt-3 flex flex-wrap items-center gap-3 border-t pt-3">
                  <div><div className="label">True cost per productive hour</div><div className="font-mono text-2xl font-bold">{fmtMoney(calc.rate)}</div></div>
                  <Chip tone={tone[calc.status]}>{calc.status}</Chip>
                  <div className="text-xs text-muted-foreground">Weekly cost {fmtMoney(calc.weekly_cost)} · {fmtMoney(calc.per_paid_hour)} per paid hour</div>
                </div>
                <p className="mt-2 text-sm">{calc.status_note}</p>
              </div>
            )}
            {build?.calc.history && build.calc.history.length > 0 && (
              <div className="mt-4"><div className="label">Earlier builds (kept)</div>
                <ul className="mt-1 text-sm">{build.calc.history.map((h, i) => <li key={i}>{fmtMoney(Number(h.rate))} · {h.evidence} · {h.source_date} · {h.status}</li>)}</ul></div>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>{editing ? "Cancel" : "Close"}</button>
          {editing && <button className="btn btn-solid" disabled={!calc}>{build ? "Update this rate" : "Add to rate library"}</button>}</div>
      </form>
    </Modal>
  );
}
