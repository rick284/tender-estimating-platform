import { createContext, useContext } from "react";
import type { Edit } from "./types";

/** An edit as typed by the user. `scale` marks percentage inputs (typed 10 = 0.10 sent to the engine). */
export interface DraftEdit extends Edit { scale?: number; original: string }
export interface EditCtx {
  editing: boolean;
  edits: Record<string, DraftEdit>;
  set: (e: DraftEdit) => void;
  reset: (target: string, key: string, field: string) => void;
}
const Ctx = createContext<EditCtx>({ editing: false, edits: {}, set: () => {}, reset: () => {} });
export const EditProvider = Ctx.Provider;
export const useEdit = () => useContext(Ctx);
export const editKey = (t: string, k: string, f: string) => `${t}|${k}|${f}`;

/** Convert what the user typed into the value the engine expects. Unparseable text is passed through so the engine rejects it. */
export function toApi(e: DraftEdit): Edit {
  let v = e.value.trim();
  if (e.scale && v !== "" && Number.isFinite(Number(v))) v = String(Number((Number(v) / e.scale).toFixed(8)));
  return { target: e.target, key: e.key, field: e.field, value: v };
}
export function fromApiNumber(v: number | null | undefined, scale = 1): string {
  if (v === null || v === undefined) return "";
  return String(Number((v * scale).toFixed(6)));
}
