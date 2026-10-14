import { useEffect, useState } from "react";
import type { DraftEdit } from "./edit";

/** True while the browser has a network connection. */
export function useOnline(): boolean {
  const [on, setOn] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  useEffect(() => {
    const up = () => setOn(true), down = () => setOn(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return on;
}

// Unsaved edit drafts are kept on this device, per tender and revision, so a lost connection, a closed tab or a flat battery loses nothing.
const key = (tender: string, rev: number) => `qsi.draft.${tender}.${rev}`;
export interface SavedDraft { edits: Record<string, DraftEdit>; savedAt: string }

export function loadDraft(tender: string, rev: number): SavedDraft | null {
  try {
    const raw = localStorage.getItem(key(tender, rev));
    if (!raw) return null;
    const d = JSON.parse(raw) as SavedDraft;
    return d && d.edits && Object.keys(d.edits).length ? d : null;
  } catch { return null; }
}
export function saveDraft(tender: string, rev: number, edits: Record<string, DraftEdit>): void {
  try {
    if (Object.keys(edits).length === 0) localStorage.removeItem(key(tender, rev));
    else localStorage.setItem(key(tender, rev), JSON.stringify({ edits, savedAt: new Date().toISOString() } satisfies SavedDraft));
  } catch { /* storage full or blocked: editing still works */ }
}
export function clearDraft(tender: string, rev: number): void {
  try { localStorage.removeItem(key(tender, rev)); } catch { /* ignore */ }
}
