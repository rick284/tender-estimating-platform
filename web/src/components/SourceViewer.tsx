import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";
import { api, type SheetInfo, type TakeoffSource } from "../lib/api";
import { fmtNum } from "../lib/format";
import { Modal } from "./Modal";

const ZOOMS = [1, 1.5, 2, 3];

/** Read-only drawing viewer: shows the page a number was taken from and outlines where it is written. Nothing here measures or marks up the drawing. */
export function SourceViewer({ tenderId, lineId, title, start, onClose }: { tenderId: string; lineId: string; title: string; start: number; onClose: () => void }) {
  const [sources, setSources] = useState<TakeoffSource[]>([]);
  const [idx, setIdx] = useState(start);
  const [page, setPage] = useState(0);
  const [img, setImg] = useState("");
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [zoom, setZoom] = useState(1.5);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const box = useRef<HTMLDivElement>(null);
  const src = sources[idx];

  useEffect(() => {
    api.takeoffSources(lineId).then((r) => { setSources(r.sources); const s = r.sources[start]; if (s?.viewable) setPage(s.page); }).catch((e) => setErr((e as Error).message));
  }, [lineId, start]);
  useEffect(() => { if (src?.viewable) setPage(src.page); }, [src]);
  useEffect(() => {
    if (!src?.file_id) return;
    api.takeoffSheets(tenderId, src.file_id).then((r) => setSheets(r.pages)).catch(() => setSheets([]));
  }, [tenderId, src?.file_id]);
  useEffect(() => {
    if (!src?.viewable || !page) return;
    let url = ""; let live = true;
    setLoading(true); setErr("");
    api.pageImageUrl(tenderId, src.file_id, page).then((u) => { url = u; if (live) setImg(u); else URL.revokeObjectURL(u); }).catch((e) => live && setErr((e as Error).message)).finally(() => live && setLoading(false));
    return () => { live = false; if (url) URL.revokeObjectURL(url); };
  }, [tenderId, src?.file_id, src?.viewable, page]);
  // bring the outlined text into the middle of the view (after the image has its size, and again when the zoom changes)
  const centre = () => {
    const c = box.current; const r = src?.rects[0];
    if (!c || !r || page !== src?.page) return;
    const inner = c.firstElementChild as HTMLElement | null;
    if (!inner) return;
    c.scrollTo({ left: ((r.x0 + r.x1) / 2) * inner.offsetWidth - c.clientWidth / 2, top: ((r.y0 + r.y1) / 2) * inner.offsetHeight - c.clientHeight / 2 });
  };
  useEffect(() => { if (img) centre(); }, [zoom]); // eslint-disable-line react-hooks/exhaustive-deps

  const sheet = sheets.find((s) => s.page === page);
  const onPage = src && page === src.page;
  return (
    <Modal open onClose={onClose} title={`Source: ${title}`} huge>
      {err && <div role="alert" className="mb-3 border border-red-line bg-red-bg px-4 py-3 text-sm text-red-fg">{err}</div>}
      <div className="mb-3 flex flex-wrap gap-2">
        {sources.map((s, i) => (
          <button key={i} onClick={() => setIdx(i)} aria-pressed={i === idx} className={`border px-3 py-1.5 text-left text-sm ${i === idx ? "border-primary bg-muted" : "bg-background"}`}>
            <span className="num font-semibold">{fmtNum(s.value)} {s.unit}</span> <span className="text-muted-foreground">{s.label}</span>
          </button>
        ))}
      </div>
      {src && (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{src.file || "Document"}</span>
            <span className="text-muted-foreground">sheet {src.sheet || "?"} · cited page {src.page}</span>
            <span className="ml-auto flex items-center gap-1">
              <button aria-label="Previous page" className="border p-1.5 disabled:opacity-40" disabled={!src.viewable || page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button>
              <span className="num px-2" aria-live="polite">Page {page || "-"} of {src.pages ?? "-"}{sheet?.code ? ` · ${sheet.code}${sheet.title ? ` ${sheet.title}` : ""}` : ""}</span>
              <button aria-label="Next page" className="border p-1.5 disabled:opacity-40" disabled={!src.viewable || page >= (src.pages ?? 0)} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button>
              <button aria-label="Zoom out" className="ml-2 border p-1.5 disabled:opacity-40" disabled={zoom <= ZOOMS[0]} onClick={() => setZoom(ZOOMS[Math.max(0, ZOOMS.indexOf(zoom) - 1)])}><Minus size={16} /></button>
              <span className="num w-12 text-center">{Math.round(zoom * 100)}%</span>
              <button aria-label="Zoom in" className="border p-1.5 disabled:opacity-40" disabled={zoom >= ZOOMS[ZOOMS.length - 1]} onClick={() => setZoom(ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(zoom) + 1)])}><Plus size={16} /></button>
            </span>
          </div>
          {!src.viewable && <p className="border bg-muted/50 px-4 py-3 text-sm">This source can't be shown as a page (it isn't a PDF drawing, or Drive could not be reached). Its text is listed on the takeoff line.</p>}
          {src.viewable && onPage && src.how === "none" && src.source !== "scaled" && src.source !== "counted" && <p className="mb-2 text-sm text-red-fg">The platform could not find this text on the page, so nothing is outlined. Check the page yourself.</p>}
          {src.viewable && onPage && (src.source === "scaled" || src.source === "counted") && <p className="mb-2 text-sm text-muted-foreground">This number was {src.source} by the AI, so there is no written text to outline. Check it on this page{src.quote ? "" : " against the AI's note on the line"}.</p>}
          {src.viewable && onPage && src.how === "number" && <p className="mb-2 text-sm text-muted-foreground">Outlined: the number {fmtNum(src.value)} as written on the page (the exact quote wasn't found word for word).</p>}
          {src.viewable && onPage && src.how === "quote" && <p className="mb-2 text-sm text-muted-foreground">Outlined: the quoted text on the page.</p>}
          {src.viewable && (
            <div ref={box} className="max-h-[68vh] overflow-auto border bg-muted/30" data-testid="viewer-scroll">
              {loading && !img && <div className="p-8 text-sm text-muted-foreground">Loading the drawing from Drive…</div>}
              {img && (
                <div className="relative" style={{ width: `${zoom * 100}%` }}>
                  <img src={img} alt={`${src.file}, page ${page}`} className="block w-full" draggable={false} onLoad={centre} />
                  {onPage && src.rects.map((r, i) => (
                    <div key={i} data-testid="source-highlight" aria-label="Source of the number"
                      className="pointer-events-none absolute border-2 border-red-600 bg-red-500/10 shadow-[0_0_0_3px_rgba(255,255,255,0.8)]"
                      style={{ left: `${r.x0 * 100}%`, top: `${r.y0 * 100}%`, width: `${(r.x1 - r.x0) * 100}%`, height: `${(r.y1 - r.y0) * 100}%` }} />
                  ))}
                </div>
              )}
            </div>
          )}
          {src.quote && <p className="mt-2 text-sm">“{src.quote}”</p>}
        </>
      )}
    </Modal>
  );
}
