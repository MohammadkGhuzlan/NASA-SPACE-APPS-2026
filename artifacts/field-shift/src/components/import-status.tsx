import { useGetDataStatus } from "@workspace/api-client-react";
import { Section, SectionSkeleton, Unavailable, errMessage, Note } from "@/components/env-kit";
import { cn } from "@/lib/utils";

type Rec = Record<string, unknown>;
const isRec = (v: unknown): v is Rec => !!v && typeof v === "object" && !Array.isArray(v);
const strList = (v: unknown): string[] => (Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : JSON.stringify(x))) : []);
const fmt = (v: unknown) => (v === null || v === undefined ? "none" : typeof v === "object" ? JSON.stringify(v) : String(v));

function FileCard({ f, i }: { f: Rec; i: number }) {
  const name = fmt(f.file ?? f.fileName ?? f.name ?? `File ${i + 1}`);
  const warnings = strList(f.warnings), errors = strList(f.errors);
  const scalars = Object.entries(f).filter(([k, v]) => !["file", "fileName", "name", "warnings", "errors"].includes(k) && (typeof v !== "object" || v === null));
  const nested = Object.entries(f).filter(([k, v]) => !["warnings", "errors"].includes(k) && v !== null && typeof v === "object");
  return (
    <div className="min-w-0 max-w-full rounded-2xl border border-border p-4 [overflow-wrap:anywhere]" data-testid={`card-import-file-${i}`}>
      <p className="font-mono text-sm font-semibold break-all">{name}</p>
      <dl className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
        {scalars.map(([k, v]) => <div key={k}><dt className="text-[10.5px] font-mono uppercase tracking-wider text-muted-foreground">{k}</dt><dd className="text-sm font-medium break-words">{fmt(v)}</dd></div>)}
      </dl>
      {nested.map(([k, v]) => <p key={k} className="mt-2 text-xs text-muted-foreground break-words"><span className="font-mono">{k}:</span> {fmt(v)}</p>)}
      {errors.length > 0 && <ul className="mt-2 space-y-1 text-xs text-destructive">{errors.map((e, j) => <li key={j}>Error: {e}</li>)}</ul>}
      {warnings.length > 0 && <ul className="mt-2 space-y-1 text-xs text-[hsl(30_60%_28%)]">{warnings.map((e, j) => <li key={j}>Warning: {e}</li>)}</ul>}
    </div>
  );
}

export function ImportStatus() {
  const q = useGetDataStatus();
  return (
    <div id="data-import-audit" className="mt-12 min-w-0 max-w-full [overflow-wrap:anywhere]">
      <h2 className="font-display text-3xl text-primary mb-4">Data import audit</h2>
      {q.isLoading ? <SectionSkeleton /> : q.isError || !q.data ? <Unavailable title="Import status unavailable" detail={errMessage(q.error)} onRetry={() => q.refetch()} testid="data-status" /> : (
        <div className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="rounded-3xl border border-card-border bg-card p-5"><p className="text-sm text-muted-foreground">Stored environmental values</p><p className="font-display text-4xl text-primary" data-testid="text-env-values">{q.data.environmentalValues.toLocaleString()}</p></div>
            <div className="rounded-3xl border border-card-border bg-card p-5"><p className="text-sm text-muted-foreground">Stored soil estimates</p><p className="font-display text-4xl text-primary" data-testid="text-soil-estimates">{q.data.soilEstimates.toLocaleString()}</p></div>
          </div>
          <p className="text-sm text-muted-foreground" data-testid="text-import-policy">{q.data.importPolicy}</p>
          {!q.data.reports.length ? <Unavailable title="No import runs recorded" detail="No ingestion audit exists yet." /> : q.data.reports.map((r) => {
            const files = Array.isArray(r.report.files) ? r.report.files.filter(isRec) : [];
            const top = Object.entries(r.report).filter(([k, v]) => k !== "files" && (typeof v !== "object" || v === null));
            const errs = strList(r.report.errors), warns = strList(r.report.warnings);
            return (
              <Section key={r.id} eyebrow={`Run ${r.id} · ${r.source}`} title={r.startedAt} testid={`section-import-${r.id}`}
                actions={<span className={cn("rounded-full px-3 py-1 font-mono text-[10.5px] uppercase tracking-wider", /fail|error/i.test(r.status) ? "bg-destructive/15 text-destructive" : /partial|warn/i.test(r.status) ? "bg-[hsl(38_70%_50%/.15)] text-[hsl(30_60%_30%)]" : "bg-secondary")}>{r.status}</span>}>
                <p className="text-xs text-muted-foreground">Completed {r.completedAt ?? "not completed"}</p>
                {top.length > 0 && <p className="mt-2 text-xs">{top.map(([k, v]) => <span key={k} className="mr-4"><span className="font-mono text-muted-foreground">{k}:</span> {fmt(v)}</span>)}</p>}
                {errs.map((e, j) => <p key={`e${j}`} className="mt-1 text-xs text-destructive">Error: {e}</p>)}
                {warns.map((e, j) => <p key={`w${j}`} className="mt-1 text-xs text-[hsl(30_60%_28%)]">Warning: {e}</p>)}
                <div className="mt-3 grid gap-3">{files.length ? files.map((f, i) => <FileCard key={i} f={f} i={i} />) : <p className="text-sm text-muted-foreground">No per-file report.</p>}</div>
              </Section>
            );
          })}
          <Note>Read-only, newest runs first. Earlier failed runs remain in the audit trail even after a later run resolves them. Imports are run by the operator; this page cannot trigger them.</Note>
        </div>
      )}
    </div>
  );
}
