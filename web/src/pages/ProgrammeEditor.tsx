import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown, ArrowLeft, ArrowUp, ClipboardList, Download, Eye, FilePlus2, FileText, Flag, IndentDecrease, IndentIncrease, Link2, Link2Off,
  Loader2, Pencil, Plus, Redo2, Save, Trash2, Undo2, Upload,
} from "lucide-react";
import { api, ApiError, type ProgrammeDoc } from "../lib/api";
import { go } from "../lib/route";
import { toast } from "../lib/toast";
import type { Estimate } from "../lib/types";
import { Chip, Empty, PageHeader, Panel } from "../components/ui";
import { Modal } from "../components/Modal";
// The scheduling logic and the Gantt chart are plain JavaScript modules carried over from the Blackline programme viewer.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import useProgramEditor from "../programme/useProgramEditor";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import ProgramGantt from "../programme/ProgramGantt";
import { LinksDialog, ResourceDialog } from "../programme/ProgramDialogs";
import { ResourcePanel } from "../programme/ResourcePanel";

/* eslint-disable @typescript-eslint/no-explicit-any */
const fmt = (s?: string | null) => {
  if (!s) return "-";
  const d = new Date(s);
  return isNaN(d.getTime()) ? "-" : d.toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" });
};
const todayYmd = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const field = "border bg-background px-2 text-sm";
const msg = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
const tb = "btn btn-ghost !h-8 !px-2 !py-0";                // toolbar button
const SOURCE: Record<string, string> = { upload: "Uploaded MS Project file", blank: "Built here from scratch", estimate: "Built from the estimate" };

/* ------------------------------------------------------------------ editor */

