import { useEffect, useState } from "react";
import { X } from "lucide-react";

type Kind = "error" | "success" | "info";
interface Item { id: number; kind: Kind; text: string }
let items: Item[] = [];
let n = 0;
const subs = new Set<(i: Item[]) => void>();
const emit = () => subs.forEach((f) => f(items));
const push = (kind: Kind, text: string) => {
  const id = ++n;
  items = [...items, { id, kind, text }].slice(-4);
  emit();
  setTimeout(() => dismiss(id), kind === "error" ? 9000 : 4500);
};
const dismiss = (id: number) => { items = items.filter((i) => i.id !== id); emit(); };

/** Small messages that appear bottom-right and fade by themselves. */
export const toast = {
  error: (t: string) => push("error", t),
  success: (t: string) => push("success", t),
  info: (t: string) => push("info", t),
};

export function Toaster() {
  const [list, setList] = useState<Item[]>(items);
  useEffect(() => { subs.add(setList); return () => { subs.delete(setList); }; }, []);
  return (
    <div className="no-print pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      {list.map((i) => (
        <div key={i.id} role={i.kind === "error" ? "alert" : "status"}
          className={`pointer-events-auto flex items-start gap-3 border px-4 py-3 text-sm shadow-lg ${i.kind === "error" ? "border-red-line bg-red-bg text-red-fg" : i.kind === "success" ? "border-green-line bg-green-bg text-green-fg" : "border-primary bg-background text-foreground"}`}>
          <span className="flex-1">{i.text}</span>
          <button aria-label="Dismiss" onClick={() => dismiss(i.id)} className="-mr-1 mt-0.5"><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}
