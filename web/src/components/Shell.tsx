import { useState, type ReactNode } from "react";
import { BarChart3, Calculator, CloudRain, Layers, LayoutDashboard, Library, ListTree, Menu, Package, X } from "lucide-react";
import type { Estimate } from "../lib/types";
import { Chip } from "./ui";

export const NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "consolidated", label: "Consolidated Package", icon: Package },
  { id: "tender", label: "Tender Build-Up", icon: Calculator },
  { id: "qs", label: "QS Takeoff", icon: ListTree },
  { id: "buildup", label: "Resource Build-Up", icon: Layers },
  { id: "weather", label: "Weather Risk", icon: CloudRain },
  { id: "library", label: "Rate Library", icon: Library },
] as const;
export type PageId = (typeof NAV)[number]["id"];

function Brand() {
  return (
    <div className="leading-none">
      <div className="font-heading text-base font-black uppercase tracking-tight">Estimating Platform</div>
      <div className="label mt-1 !text-[0.625rem]">Civil &amp; commercial tenders</div>
    </div>
  );
}

function NavList({ page, onGo }: { page: PageId; onGo: (p: PageId) => void }) {
  return (
    <nav aria-label="Estimate sections" className="space-y-0.5 p-3">
      {NAV.map(({ id, label, icon: Icon }) => {
        const active = id === page;
        return (
          <button
            key={id}
            onClick={() => onGo(id)}
            aria-current={active ? "page" : undefined}
            className={`flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm font-medium transition-colors ${active ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted"}`}
          >
            <Icon size={16} strokeWidth={1.75} aria-hidden />
            {label}
          </button>
        );
      })}
    </nav>
  );
}

export function Shell({ est, page, onGo, onReset, children }: { est: Estimate; page: PageId; onGo: (p: PageId) => void; onReset: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const rev = (est.meta.snapshot || "").split(" ")[0] || "";
  const hold = /HOLD/i.test(est.controls.cover_release || "");
  const go = (p: PageId) => { onGo(p); setOpen(false); window.scrollTo(0, 0); };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background px-4 lg:hidden">
        <button aria-label="Open navigation" onClick={() => setOpen(true)} className="-ml-2 p-2"><Menu size={20} /></button>
        <Brand />
      </header>
      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 overflow-y-auto border-r bg-background transition-transform lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-auto lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-16 items-center justify-between border-b px-4">
          <Brand />
          <button aria-label="Close navigation" onClick={() => setOpen(false)} className="p-2 lg:hidden"><X size={18} /></button>
        </div>
        <NavList page={page} onGo={go} />
        <div className="mt-2 border-t p-4 text-xs text-muted-foreground">
          <div className="label mb-1">Source</div>
          <div className="break-words">{est.meta.project}</div>
          <button onClick={onReset} className="mt-3 inline-flex items-center gap-2 font-heading text-2xs font-bold uppercase tracking-wider text-foreground underline underline-offset-4">
            <BarChart3 size={12} /> Load another workbook
          </button>
        </div>
      </aside>
      <div className="min-w-0">
        <div className="border-b bg-background">
          <div className="mx-auto flex max-w-[88rem] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
            <div className="min-w-0 flex-1">
              <div className="label">Project</div>
              <div className="truncate font-heading text-sm font-bold uppercase" title={est.meta.project}>{est.meta.project}</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {rev && <Chip tone="neutral">{rev}</Chip>}
              {est.controls.cover_release && <Chip tone={hold ? "red" : "green"} title="Release status shown in the workbook cover">{est.controls.cover_release}</Chip>}
              <Chip tone={est.reconciled ? "green" : "red"} title="Every figure is recomputed by the platform and compared with the workbook">
                {est.reconciled ? "Reconciled to workbook" : "Differs from workbook"}
              </Chip>
            </div>
          </div>
        </div>
        <main className="mx-auto max-w-[88rem] px-4 py-6 sm:px-6 sm:py-8">{children}</main>
      </div>
    </div>
  );
}
