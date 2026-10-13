import type { ReactNode } from "react";
import { editKey, fromApiNumber, useEdit } from "../lib/edit";

const base = "h-7 border bg-background px-2 text-right font-mono text-[13px] focus:border-primary";

/** Shows `display` normally; an input while editing. Changed values are highlighted and keep their original on hover. */
export function EditNum({ target, id, field, original, display, scale = 1, width = "w-24", label, placeholder, dp }: {
  target: string; id: string; field: string; original: number | null | undefined; display: ReactNode;
  scale?: number; width?: string; label: string; placeholder?: string; dp?: number;
}) {
  const { editing, edits, set, reset } = useEdit();
  if (!editing) return <>{display}</>;
  const k = editKey(target, id, field);
  const orig = fromApiNumber(original, scale);
  const e = edits[k];
  // dp only rounds what is SHOWN (e.g. cents); change detection still uses the full-precision original
  const initial = dp !== undefined && original !== null && original !== undefined ? String(Number((original * scale).toFixed(dp))) : orig;
  const value = e ? e.value : initial;
  const changed = !!e && Number(e.value || NaN) !== Number(orig || NaN) && !(e.value === "" && orig === "");
  return (
    <input
      aria-label={label} title={changed ? `Was ${orig === "" ? "blank" : orig}` : undefined} inputMode="decimal" placeholder={placeholder}
      value={value} onClick={(ev) => ev.stopPropagation()}
      onChange={(ev) => {
        const v = ev.target.value;
        if (v === orig) reset(target, id, field);
        else set({ target, key: id, field, value: v, scale: scale === 1 ? undefined : scale, original: orig });
      }}
      className={`${base} ${width} ${changed ? "border-amber-line bg-amber-bg" : ""}`}
    />
  );
}

export function EditCheck({ target, id, field, original, label, display }: {
  target: string; id: string; field: string; original: boolean; label: string; display?: ReactNode;
}) {
  const { editing, edits, set, reset } = useEdit();
  if (!editing) return <>{display ?? (original ? "Yes" : "No")}</>;
  const k = editKey(target, id, field);
  const e = edits[k];
  const checked = e ? e.value === "Yes" : original;
  return (
    <input type="checkbox" aria-label={label} checked={checked} onClick={(ev) => ev.stopPropagation()}
      className={`h-4 w-4 accent-black ${e ? "outline outline-2 outline-amber-line" : ""}`}
      onChange={(ev) => {
        const next = ev.target.checked;
        if (next === original) reset(target, id, field);
        else set({ target, key: id, field, value: next ? "Yes" : "No", original: original ? "Yes" : "No" });
      }} />
  );
}

const field = "h-8 border bg-background px-2 text-sm focus:border-primary";

/** Text / number / date / select input for settings that aren't plain money amounts. `value` is what is shown now
 *  (including any pending edit); the first value seen is remembered as the original so typing it back clears the edit. */
export function EditField({ target, id, field: f, value, display, kind = "text", options, label, width = "w-36", placeholder, rows = 3 }: {
  target: string; id: string; field: string; value: string; display?: ReactNode; kind?: "text" | "number" | "date" | "select" | "textarea";
  options?: { value: string; label: string }[]; label: string; width?: string; placeholder?: string; rows?: number;
}) {
  const { editing, edits, set, reset } = useEdit();
  if (!editing) return <>{display ?? (value === "" ? "—" : value)}</>;
  const k = editKey(target, id, f);
  const e = edits[k];
  const original = e ? e.original : value;
  const shown = e ? e.value : value;
  const change = (v: string) => (v === original ? reset(target, id, f) : set({ target, key: id, field: f, value: v, original }));
  const cls = `${field} ${width} ${kind === "number" ? "text-right font-mono" : ""} ${e ? "border-amber-line bg-amber-bg" : ""}`;
  if (kind === "select") {
    return (
      <select aria-label={label} value={shown} onClick={(ev) => ev.stopPropagation()} onChange={(ev) => change(ev.target.value)} className={cls}>
        {options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  }
  if (kind === "textarea") {
    return (
      <textarea aria-label={label} rows={rows} placeholder={placeholder} title={e ? `Was ${original === "" ? "blank" : original}` : undefined} value={shown}
        onClick={(ev) => ev.stopPropagation()} onChange={(ev) => change(ev.target.value)}
        className={`w-full border bg-background px-2 py-1 text-sm focus:border-primary ${e ? "border-amber-line bg-amber-bg" : ""}`} />
    );
  }
  return (
    <input aria-label={label} type={kind === "date" ? "date" : "text"} inputMode={kind === "number" ? "decimal" : undefined} placeholder={placeholder}
      title={e ? `Was ${original === "" ? "blank" : original}` : undefined} value={shown} onClick={(ev) => ev.stopPropagation()}
      onChange={(ev) => change(ev.target.value)} className={cls} />
  );
}

/** Yes/No checkbox for a setting. */
export function EditToggle({ target, id, field: f, value, label, display }: {
  target: string; id: string; field: string; value: boolean; label: string; display?: ReactNode;
}) {
  const { editing, edits, set, reset } = useEdit();
  if (!editing) return <>{display ?? (value ? "Yes" : "No")}</>;
  const k = editKey(target, id, f);
  const e = edits[k];
  const original = e ? e.original === "Yes" : value;
  const checked = e ? e.value === "Yes" : value;
  return (
    <input type="checkbox" aria-label={label} checked={checked} onClick={(ev) => ev.stopPropagation()}
      className={`h-4 w-4 accent-black ${e ? "outline outline-2 outline-amber-line" : ""}`}
      onChange={(ev) => (ev.target.checked === original ? reset(target, id, f) : set({ target, key: id, field: f, value: ev.target.checked ? "Yes" : "No", original: original ? "Yes" : "No" }))} />
  );
}
