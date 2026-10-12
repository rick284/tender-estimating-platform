import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

/** Native <dialog>: focus is trapped, Esc closes, background is inert. */
export function Modal({ open, onClose, title, children, wide = false, huge = false }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean; huge?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}
      className={`m-auto ${huge ? "w-[min(96rem,calc(100vw-1rem))]" : wide ? "w-[min(46rem,calc(100vw-2rem))]" : "w-[min(32rem,calc(100vw-2rem))]"} border border-primary bg-background p-0 text-foreground backdrop:bg-black/50`}>
      {open && (
        <div>
          <div className="flex items-center justify-between border-b px-5 py-3">
            <h2 className="text-sm tracking-wider">{title}</h2>
            <button aria-label="Close" onClick={onClose} className="-mr-2 p-2"><X size={16} /></button>
          </div>
          <div className="p-5">{children}</div>
        </div>
      )}
    </dialog>
  );
}
