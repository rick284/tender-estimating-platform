import { useState, type FormEvent } from "react";
import type { Estimate, RegisterItem, RegisterKind } from "../lib/types";
import { EditField } from "../components/EditCells";
import { Modal } from "../components/Modal";
import { Chip, Empty, PageHeader, Panel, Stat } from "../components/ui";
import { useEdit } from "../lib/edit";

const TABS: { kind: RegisterKind; label: string; one: string; hint: string }[] = [
  { kind: "rfi", label: "RFIs", one: "RFI", hint: "A question or clarification you need answered, or a pricing qualification." },
  { kind: "risk", label: "Risks", one: "risk", hint: "A material uncertainty, how the price treats it and what happens outside the baseline." },
  { kind: "assumption", label: "Assumptions", one: "assumption", hint: "Something the price assumes to be true." },
  { kind: "exclusion", label: "Exclusions", one: "exclusion", hint: "Work that is excluded or by others." },
  { kind: "inclusion", label: "Inclusions", one: "inclusion", hint: "Work the price specifically includes." },
  { kind: "document", label: "Documents", one: "document", hint: "A drawing, specification, report or message the price is based on." },
];
const rid = () => { const a = new Uint8Array(5); crypto.getRandomValues(a); return "R-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8); };
const ragTone = (r: string) => (r === "RED" ? "red" : r === "AMBER" ? "amber" : r === "GREEN" ? "green" : "neutral") as "red" | "amber" | "green" | "neutral";
const RAGS = [{ value: "", label: "—" }, { value: "RED", label: "RED" }, { value: "AMBER", label: "AMBER" }, { value: "GREEN", label: "GREEN" }];
const STATUS = [{ value: "OPEN", label: "OPEN" }, { value: "CLOSED", label: "CLOSED" }];

function AddDialog({ open, onClose, kind, onAdd }: { open: boolean; onClose: () => void; kind: RegisterKind; onAdd: (payload: Record<string, unknown>) => void }) {
  const tab = TABS.find((t) => t.kind === kind)!;
  const [f, setF] = useState({ ref: "", title: "", detail: "", rag: "", action: "", owner: "" });
  const [err, setErr] = useState("");
  const field = "mt-1 w-full border bg-background px-3 text-sm focus:border-primary";
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim() && !f.detail.trim()) return setErr(`Describe the ${tab.one}: it needs a title or some detail.`);
    onAdd({ kind, ...f });
    setF({ ref: "", title: "", detail: "", rag: "", action: "", owner: "" }); setErr(""); onClose();
  };
  return (
    <Modal open={open} onClose={onClose} title={`Add ${tab.one}`}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <p className="text-sm text-muted-foreground">{tab.hint}</p>
        <label className="block"><span className="label">{kind === "document" ? "Source" : "Title"}</span><input className={`${field} h-10`} value={f.title} onChange={set("title")} maxLength={300} autoFocus /></label>
        <label className="block"><span className="label">{kind === "document" ? "How the estimate uses it" : kind === "risk" ? "How the price treats it" : "Detail"}</span><textarea className={`${field} py-2`} rows={4} value={f.detail} onChange={set("detail")} maxLength={3000} /></label>
        {kind === "risk" && <label className="block"><span className="label">Outside the baseline / closeout</span><textarea className={`${field} py-2`} rows={2} value={f.action} onChange={set("action")} maxLength={3000} /></label>}
        <div className="grid grid-cols-2 gap-3">
          <label className="block"><span className="label">{kind === "document" ? "Revision / date" : "Reference (optional)"}</span><input className={`${field} h-10`} value={f.ref} onChange={set("ref")} maxLength={40} placeholder={kind === "document" ? "e.g. Rev B, 11-Sep-2026" : "next number is filled in"} /></label>
          {(kind === "rfi" || kind === "risk") && <label className="block"><span className="label">Rating</span><select className={`${field} h-10`} value={f.rag} onChange={set("rag")}>{RAGS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>}
        </div>
        {kind === "risk" && <label className="block"><span className="label">Owner</span><input className={`${field} h-10`} value={f.owner} onChange={set("owner")} maxLength={80} /></label>}
        {err && <div role="alert" className="border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button><button className="btn btn-solid">Add {tab.one}</button></div>
      </form>
    </Modal>
  );
}

export function Register({ est }: { est: Estimate }) {
  const { editing, add, remove } = useEdit();
  const [kind, setKind] = useState<RegisterKind>("rfi");
  const [adding, setAdding] = useState(false);
  const [hideClosed, setHideClosed] = useState(false);
  const items = est.register ?? [];
  const sum = est.register_summary ?? { rfis: 0, open_rfis: 0, open_red_rfis: 0, red_risks: 0 };
  const count = (k: RegisterKind) => items.filter((x) => x.kind === k).length;
  let rows = items.filter((x) => x.kind === kind);
  if (kind === "rfi" && hideClosed) rows = rows.filter((x) => x.status !== "CLOSED");
  const tab = TABS.find((t) => t.kind === kind)!;
  const E = (it: RegisterItem, f: keyof RegisterItem, label: string, o: { kind?: "text" | "textarea" | "select"; options?: { value: string; label: string }[]; width?: string } = {}) => (
    <EditField target="register" id={it.id} field={f} value={String(it[f] ?? "")} label={`${it.ref} ${label}`} kind={o.kind} options={o.options} width={o.width ?? "w-full"}
      display={o.kind === "select" && f === "rag" ? (it.rag ? <Chip tone={ragTone(it.rag)}>{it.rag}</Chip> : "—") : (String(it[f] ?? "") || "—")} />
  );
  const del = (it: RegisterItem) => editing && <button className="btn btn-ghost !px-2 !py-1" aria-label={`Delete ${it.ref}`} onClick={() => { if (window.confirm(`Delete ${it.ref}? You can undo this before saving.`)) remove("register", it.id); }}>Delete</button>;
  const wrap = "whitespace-pre-line text-sm leading-snug";

  return (
    <>
      <PageHeader title="Tender register" sub="The record behind the price: what it is based on, what it assumes, what it excludes, and what is still open. It feeds the tender report."
        actions={editing ? <button className="btn btn-solid" onClick={() => setAdding(true)}>Add {tab.one}</button> : undefined} />
      <Panel className="mb-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
          <Stat label="Open RFIs" value={sum.open_rfis} sub={`${sum.rfis} in total`} />
          <Stat label="Open RED RFIs" value={sum.open_red_rfis} sub="decision blockers" />
          <Stat label="RED risks" value={sum.red_risks} />
          <Stat label="Documents" value={count("document")} sub={`${count("assumption")} assumptions · ${count("exclusion")} exclusions`} />
        </div>
      </Panel>
      <div role="tablist" aria-label="Register section" className="mb-3 flex flex-wrap border">
        {TABS.map((t) => (
          <button key={t.kind} role="tab" aria-selected={kind === t.kind} onClick={() => setKind(t.kind)}
            className={`px-3 py-2 font-heading text-2xs font-bold uppercase tracking-wider ${kind === t.kind ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}>
            {t.label} <span className="ml-1 font-mono font-normal opacity-70">{count(t.kind)}</span>
          </button>
        ))}
        {kind === "rfi" && <label className="ml-auto flex items-center gap-2 px-3 text-sm"><input type="checkbox" className="h-4 w-4 accent-black" checked={hideClosed} onChange={(e) => setHideClosed(e.target.checked)} /> Hide closed</label>}
      </div>
      {rows.length === 0 ? <Empty title={`No ${tab.label.toLowerCase()} yet`} body={editing ? `Use Add ${tab.one} to record one. ${tab.hint}` : `${tab.hint} Press Edit to add one.`} /> : (
        <Panel flush>
          <div className="grid-scroll">
            <table className="grid-table min-w-[60rem]">
              {kind === "rfi" && <>
                <thead><tr><th className="w-24">Ref</th><th className="min-w-[14rem]">Item</th><th className="min-w-[18rem]">Detail</th><th className="w-28">Status</th><th className="w-28">Rating</th>{editing && <th />}</tr></thead>
                <tbody>{rows.map((it) => <tr key={it.id}><td className="font-mono text-xs">{E(it, "ref", "reference", { width: "w-20" })}</td><td className="font-medium">{E(it, "title", "title")}</td>
                  <td className={wrap}>{E(it, "detail", "detail", { kind: "textarea" })}</td><td>{E(it, "status", "status", { kind: "select", options: STATUS, width: "w-24" })}</td>
                  <td>{E(it, "rag", "rating", { kind: "select", options: RAGS, width: "w-24" })}</td>{editing && <td>{del(it)}</td>}</tr>)}</tbody></>}
              {kind === "risk" && <>
                <thead><tr><th className="w-20">Ref</th><th className="min-w-[13rem]">Risk</th><th className="w-20">Likelihood</th><th className="w-20">Impact</th><th>Treatment in the price</th><th>Outside baseline / closeout</th><th className="w-28">Owner</th><th className="w-24">Rating</th>{editing && <th />}</tr></thead>
                <tbody>{rows.map((it) => <tr key={it.id}><td className="font-mono text-xs">{E(it, "ref", "reference", { width: "w-16" })}</td><td className="font-medium">{E(it, "title", "title")}</td><td>{E(it, "likelihood", "likelihood", { width: "w-20" })}</td>
                  <td>{E(it, "impact", "impact", { width: "w-20" })}</td><td className={wrap}>{E(it, "detail", "treatment", { kind: "textarea" })}</td><td className={wrap}>{E(it, "action", "closeout", { kind: "textarea" })}</td>
                  <td>{E(it, "owner", "owner", { width: "w-24" })}</td><td>{E(it, "rag", "rating", { kind: "select", options: RAGS, width: "w-24" })}</td>{editing && <td>{del(it)}</td>}</tr>)}</tbody></>}
              {(kind === "assumption" || kind === "exclusion" || kind === "inclusion") && <>
                <thead><tr><th className="w-24">Ref</th><th className="w-64">Summary</th><th className="min-w-[18rem]">Detail</th>{editing && <th />}</tr></thead>
                <tbody>{rows.map((it) => <tr key={it.id}><td className="font-mono text-xs">{E(it, "ref", "reference", { width: "w-20" })}</td><td className="font-medium">{E(it, "title", "summary", { kind: "textarea" })}</td>
                  <td className={wrap}>{E(it, "detail", "detail", { kind: "textarea" })}</td>{editing && <td>{del(it)}</td>}</tr>)}</tbody></>}
              {kind === "document" && <>
                <thead><tr><th className="w-64">Source</th><th className="w-56">Revision / date</th><th>How the estimate uses it</th><th className="w-28">Status</th>{editing && <th />}</tr></thead>
                <tbody>{rows.map((it) => <tr key={it.id}><td className="font-medium">{E(it, "title", "source")}</td><td className={wrap}>{E(it, "ref", "revision", { kind: "textarea" })}</td>
                  <td className={wrap}>{E(it, "detail", "use", { kind: "textarea" })}</td><td>{E(it, "status", "status", { width: "w-24" })}</td>{editing && <td>{del(it)}</td>}</tr>)}</tbody></>}
            </table>
          </div>
        </Panel>
      )}
      <AddDialog key={kind} open={adding} onClose={() => setAdding(false)} kind={kind} onAdd={(p) => add("register", rid(), p)} />
    </>
  );
}
