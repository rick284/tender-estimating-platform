import { useState, type ReactNode } from "react";
import { BarChart3, Calculator, ClipboardList, CloudRain, FileText, FolderOpen, GitCompare, Layers, LayoutDashboard, Library, ListTree, LogOut, Menu, Package, X } from "lucide-react";
import { go, type Route } from "../lib/route";
import type { User } from "../lib/types";

export const TENDER_NAV = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "consolidated", label: "Consolidated Package", icon: Package },
  { id: "tender", label: "Tender Build-Up", icon: Calculator },
  { id: "qs", label: "QS Takeoff", icon: ListTree },
  { id: "buildup", label: "Resource Build-Up", icon: Layers },
  { id: "weather", label: "Weather Risk", icon: CloudRain },
  { id: "register", label: "Register", icon: ClipboardList },
  { id: "outputs", label: "Client Outputs", icon: FileText },
  { id: "library", label: "Rate Library", icon: Library },
  { id: "revisions", label: "Revisions", icon: GitCompare },
] as const;
export type TenderPage = (typeof TENDER_NAV)[number]["id"];
export const isTenderPage = (p: string): p is TenderPage => TENDER_NAV.some((n) => n.id === p);

function Brand() {
  return (
    <div className="leading-none">
      <div className="font-heading text-base font-black uppercase tracking-tight">Estimating Platform</div>
      <div className="label mt-1 !text-[0.625rem]">Civil &amp; commercial tenders</div>
    </div>
  );
}

const itemCls = (active: boolean) =>
  `flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm font-medium transition-colors ${active ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-muted"}`;

export function Shell({ user, route, tenderName, onLogout, children }: { user: User; route: Route; tenderName?: string; onLogout: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const inTender = route.name === "tender";
  const nav = (r: Route) => { go(r); setOpen(false); };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background px-4 lg:hidden">
        <button aria-label="Open navigation" onClick={() => setOpen(true)} className="-ml-2 p-2"><Menu size={20} /></button>
        <Brand />
      </header>
      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col overflow-y-auto border-r bg-background transition-transform lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-auto lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-16 shrink-0 items-center justify-between border-b px-4">
          <Brand />
          <button aria-label="Close navigation" onClick={() => setOpen(false)} className="p-2 lg:hidden"><X size={18} /></button>
        </div>
        <nav aria-label="Main" className="space-y-0.5 p-3">
          <button className={itemCls(route.name === "tenders")} aria-current={route.name === "tenders" ? "page" : undefined} onClick={() => nav({ name: "tenders" })}>
            <FolderOpen size={16} strokeWidth={1.75} aria-hidden /> All tenders
          </button>
        </nav>
        {inTender && route.name === "tender" && (
          <nav aria-label="This tender" className="border-t p-3">
            <div className="label mb-1 px-3 pt-1">Open tender</div>
            <div className="mb-2 truncate px-3 text-xs text-muted-foreground" title={tenderName}>{tenderName}</div>
            <div className="space-y-0.5">
              {TENDER_NAV.map(({ id, label, icon: Icon }) => (
                <button key={id} className={itemCls(route.page === id)} aria-current={route.page === id ? "page" : undefined}
                  onClick={() => nav({ name: "tender", id: route.id, page: id, rev: route.rev })}>
                  <Icon size={16} strokeWidth={1.75} aria-hidden /> {label}
                </button>
              ))}
            </div>
          </nav>
        )}
        <div className="mt-auto border-t p-4 text-xs">
          <div className="flex items-center gap-2 text-muted-foreground"><BarChart3 size={12} aria-hidden /><span className="label !tracking-wider">Workspace</span></div>
          <div className="mt-1 truncate font-medium" title={user.org_name ?? ""}>{user.org_name}</div>
          <div className="truncate text-muted-foreground" title={user.email}>{user.name} · {user.email}</div>
          <button onClick={onLogout} className="mt-3 inline-flex items-center gap-2 font-heading text-2xs font-bold uppercase tracking-wider underline underline-offset-4">
            <LogOut size={12} aria-hidden /> Sign out
          </button>
        </div>
      </aside>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
