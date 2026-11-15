import type { ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import type { AgriculturalReference, PlanningFinding } from "@workspace/api-client-react";

export function humanize(key: string) {
  return key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\bmm\b/gi, "mm")
    .replace(/^./, (c) => c.toUpperCase());
}

const isUrl = (v: unknown): v is string => typeof v === "string" && /^https?:\/\//.test(v);

export function Value({ v, depth = 0 }: { v: unknown; depth?: number }): ReactNode {
  if (v === null || v === undefined || v === "") return <span className="text-muted-foreground italic">Not available</span>;
  if (typeof v === "boolean") return <span>{v ? "Yes" : "No"}</span>;
  if (typeof v === "number") return <span className="font-mono">{Number.isInteger(v) ? v : v.toFixed(3).replace(/0+$/, "")}</span>;
  if (isUrl(v)) return <a href={v} target="_blank" rel="noreferrer" className="text-accent underline-offset-2 hover:underline inline-flex max-w-full min-w-0 items-start gap-1"><span className="min-w-0 [overflow-wrap:anywhere]">{v}</span><ExternalLink className="h-3 w-3 shrink-0 mt-1" /></a>;
  if (typeof v === "string") return <span className="[overflow-wrap:anywhere]">{v}</span>;
  if (Array.isArray(v)) {
    if (!v.length) return <span className="text-muted-foreground italic">None</span>;
    if (v.every((x) => typeof x !== "object" || x === null)) {
      return <span>{v.map((x, i) => <span key={i}>{i > 0 && ", "}<Value v={x} depth={depth + 1} /></span>)}</span>;
    }
    return <div className="space-y-2">{v.map((x, i) => <div key={i} className="rounded-xl border border-border/70 p-3"><Value v={x} depth={depth + 1} /></div>)}</div>;
  }
  if (typeof v === "object") return <RecordView record={v as Record<string, unknown>} depth={depth + 1} />;
  return <span>{String(v)}</span>;
}

export function RecordView({ record, depth = 0 }: { record: Record<string, unknown>; depth?: number }) {
  const entries = Object.entries(record ?? {});
  if (!entries.length) return <p className="text-sm text-muted-foreground italic">No entries recorded.</p>;
  return (
    <dl className={depth > 0 ? "min-w-0 max-w-full space-y-1.5 border-l-2 border-secondary pl-3" : "min-w-0 max-w-full space-y-2"}>
      {entries.map(([k, v]) => (
        <div key={k} className={`min-w-0 max-w-full grid ${depth === 0 ? "sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)]" : ""} gap-x-4 gap-y-0.5 text-sm`}>
          <dt className="min-w-0 [overflow-wrap:anywhere] font-mono text-[11px] uppercase tracking-wider text-muted-foreground pt-0.5">{humanize(k)}</dt>
          <dd className="min-w-0 max-w-full [overflow-wrap:anywhere]"><Value v={v} depth={depth} /></dd>
        </div>
      ))}
    </dl>
  );
}

export function Findings({ items, refs, tone = "neutral", empty, testid }: { items: PlanningFinding[]; refs: AgriculturalReference[]; tone?: "neutral" | "risk" | "benefit"; empty: string; testid: string }) {
  if (!items.length) return <p className="text-sm text-muted-foreground italic">{empty}</p>;
  const bar = tone === "risk" ? "bg-destructive/70" : tone === "benefit" ? "bg-chart-3" : "bg-chart-1";
  return (
    <ul className="space-y-2.5">
      {items.map((f, i) => (
        <li key={`${f.code}-${i}`} className="flex gap-3 text-sm" data-testid={`${testid}-${i}`}>
          <span className={`mt-1.5 h-3 w-1 shrink-0 rounded-full ${bar}`} />
          <div className="min-w-0">
            <p className="leading-relaxed">{f.message}</p>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
              <span>{humanize(f.code)}</span>
              {f.sourceIds.map((sid) => {
                const r = refs.find((x) => x.id === sid);
                return r ? <a key={sid} href={r.url} target="_blank" rel="noreferrer" className="text-accent hover:underline" title={r.title}>{sid}</a> : <span key={sid}>{sid}</span>;
              })}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
