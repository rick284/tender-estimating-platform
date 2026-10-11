import type { ReactNode } from "react";
import { fmtMoney } from "../lib/format";

export function Chip({ tone, children, title }: { tone: "green" | "amber" | "red" | "neutral" | "solid"; children: ReactNode; title?: string }) {
  const cls = {
    green: "bg-green-bg text-green-fg border-green-line",
    amber: "bg-amber-bg text-amber-fg border-amber-line",
    red: "bg-red-bg text-red-fg border-red-line",
    neutral: "bg-muted text-foreground border-border",
    solid: "bg-primary text-primary-foreground border-primary",
  }[tone];
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 border px-1.5 py-0.5 font-heading text-2xs font-bold uppercase leading-4 tracking-wider whitespace-nowrap ${cls}`}>
      {tone !== "neutral" && tone !== "solid" && <span aria-hidden className="h-1.5 w-1.5" style={{ background: `hsl(var(--${tone}-line))` }} />}
      {children}
    </span>
  );
}

export function RagChip({ value }: { value: string }) {
  const v = (value || "").toUpperCase();
  if (v === "GREEN") return <Chip tone="green">Green</Chip>;
  if (v === "AMBER") return <Chip tone="amber">Amber</Chip>;
  if (v === "RED") return <Chip tone="red">Red</Chip>;
  return <span className="text-muted-foreground">—</span>;
}

export function QaChip({ value, workbook }: { value: string; workbook?: string }) {
  const tone = value === "OK" ? "green" : value === "VERIFY" ? "amber" : "red";
  const label = value === "OK" ? "OK" : value === "VERIFY" ? "Verify" : value.replace("-", " ").toLowerCase();
  return <Chip tone={tone} title={workbook && workbook !== value ? `Workbook showed: ${workbook}` : undefined}>{label}</Chip>;
}

export function Panel({ title, action, children, className = "", flush = false }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <h2 className="text-xs tracking-wider">{title}</h2>
          {action}
        </div>
      )}
      <div className={flush ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, strong = false }: { label: string; value: ReactNode; sub?: ReactNode; strong?: boolean }) {
  return (
    <div className="min-w-0 border-l-2 border-primary pl-3">
      <div className="label">{label}</div>
      <div className={`num !text-left ${strong ? "text-2xl font-semibold" : "text-lg"} leading-tight mt-0.5`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function Money({ v, dash0 }: { v: number | null | undefined; dash0?: boolean }) {
  return <span className="num inline-block">{fmtMoney(v, { dash0 })}</span>;
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl leading-none sm:text-3xl">{title}</h1>
        {sub && <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{sub}</p>}
      </div>
      {actions && <div className="no-print flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={placeholder}
      className="h-9 w-full min-w-[12rem] border bg-background px-3 text-sm placeholder:text-muted-foreground focus:border-primary sm:w-64"
    />
  );
}

export function Select({ value, onChange, options, label, disabled }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string; disabled?: boolean }) {
  return (
    <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} aria-label={label} className="h-9 border bg-background px-2 text-sm focus:border-primary disabled:opacity-50">
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-dashed px-6 py-10 text-center">
      <div className="font-heading text-sm font-bold uppercase">{title}</div>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
