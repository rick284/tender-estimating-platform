import { useEffect, useMemo, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import { Modal } from "../components/Modal";
import type { Estimate } from "../lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Task = any;
const field = "border bg-background px-2 text-sm";

const TYPES = [
  { value: "FS", label: "Finish to Start (FS)" },
  { value: "SS", label: "Start to Start (SS)" },
  { value: "FF", label: "Finish to Finish (FF)" },
  { value: "SF", label: "Start to Finish (SF)" },
];

/** What a task depends on: pick the task, the link type and a lag in days (negative = lead / overlap). */
export function LinksDialog({ open, task, tasks, onClose, onApply }: { open: boolean; task: Task | null; tasks: Task[]; onClose: () => void; onApply: (preds: Task[]) => void }) {
  const [rows, setRows] = useState<{ uid: string; type: string; lag: string }[]>([]);
  useEffect(() => {
    if (open && task) setRows((task.predecessors || []).map((p: Task) => ({ uid: String(p.uid), type: p.type || "FS", lag: String(p.lag_days || 0) })));
  }, [open, task]);
  const options = useMemo(() => (task ? tasks.filter((t) => t.uid !== task.uid) : []), [tasks, task]);
  const successors = useMemo(() => (task ? tasks.filter((t) => (t.predecessors || []).some((p: Task) => p.uid === task.uid)) : []), [tasks, task]);
  const update = (i: number, patch: Partial<{ uid: string; type: string; lag: string }>) => setRows((prev) => prev.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const apply = () => {
    const seen = new Set<string>();
    const preds: Task[] = [];
    rows.forEach((r) => {
      if (!r.uid || seen.has(r.uid)) return;
      seen.add(r.uid);
      const target = tasks.find((t) => String(t.uid) === r.uid);
      preds.push({ uid: Number(r.uid), id: target ? target.id : undefined, type: r.type, lag_days: Math.round(Number(r.lag) || 0) });
    });
    onApply(preds);
  };
  return (
    <Modal open={open && !!task} onClose={onClose} title={`Dependencies${task ? ` - ${task.id}. ${task.name}` : ""}`} wide>
      <p className="mb-3 text-sm text-muted-foreground">This task cannot start or finish until the tasks below allow it. Use a negative lag for a lead (overlap).</p>
      <div className="space-y-2" data-testid="program-links-dialog">
        <p className="label">Depends on (predecessors)</p>
        {rows.length === 0 && <p className="border border-dashed p-3 text-sm text-muted-foreground">No predecessors: this task starts on the project start date (or its fixed start).</p>}
        {rows.map((r, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2" data-testid="link-row">
            <select className={`${field} h-9 min-w-[12rem] flex-1`} value={r.uid} onChange={(e) => update(i, { uid: e.target.value })} data-testid="link-task" aria-label="Predecessor task">
              <option value="">Choose a task…</option>
              {options.map((t) => <option key={t.uid} value={t.uid}>{`${t.id}. ${"  ".repeat(Math.max(0, t.outline_level - 1))}${t.name}`}</option>)}
            </select>
            <select className={`${field} h-9`} value={r.type} onChange={(e) => update(i, { type: e.target.value })} data-testid="link-type" aria-label="Link type">
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <label className="flex items-center gap-1 text-xs text-muted-foreground">Lag
              <input type="number" step="1" value={r.lag} onChange={(e) => update(i, { lag: e.target.value })} className={`${field} h-9 w-16 text-right`} data-testid="link-lag" />d
            </label>
            <button className="p-1 text-muted-foreground hover:text-red-fg" onClick={() => setRows((prev) => prev.filter((_, k) => k !== i))} title="Remove" aria-label="Remove predecessor"><Trash2 size={16} /></button>
          </div>
        ))}
        <button type="button" className="btn btn-ghost !py-1.5" onClick={() => setRows((prev) => [...prev, { uid: "", type: "FS", lag: "0" }])} data-testid="link-add"><Plus size={14} aria-hidden />Add predecessor</button>
      </div>
      {successors.length > 0 && (
        <div className="pt-4">
          <p className="label mb-1">Tasks that depend on this one</p>
          <p className="text-sm text-muted-foreground">{successors.map((t) => `${t.id}. ${t.name}`).join("  ·  ")}</p>
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-solid" onClick={apply} data-testid="links-apply">Apply</button>
      </div>
    </Modal>
  );
}

const CUSTOM_TYPES = ["labour", "plant", "subcontractor", "material", "other"];
const norm = (c: string) => (c || "").trim().toLowerCase();

/** Assign resources to one task: pick from the tender's rate library or add a custom one, with units (e.g. 2 labourers) on the task at once. */
export function ResourceDialog({ open, task, library, onClose, onApply }: { open: boolean; task: Task | null; library: Estimate["library"]; onClose: () => void; onApply: (a: Task[]) => void }) {
  const [assigned, setAssigned] = useState<Task[]>([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [customName, setCustomName] = useState("");
  const [customType, setCustomType] = useState("labour");
  useEffect(() => {
    if (open && task) { setAssigned((task.resource_assignments || []).map((a: Task) => ({ ...a }))); setQ(""); setType(""); setCustomName(""); }
  }, [open, task]);
  const cats = useMemo(() => Array.from(new Set(library.map((l) => norm(l.category)).filter(Boolean))).slice(0, 8), [library]);
  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    return library.filter((l) => (!type || norm(l.category) === type) && (!s || `${l.code} ${l.description}`.toLowerCase().includes(s))).slice(0, 60);
  }, [library, q, type]);
  const addLib = (l: Estimate["library"][number]) => setAssigned((prev) => {
    const ex = prev.find((a) => a.resource_id === l.code);
    if (ex) return prev.map((a) => (a === ex ? { ...a, units: (Number(a.units) || 0) + 1 } : a));
    return [...prev, { resource_id: l.code, name: l.description, type: norm(l.category), unit: l.unit, units: 1 }];
  });
  const addCustom = () => {
    const name = customName.trim();
    if (!name) return;
    setAssigned((prev) => [...prev, { resource_id: null, name, type: customType, unit: null, units: 1 }]);
    setCustomName("");
  };
  const apply = () => onApply(assigned.map((a) => ({ ...a, units: Math.max(0.1, Number(a.units) || 1) })).filter((a) => a.name));
  return (
    <Modal open={open && !!task} onClose={onClose} title={`Resources${task ? ` - ${task.name}` : ""}`} wide>
      <p className="mb-3 text-sm text-muted-foreground">Pick from this tender's rate library or add a custom one. Units is how many are on the task at once (e.g. 2 labourers).</p>
      <div className="grid gap-4 md:grid-cols-2" data-testid="program-resource-dialog">
        <div className="space-y-2">
          <p className="label">Rate library</p>
          <div className="relative">
            <Search size={14} className="absolute left-2 top-3 text-muted-foreground" aria-hidden />
            <input className={`${field} h-10 w-full pl-7`} placeholder="Search code or description" value={q} onChange={(e) => setQ(e.target.value)} data-testid="resource-search" aria-label="Search resources" />
          </div>
          <div className="flex flex-wrap gap-1">
            {["", ...cats].map((c) => (
              <button key={c || "all"} className={`border px-2 py-0.5 text-xs capitalize ${type === c ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"}`} onClick={() => setType(c)}>{c || "All"}</button>
            ))}
          </div>
          <div className="h-56 overflow-y-auto border">
            {results.length === 0 && <div className="p-3 text-xs text-muted-foreground">No matching rates. Add a custom resource below.</div>}
            {results.map((l) => (
              <button key={l.code} className="flex w-full items-center gap-2 border-b px-2 py-1.5 text-left text-xs hover:bg-muted" onClick={() => addLib(l)} data-testid="resource-result">
                <Plus size={12} className="flex-none" aria-hidden />
                <span className="font-mono">{l.code}</span><span className="flex-1 truncate">{l.description}</span>
                <span className="text-muted-foreground">{l.unit}</span>
              </button>
            ))}
          </div>
          <p className="label pt-2">Custom resource</p>
          <div className="flex gap-2">
            <input className={`${field} h-10 min-w-0 flex-1`} placeholder="e.g. Dave's crew" value={customName} onChange={(e) => setCustomName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addCustom()} data-testid="custom-resource-name" aria-label="Custom resource name" />
            <select className={`${field} h-10 capitalize`} value={customType} onChange={(e) => setCustomType(e.target.value)} aria-label="Custom resource type">{CUSTOM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select>
            <button type="button" className="btn btn-ghost" onClick={addCustom} data-testid="custom-resource-add">Add</button>
          </div>
        </div>
        <div className="space-y-2">
          <p className="label">On this task ({assigned.length})</p>
          <div className="min-h-[14rem] border">
            {assigned.length === 0 && <div className="p-3 text-xs text-muted-foreground">Nothing assigned yet.</div>}
            {assigned.map((a, i) => (
              <div key={`${a.resource_id || a.name}-${i}`} className="flex items-center gap-2 border-b px-2 py-1.5 text-xs" data-testid="assigned-resource">
                <span className="flex-1 truncate">{a.name}{!a.resource_id && <span className="ml-1 text-2xs text-muted-foreground">(custom)</span>}</span>
                <span className="border px-1 text-2xs uppercase">{a.type || "other"}</span>
                <span className="text-muted-foreground">Units</span>
                <input type="number" min="0.1" step="0.5" value={a.units} onChange={(e) => setAssigned((prev) => prev.map((x, k) => (k === i ? { ...x, units: e.target.value } : x)))} className={`${field} h-7 w-14 text-right`} data-testid="assigned-units" aria-label={`Units of ${a.name}`} />
                <button onClick={() => setAssigned((prev) => prev.filter((_, k) => k !== i))} className="text-muted-foreground hover:text-red-fg" title="Remove" aria-label={`Remove ${a.name}`}><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-solid" onClick={apply} data-testid="resource-apply">Apply</button>
      </div>
    </Modal>
  );
}