function Editor({ doc, tenderId, library, onDeleted, onBack }: { doc: ProgrammeDoc; tenderId: string; library: Estimate["library"]; onDeleted: (id: string) => void; onBack: () => void }) {
  const ed: any = useProgramEditor(doc);
  const { actions } = ed;
  const [mode, setMode] = useState<"view" | "edit">(doc.source === "blank" || doc.source === "estimate" ? "edit" : "view");
  const [tab, setTab] = useState<"gantt" | "resources">("gantt");
  const [resUid, setResUid] = useState<number | null>(null);
  const [linksUid, setLinksUid] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const editable = mode === "edit";
  const justAdded = useRef(false);
  const autoSaved = useRef(false);

  const selected = useMemo(() => ed.tasks.find((t: any) => t.uid === ed.selectedUid) || null, [ed.tasks, ed.selectedUid]);
  const resTask = useMemo(() => ed.tasks.find((t: any) => t.uid === resUid) || null, [ed.tasks, resUid]);
  const linksTask = useMemo(() => ed.tasks.find((t: any) => t.uid === linksUid) || null, [ed.tasks, linksUid]);
  const nSelected: number = ed.selectedUids.length;

  const ganttData = useMemo(() => ({ start: ed.start, finish: doc.finish, status_date: doc.status_date, working_days: ed.working_days, non_working_dates: ed.non_working_dates }),
    [ed.start, ed.working_days, ed.non_working_dates, doc.finish, doc.status_date]);
  const projectFinish = useMemo(() => {
    const fs = ed.tasks.map((t: any) => t.finish).filter(Boolean) as string[];
    return fs.length ? fs.reduce((a, b) => (a > b ? a : b)) : ed.start;
  }, [ed.tasks, ed.start]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      await api.programmeSave(tenderId, doc.id, { name: ed.name, tasks: ed.tasks, start: ed.start, finish: projectFinish, working_days: ed.working_days, non_working_dates: ed.non_working_dates });
      actions.saved();
      return true;
    } catch (e) { toast.error(msg(e)); return false; } finally { setSaving(false); }
  }, [tenderId, doc.id, ed.name, ed.tasks, ed.start, ed.working_days, ed.non_working_dates, projectFinish, actions]);

  // Programmes built from blank / an estimate are scheduled on first open: save that once.
  useEffect(() => {
    if (doc.needs_schedule && !autoSaved.current && ed.tasks.length) { autoSaved.current = true; void save(); }
  }, [doc.needs_schedule, ed.tasks.length, save]);
  useEffect(() => { if (ed.error) toast.error(ed.error); }, [ed.errorId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (justAdded.current && ed.selectedUid != null) {
      justAdded.current = false;
      const el = document.querySelector<HTMLInputElement>(`[data-name-uid="${ed.selectedUid}"]`);
      if (el) { el.focus(); el.select(); }
    }
  }, [ed.tasks, ed.selectedUid]);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (ed.dirty) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [ed.dirty]);
  useEffect(() => {
    if (!editable) return undefined;
    const onKey = (e: KeyboardEvent) => {
      const inField = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName ?? "");
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); void save(); return; }
      if (inField) return;
      if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); if (e.shiftKey) actions.redo(); else actions.undo(); }
      else if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); actions.redo(); }
      else if ((e.key === "Delete" || e.key === "Backspace") && nSelected) { e.preventDefault(); actions.removeMany(ed.selectedUids); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editable, actions, ed.selectedUids, nSelected, save]);

  const addTask = (props: any) => { justAdded.current = true; actions.insert(ed.selectedUid, props); };
  const exportXml = async () => {
    setExporting(true);
    try {
      if (ed.dirty && !(await save())) return;
      await api.programmeExportXml(tenderId, doc.id);
      toast.success("Exported. Open the .xml file in MS Project (File > Open); use Save As to keep it as .mpp.");
    } catch (e) { toast.error(msg(e)); } finally { setExporting(false); }
  };
  const leave = () => { if (!ed.dirty || window.confirm("You have unsaved changes. Leave without saving?")) onBack(); };

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button className="btn btn-ghost !h-8 !py-0" onClick={leave}><ArrowLeft size={14} aria-hidden />All programmes</button>
        <div className="min-w-[14rem]">
          {editable
            ? <input className={`${field} h-8 w-80 max-w-full text-base font-bold`} value={ed.name || ""} onChange={(e) => actions.setName(e.target.value)} data-testid="program-name" aria-label="Programme name" />
            : <h2 className="text-lg font-bold leading-tight">{ed.name}</h2>}
          <p className="mt-0.5 text-xs text-muted-foreground">
            {doc.filename ? `${doc.filename} · ` : ""}{ed.tasks.length} tasks · {fmt(ed.start)} → {fmt(projectFinish)}
            {ed.dirty && <span className="ml-2 font-semibold text-amber-fg">Unsaved changes</span>}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <div className="flex border">
            <button className={`h-8 px-3 text-xs ${tab === "gantt" ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`} onClick={() => setTab("gantt")}>Gantt</button>
            <button className={`h-8 px-3 text-xs ${tab === "resources" ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`} onClick={() => setTab("resources")} data-testid="tab-resources">Resources</button>
          </div>
          <button className="btn btn-ghost !h-8 !py-0" onClick={() => setMode(editable ? "view" : "edit")} data-testid="toggle-edit">
            {editable ? <><Eye size={14} aria-hidden />View only</> : <><Pencil size={14} aria-hidden />Edit programme</>}
          </button>
          <button className="btn btn-ghost !h-8 !py-0" onClick={exportXml} disabled={exporting} data-testid="export-xml" title="Download as MS Project XML. Open it in MS Project and Save As .mpp">
            {exporting ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Download size={14} aria-hidden />}MS Project XML
          </button>
          {editable && (
            <button className="btn btn-solid !h-8 !py-0" onClick={() => void save()} disabled={saving || !ed.dirty} data-testid="save-program">
              {saving ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Save size={14} aria-hidden />}Save
            </button>
          )}
          <button className="btn btn-ghost !h-8 !px-2 !py-0" onClick={() => onDeleted(doc.id)} title="Delete programme" aria-label="Delete programme"><Trash2 size={14} /></button>
        </div>
      </div>

      {editable && tab === "gantt" && (
        <div className="mb-2 flex flex-wrap items-center gap-1.5 border bg-card p-2 text-xs" data-testid="edit-toolbar">
          <button className={tb} onClick={actions.undo} disabled={!ed.canUndo} title="Undo (Ctrl+Z)" aria-label="Undo" data-testid="undo"><Undo2 size={14} /></button>
          <button className={tb} onClick={actions.redo} disabled={!ed.canRedo} title="Redo (Ctrl+Y)" aria-label="Redo"><Redo2 size={14} /></button>
          <span className="mx-1 h-5 w-px bg-border" />
          <button className="btn btn-solid !h-8 !px-2 !py-0" onClick={() => addTask({})} data-testid="add-task"><Plus size={14} aria-hidden />Add task</button>
          <button className={tb} onClick={() => addTask({ name: "New milestone", duration: { value: 0, unit: "D" } })} data-testid="add-milestone"><Flag size={14} aria-hidden />Milestone</button>
          <span className="mx-1 h-5 w-px bg-border" />
          <button className={tb} disabled={!selected} onClick={() => actions.outdent(ed.selectedUid)} title="Outdent (promote)" aria-label="Outdent" data-testid="outdent"><IndentDecrease size={14} /></button>
          <button className={tb} disabled={!selected} onClick={() => actions.indent(ed.selectedUid)} title="Indent (make a sub-task of the row above)" aria-label="Indent" data-testid="indent"><IndentIncrease size={14} /></button>
          <button className={tb} disabled={!selected} onClick={() => actions.move(ed.selectedUid, -1)} title="Move up" aria-label="Move up"><ArrowUp size={14} /></button>
          <button className={tb} disabled={!selected} onClick={() => actions.move(ed.selectedUid, 1)} title="Move down" aria-label="Move down"><ArrowDown size={14} /></button>
          <button className={tb} disabled={!nSelected} onClick={() => actions.removeMany(ed.selectedUids)} title="Delete selected (Del)" aria-label="Delete selected" data-testid="delete-task"><Trash2 size={14} /></button>
          <span className="mx-1 h-5 w-px bg-border" />
          <button className={tb} data-testid="link-tasks" title="Link the selected tasks, in order (finish to start)"
            onClick={() => (nSelected < 2 ? toast.info("Select two or more tasks (Ctrl/Shift + click rows) to link them in order") : actions.linkSelected())}><Link2 size={14} aria-hidden />Link</button>
          <button className={tb} disabled={!nSelected} onClick={actions.unlinkSelected} title="Remove links between the selected tasks (or all links of one task)" data-testid="unlink-tasks"><Link2Off size={14} aria-hidden />Unlink</button>
          <button className={tb} disabled={!selected} onClick={() => setLinksUid(ed.selectedUid)} data-testid="open-links">Dependencies</button>
          <span className="mx-1 h-5 w-px bg-border" />
          <button className={tb} disabled={!selected || selected.is_summary} onClick={() => setResUid(ed.selectedUid)} data-testid="open-resources">Resources</button>
          <span className="mx-1 h-5 w-px bg-border" />
          <label className="flex items-center gap-1 text-muted-foreground">Project start
            <input type="date" value={ed.projectStartYmd} onChange={(e) => e.target.value && actions.setStart(e.target.value)} className={`${field} h-8 px-1 text-xs`} data-testid="project-start" />
          </label>
          <span className="ml-auto hidden text-muted-foreground lg:inline">Drag bars to move/resize · Ctrl/Shift+click rows then Link · drag the blue dot to link · pin = fixed start</span>
        </div>
      )}

      {tab === "gantt" ? (
        <ProgramGantt data={ganttData} tasks={ed.tasks} cal={ed.cal} editable={editable} selectedUid={ed.selectedUid} selectedUids={ed.selectedUids}
          onSelect={actions.select} onEdit={actions.edit} onLink={actions.link} onOpenResources={(uid: number) => setResUid(uid)} onOpenLinks={(uid: number) => setLinksUid(uid)}
          onError={(m: string) => toast.error(m)} />
      ) : <ResourcePanel tasks={ed.tasks} cal={ed.cal} />}

      <LinksDialog open={linksUid != null} task={linksTask} tasks={ed.tasks} onClose={() => setLinksUid(null)}
        onApply={(preds) => { actions.edit(linksUid, { predecessors: preds }); setLinksUid(null); }} />
      <ResourceDialog open={resUid != null} task={resTask} library={library} onClose={() => setResUid(null)}
        onApply={(assignments) => { actions.edit(resUid, { resource_assignments: assignments, resources: assignments.map((a: any) => a.name) }); setResUid(null); }} />
    </>
  );
}

