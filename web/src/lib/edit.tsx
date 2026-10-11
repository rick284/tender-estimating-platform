import { createContext, useContext } from "react";
import type { Edit } from "./types";

/** An edit as held in the UI. Value edits carry what the user typed (`scale` marks percentage inputs: typed 10 = 0.10).
 *  Structural edits (`op`) add or delete a thing and carry their details in `payload`. */
export interface DraftEdit {
  target: string; key: string; field: string; value: string; scale?: number; original: string;
  op?: "add" | "delete"; payload?: Record<string, unknown>;
}
export interface EditCtx {
  editing: boolean;
  edits: Record<string, DraftEdit>;
  set: (e: DraftEdit) => void;
  reset: (target: string, key: string, field: string) => void;
  add: (target: string, key: string, payload: Record<string, unknown>) => void;
  remove: (target: string, key: string) => void;
  undoKey: (k: string) => void;
}
const noop = () => {};
const Ctx = createContext<EditCtx>({ editing: false, edits: {}, set: noop, reset: noop, add: noop, remove: noop, undoKey: noop });
export const EditProvider = Ctx.Provider;
export const useEdit = () => useContext(Ctx);
export const editKey = (t: string, k: string, f: string) => `${t}|${k}|${f}`;
export const opKey = (t: string, k: string, op: "add" | "delete") => `${t}|${k}|@${op}`;

/** What to send to the engine. Unparseable text is passed through so the engine rejects it with a plain message. */
export function toApi(e: DraftEdit): Edit {
  if (e.op) return { target: e.target, key: e.key, op: e.op, value: e.payload ?? null };
  let v = e.value.trim();
  if (e.scale && v !== "" && Number.isFinite(Number(v))) v = String(Number((Number(v) / e.scale).toFixed(8)));
  return { target: e.target, key: e.key, field: e.field, value: v };
}
export function fromApiNumber(v: number | null | undefined, scale = 1): string {
  if (v === null || v === undefined) return "";
  return String(Number((v * scale).toFixed(6)));
}
export function newUid(): string {
  const a = new Uint8Array(5); crypto.getRandomValues(a);
  return "N-" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join("").slice(0, 8);
}
