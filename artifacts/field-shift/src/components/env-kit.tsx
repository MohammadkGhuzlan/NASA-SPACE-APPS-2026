import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export const axisTick = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };
export const tooltipStyle = { borderRadius: 14, border: "1px solid hsl(var(--border))", background: "hsl(var(--card))", fontSize: 12 };

export function fmtNum(v: unknown, digits = 1, unit = ""): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "no value";
  return `${v.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

export function Section({ eyebrow, title, children, actions, testid }: { eyebrow?: string; title: ReactNode; children: ReactNode; actions?: ReactNode; testid?: string }) {
  return (
    <section className="min-w-0 max-w-full rounded-3xl border border-card-border bg-card p-5 md:p-6" data-testid={testid}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow && <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">{eyebrow}</p>}
          <h2 className="font-display text-2xl text-primary mt-1">{title}</h2>
        </div>
        {actions}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Warnings({ items, testid }: { items: string[]; testid?: string }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2" data-testid={testid}>
      {items.map((w, i) => (
        <li key={i} className="flex gap-2 rounded-xl bg-[hsl(38_70%_50%/.12)] px-3 py-2 text-sm text-[hsl(30_60%_28%)]"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />{w}</li>
      ))}
    </ul>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="mt-3 text-xs text-muted-foreground leading-relaxed">{children}</p>;
}

export function Unavailable({ title, detail, onRetry, testid }: { title: string; detail: string; onRetry?: () => void; testid?: string }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-input furrows p-8 text-center" data-testid={testid}>
      <p className="font-display text-xl text-primary">{title}</p>
      <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">{detail}</p>
      {onRetry && <Button variant="outline" className="mt-4 rounded-full" onClick={onRetry} data-testid={testid ? `button-retry-${testid}` : undefined}><RefreshCw className="h-4 w-4" />Retry</Button>}
    </div>
  );
}

export function SectionSkeleton({ note }: { note?: string }) {
  return (
    <div className="rounded-3xl border border-card-border bg-card p-6">
      <Skeleton className="h-6 w-60" /><Skeleton className="h-[260px] mt-5 rounded-2xl" />
      {note && <p className="text-xs text-muted-foreground mt-3">{note}</p>}
    </div>
  );
}

export function errMessage(e: unknown): string {
  if (e && typeof e === "object") {
    const r = e as Record<string, unknown>;
    const d = r.data as Record<string, unknown> | undefined;
    if (d && typeof d.detail === "string") return d.detail;
    if (typeof r.message === "string") return r.message;
  }
  return "The request failed.";
}