/* ------------------------------------------------------------------ page */

export function ProgrammeEditor({ tenderId, est, rev, sub }: { tenderId: string; est: Estimate; rev: number; sub?: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [list, setList] = useState<Omit<ProgrammeDoc, "tasks">[] | null>(null);
  const [doc, setDoc] = useState<ProgrammeDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [newKind, setNewKind] = useState<null | "blank" | "estimate">(null);
  const [form, setForm] = useState({ name: "", start: todayYmd() });
  const [creating, setCreating] = useState(false);
  const open = (id: string | null) => go({ name: "tender", id: tenderId, page: "gantt", rev: null, sub: id ?? undefined });

  useEffect(() => {
    let live = true;
    setLoading(true); setDoc(null);
    (sub ? api.programme(tenderId, sub).then((d) => live && setDoc(d)) : api.programmes(tenderId).then((r) => live && setList(r.programmes)))
      .catch((e) => toast.error(msg(e))).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [tenderId, sub]);

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setUploading(true);
    try { const d = await api.programmeUpload(tenderId, f); toast.success(`Loaded ${d.task_count} tasks`); open(d.id); }
    catch (err) { toast.error(msg(err)); } finally { setUploading(false); }
  };
  const remove = async (id: string) => {
    if (!window.confirm("Delete this programme? This cannot be undone.")) return;
    try { await api.programmeDelete(tenderId, id); setList((l) => (l ? l.filter((x) => x.id !== id) : l)); if (sub === id) open(null); }
    catch (e) { toast.error(msg(e)); }
  };
  const create = async () => {
    setCreating(true);
    try {
      const d = newKind === "blank" ? await api.programmeBlank(tenderId, form.name || "New programme", form.start)
        : await api.programmeFromEstimate(tenderId, rev, form.name, form.start);
      setNewKind(null); open(d.id);
    } catch (e) { toast.error(msg(e)); } finally { setCreating(false); }
  };
  const openNew = (k: "blank" | "estimate") => { setForm({ name: "", start: (k === "estimate" && est.programme?.start) || todayYmd() }); setNewKind(k); };

  if (sub) {
    if (loading) return <div className="text-sm text-muted-foreground" aria-live="polite">Loading programme…</div>;
    if (!doc) return <Empty title="Programme not found" body="It may have been deleted." />;
    return <Editor key={doc.id} doc={doc} tenderId={tenderId} library={est.library} onDeleted={remove} onBack={() => open(null)} />;
  }

  return (
    <>
      <PageHeader title="Programme Gantt" sub="Build a programme from scratch or from this estimate, or open an MS Project file to view and edit it. Export as MS Project XML: open it in MS Project and Save As .mpp."
        actions={<>
          <button className="btn btn-solid" onClick={() => openNew("blank")} data-testid="new-blank"><FilePlus2 size={14} aria-hidden />New programme</button>
          <button className="btn btn-ghost" onClick={() => openNew("estimate")} data-testid="new-from-estimate"><ClipboardList size={14} aria-hidden />From this estimate</button>
          <button className="btn btn-ghost" onClick={() => fileRef.current?.click()} disabled={uploading} data-testid="program-view-upload">
            {uploading ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Upload size={14} aria-hidden />}Open MS Project file
          </button>
        </>} />
      <input ref={fileRef} type="file" accept=".mpp,.mpx,.mpt,.xml,.planner,.pmxml,.xer" className="hidden" onChange={upload} data-testid="program-view-file" aria-label="MS Project file" />
      {loading || !list ? <div className="text-sm text-muted-foreground" aria-live="polite">Loading…</div> : list.length === 0
        ? <Empty title="No programmes yet" body="Start a new one, build one from this estimate, or open an MS Project file (.mpp or .xml)." />
        : (
          <Panel flush>
            <div className="grid-scroll">
              <table className="grid-table">
                <thead><tr><th className="min-w-[16rem]">Name</th><th className="hidden md:table-cell">Source</th><th className="text-right">Tasks</th><th className="hidden sm:table-cell">Start</th><th className="hidden sm:table-cell">Finish</th><th className="w-20" /></tr></thead>
                <tbody>
                  {list.map((v) => (
                    <tr key={v.id} className="cursor-pointer" onClick={() => open(v.id)} data-testid="program-row">
                      <td><span className="flex items-center gap-2 font-medium"><FileText size={16} className="flex-none" aria-hidden />{v.name}</span></td>
                      <td className="hidden text-muted-foreground md:table-cell">{v.filename || SOURCE[v.source] || "Programme"}{v.source === "estimate" && v.revision ? <> <Chip tone="neutral">Rev {v.revision}</Chip></> : null}</td>
                      <td className="num">{v.task_count}</td>
                      <td className="hidden text-muted-foreground sm:table-cell">{fmt(v.start)}</td>
                      <td className="hidden text-muted-foreground sm:table-cell">{fmt(v.finish)}</td>
                      <td onClick={(e) => e.stopPropagation()}><button className="btn btn-ghost !px-2 !py-1" onClick={() => void remove(v.id)} aria-label={`Delete ${v.name}`}>Delete</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      <Modal open={newKind !== null} onClose={() => setNewKind(null)} title={newKind === "estimate" ? "Programme from this estimate" : "New programme"}>
        <div data-testid="new-program-dialog" className="space-y-3">
          <p className="text-sm text-muted-foreground">{newKind === "estimate"
            ? "Sections become summary rows and priced QS items become tasks, in order. Durations come from the estimate's labour and plant hours (or the platform's programme if it is set up); the order and links are a starting point to adjust."
            : "Start with an empty programme and add tasks, links and resources."}</p>
          <label className="block"><span className="label">Programme name</span>
            <input className={`${field} mt-1 h-10 w-full`} value={form.name} placeholder={newKind === "estimate" ? "Defaults to the tender name" : "New programme"} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="new-program-name" /></label>
          <label className="block"><span className="label">Project start date</span>
            <input type="date" className={`${field} mt-1 h-10 w-full`} value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></label>
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn btn-ghost" onClick={() => setNewKind(null)}>Cancel</button>
            <button className="btn btn-solid" onClick={create} disabled={creating} data-testid="create-program">{creating && <Loader2 size={14} className="animate-spin" aria-hidden />}Create</button>
          </div>
        </div>
      </Modal>
    </>
  );
}
