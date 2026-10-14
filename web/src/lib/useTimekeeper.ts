import { useEffect, useRef } from "react";
import { api } from "./api";

const ACTIVE_WINDOW = 120_000;      // counts as working while there was keyboard, mouse, touch or scroll input in the last 2 minutes
const NEW_SESSION_AFTER = 600_000;  // no input for 10 minutes ends the session; the next input starts a new one
const PING_EVERY = 30_000;
const sid = () => { const a = new Uint8Array(9); crypto.getRandomValues(a); return "S" + Array.from(a, (b) => b.toString(36).padStart(2, "0")).join(""); };

/** Time-keeping while a tender is open: sends a small heartbeat with the seconds of real activity since the last one. The server keeps the totals;
 *  what was done is read back from the platform's own records, so nothing here records content. Errors are silent: timing must never get in the way of work. */
export function useTimekeeper(tenderId: string, page: string, draftEdits: number) {
  const now = useRef({ page, draftEdits });
  now.current = { page, draftEdits };
  useEffect(() => {
    let id = sid(), pending = 0, lastInput = Date.now(), lastTick = Date.now(), ended = false, started = false;
    const send = (end: boolean) => {
      started = true;
      const sec = Math.round(pending);
      pending -= sec;
      const body = { session_id: id, tender_id: tenderId, page: now.current.page, active_seconds: sec, draft_edits: now.current.draftEdits, end };
      api.timePing(body).then((ok) => { if (!ok) pending += sec; }).catch(() => { pending += sec; });
    };
    const input = () => {
      const t = Date.now();
      if (ended || t - lastInput > NEW_SESSION_AFTER) { if (!ended) send(true); id = sid(); pending = 0; ended = false; lastTick = t; send(false); }
      lastInput = t;
    };
    const tick = setInterval(() => {
      const t = Date.now();
      const dt = Math.min(t - lastTick, 10_000) / 1000;
      lastTick = t;
      if (!document.hidden && t - lastInput < ACTIVE_WINDOW) pending += dt;
    }, 5000);
    const beat = setInterval(() => {
      if (ended) return;
      if (Date.now() - lastInput > NEW_SESSION_AFTER) { send(true); ended = true; return; }
      send(false);
    }, PING_EVERY);
    const hide = () => { if (document.hidden && !ended) send(false); };
    const leave = () => { if (started && !ended) send(true); };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"] as const;
    events.forEach((e) => window.addEventListener(e, input, { passive: true }));
    document.addEventListener("visibilitychange", hide);
    window.addEventListener("pagehide", leave);
    const first = setTimeout(() => send(false), 1500);            // the session starts when the tender opens (a page that is only passed through leaves no trace)
    return () => {
      clearTimeout(first); clearInterval(tick); clearInterval(beat);
      events.forEach((e) => window.removeEventListener(e, input));
      document.removeEventListener("visibilitychange", hide);
      window.removeEventListener("pagehide", leave);
      leave();
    };
  }, [tenderId]);
}
