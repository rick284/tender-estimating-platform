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
