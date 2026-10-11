import { useRef, useState } from "react";
import { FileSpreadsheet, Upload } from "lucide-react";

export function ImportScreen({ onFile, onDemo, busy, error, demoAvailable }: { onFile: (f: File) => void; onDemo: () => void; busy: boolean; error: string; demoAvailable: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        <div className="mb-8">
          <div className="font-heading text-2xl font-black uppercase tracking-tight">Estimating Platform</div>
          <div className="label mt-1">Civil &amp; commercial tenders</div>
        </div>
        <h1 className="text-xl">Open an estimate</h1>
        <p className="mt-2 text-sm text-muted-foreground">Upload a Master Estimate Workbook (.xlsx). The platform recalculates every figure from its quantities, productivities, rates and commercial settings, then shows you the result and whether it agrees with the workbook.</p>
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }}
          className={`mt-6 border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-primary bg-muted" : ""}`}
        >
          <FileSpreadsheet className="mx-auto mb-3 text-muted-foreground" size={28} strokeWidth={1.5} aria-hidden />
          <div className="text-sm">Drag a workbook here, or</div>
          <button className="btn btn-solid mt-3" disabled={busy} onClick={() => ref.current?.click()}>
            <Upload size={14} aria-hidden /> {busy ? "Calculating…" : "Choose file"}
          </button>
          <input ref={ref} type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
        </div>
        {error && <div role="alert" className="mt-4 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{error}</div>}
        {demoAvailable && <button className="btn btn-ghost mt-4" disabled={busy} onClick={onDemo}>Open the demo workbook</button>}
        <p className="mt-8 text-xs text-muted-foreground">The file is processed in memory to produce this view and is not stored.</p>
      </div>
    </div>
  );
}
