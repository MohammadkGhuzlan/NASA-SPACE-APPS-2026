import { useState } from "react";
import { Loader2, MapPin, RotateCcw, Search } from "lucide-react";
import {
  useAssessFarmGaez, useGetGaezCatalog,
  type GaezAssessment, type GaezDataset, type GaezReportEvidence,
} from "@workspace/api-client-react";
import { Tag } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Warnings, errMessage } from "@/components/env-kit";
import { RecordView, humanize } from "@/components/record-view";
import { cn } from "@/lib/utils";

/** FAO GAEZ v5 RES05-SIX class definitions (categorical, ordinal; not percentages). */
const CLASS_LABELS: Record<number, string> = {
  1: "Very high", 2: "High", 3: "Good", 4: "Medium", 5: "Moderate",
  6: "Marginal", 7: "Very marginal", 8: "Not suitable",
};
const FIXED_LABELS: Record<number, string> = { 0: "No data", 9: "Water" };

const STATUS_COPY: Record<string, { title: string; detail: string }> = {
  available: { title: "Class retrieved", detail: "A published FAO class was read at the farm point." },
  nodata: { title: "No data at this point", detail: "The FAO layer has no value for this grid cell. No class is shown and nothing has been substituted." },
  not_land: { title: "Not land in the FAO grid", detail: "The sampled cell is classed as water or non-land. No crop class applies." },
  outside_coverage: { title: "Outside dataset coverage", detail: "The farm point falls outside the layer extent. No class is shown." },
  unsupported: { title: "Combination not supported", detail: "This crop or scenario is not in the verified layer subset. No class is shown." },
  unavailable: { title: "Source unavailable", detail: "The FAO layer could not be read right now. Retry later; no fallback value is used." },
};

function classTone(code: number | null | undefined) {
  if (code == null || code < 1 || code > 8) return "bg-muted text-muted-foreground border-dashed border-input";
  if (code <= 3) return "bg-secondary text-secondary-foreground border-[hsl(92_20%_70%)]";
  if (code <= 5) return "bg-[hsl(200_38%_42%/.12)] text-[hsl(200_45%_30%)] border-[hsl(200_38%_42%/.3)]";
  if (code <= 7) return "bg-[hsl(38_70%_50%/.14)] text-[hsl(30_60%_30%)] border-[hsl(38_70%_50%/.35)]";
  return "bg-destructive/10 text-destructive border-destructive/30";
}

function classText(a: GaezAssessment) {
  if (a.status !== "available" || a.rawValue == null) return humanize(a.status);
  return a.category ?? CLASS_LABELS[a.rawValue] ?? FIXED_LABELS[a.rawValue] ?? "Unlisted code";
}

function ClassChip({ a, compact }: { a: GaezAssessment; compact?: boolean }) {
  const code = a.status === "available" ? a.rawValue : null;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border font-mono uppercase tracking-wider", compact ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-[11px]", classTone(code))}>
      {code != null && <span className="opacity-70">Class {code}</span>}
      <span>{classText(a)}</span>
    </span>
  );
}

const fmt = (d: string | null | undefined) => {
  if (!d) return "not recorded";
  const t = new Date(d);
  return isNaN(t.getTime()) ? d : t.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
};

function ScopeNotes({ dataset }: { dataset: GaezDataset }) {
  return (
    <ul className="grid sm:grid-cols-2 gap-2 text-xs text-muted-foreground leading-relaxed">
      <li className="rounded-xl bg-muted/60 p-3"><span className="font-semibold text-foreground">Scale.</span> {dataset.resolutionLabel || "5 arc-minute"} grid, roughly 10 km per cell. One cell is sampled at the farm point; no farm-boundary aggregation is calculated.</li>
      <li className="rounded-xl bg-muted/60 p-3"><span className="font-semibold text-foreground">Period.</span> {dataset.referencePeriod} AgERA5 climate inside the FAO model. This is separate from the 2019 to 2025 NASA POWER data shown elsewhere in Field Shift.</li>
      <li className="rounded-xl bg-muted/60 p-3"><span className="font-semibold text-foreground">Soil.</span> Soil conditions are modeled inside FAO GAEZ. They are not independent tests of your farm's soil.</li>
      <li className="rounded-xl bg-muted/60 p-3"><span className="font-semibold text-foreground">Meaning.</span> Classes are ordered categories (1 best, 8 not suitable). They are not percentages, yields, confidence values, or a ranking across crops.</li>
    </ul>
  );
}

function ClassLegend({ classes }: { classes?: { code: number; label: string }[] }) {
  const list = classes && classes.length ? classes : Object.entries({ ...FIXED_LABELS, ...CLASS_LABELS }).map(([c, l]) => ({ code: Number(c), label: l }));
  return (
    <details className="text-sm">
      <summary className="cursor-pointer font-semibold text-accent">Class definitions</summary>
      <ul className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-1.5">
        {[...list].sort((a, b) => a.code - b.code).map((c) => (
          <li key={c.code} className={cn("rounded-lg border px-2 py-1 text-xs", classTone(c.code))}><span className="font-mono mr-1">{c.code}</span>{c.label}</li>
        ))}
      </ul>
    </details>
  );
}

function Citation({ dataset }: { dataset: GaezDataset }) {
  return (
    <div className="text-xs text-muted-foreground space-y-1">
      <p>{dataset.attribution} · License: {dataset.license}</p>
      <p className="flex flex-wrap gap-x-3 gap-y-1">
        <a href={dataset.metadataUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">Metadata</a>
        <a href={dataset.catalogUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">Data catalog</a>
        <a href={dataset.classDefinitionUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">Class definition</a>
      </p>
    </div>
  );
}

function Provenance({ a }: { a: GaezAssessment }) {
  return (
    <details className="text-sm">
      <summary className="cursor-pointer font-semibold text-accent">Source provenance and sampling</summary>
      <dl className="mt-2 grid gap-1.5 text-xs">
        <div><dt className="text-muted-foreground uppercase tracking-wider">Asset ID</dt><dd className="font-mono break-all">{a.datasetId ?? "not recorded"}</dd></div>
        <div><dt className="text-muted-foreground uppercase tracking-wider">Source URL</dt><dd className="break-all">{a.sourceUrl ? <a href={a.sourceUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">{a.sourceUrl}</a> : "not recorded"}</dd></div>
        <div><dt className="text-muted-foreground uppercase tracking-wider">SHA-256</dt><dd className="font-mono break-all">{a.sha256 ?? "not recorded"}</dd></div>
        <div><dt className="text-muted-foreground uppercase tracking-wider">Retrieved</dt><dd>{fmt(a.retrievedAt)}</dd></div>
        <div><dt className="text-muted-foreground uppercase tracking-wider">Raw code</dt><dd className="font-mono">{a.rawValue ?? "none"}</dd></div>
      </dl>
      {Object.keys(a.sampling ?? {}).length > 0 && <div className="mt-2 rounded-xl bg-muted/60 p-3"><RecordView record={a.sampling} /></div>}
    </details>
  );
}

function ResultCard({ a, onRetry, retrying }: { a: GaezAssessment; onRetry?: () => void; retrying?: boolean }) {
  const ok = a.status === "available" && a.rawValue != null;
  const copy = STATUS_COPY[a.status] ?? STATUS_COPY.unavailable;
  return (
    <div className={cn("rounded-2xl p-4 md:p-5 space-y-3", ok ? "border border-border" : "border-2 border-dashed border-input furrows")} data-testid="gaez-result" data-status={a.status}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">{a.cropCode} · {a.scenario}</p>
          <p className="font-display text-2xl text-primary">{a.cropName}</p>
          <p className="text-sm text-muted-foreground">{a.scenarioLabel}</p>
        </div>
        <ClassChip a={a} />
      </div>
      <p className={cn("text-sm", !ok && "font-semibold")} role={ok ? undefined : "status"}>{copy.title}. <span className="font-normal text-muted-foreground">{copy.detail}</span></p>
      {ok && <p className="text-sm text-muted-foreground">FAO class {a.rawValue} of 8 for this crop under this input and water scenario at one ~10 km cell. Compare only with other scenarios of the same crop, and read alongside your own constraints.</p>}
      <Warnings items={a.warnings} />
      {!ok && onRetry && <Button type="button" variant="outline" size="sm" className="rounded-full" onClick={onRetry} disabled={retrying} data-testid="gaez-retry">
        {retrying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}Retry lookup</Button>}
      <Provenance a={a} />
    </div>
  );
}

const RICE_CODES = ["RCD", "RCW"];

export function GaezEvidence({ farmId, defaultCrop }: { farmId: number; defaultCrop: string }) {
  const catalog = useGetGaezCatalog({ query: { staleTime: 5 * 60_000, retry: 1 } });
  const assess = useAssessFarmGaez();
  const crops = catalog.data?.crops ?? [];
  const scenarios = catalog.data?.scenarios ?? [];
  const guess = (() => {
    const d = defaultCrop.trim().toLowerCase();
    if (!d || d.includes("rice")) return ""; // never pick a rice type for the farmer
    return crops.find((c) => !RICE_CODES.includes(c.code) && c.name.toLowerCase() === d)?.code ?? "";
  })();
  const [cropPick, setCropPick] = useState<string | null>(null);
  const [scenarioPick, setScenarioPick] = useState<string | null>(null);
  const crop = cropPick ?? guess;
  const scenario = scenarioPick ?? scenarios[0]?.code ?? "";
  const riceHint = /rice/i.test(defaultCrop) && !cropPick;
  const unavailable = catalog.data?.status === "unavailable";

  const run = () => {
    if (!crop || !scenario) return;
    assess.mutate({ id: farmId, data: { cropCode: crop, scenario, datasetVersion: "GAEZ-v5", referencePeriod: "2001-2020" } });
  };

  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 md:p-6 space-y-5" aria-labelledby="gaez-heading" data-testid="gaez-evidence">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-3xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Published FAO evidence · not a Field Shift model</p>
          <h3 id="gaez-heading" className="font-display text-2xl md:text-3xl text-primary mt-1">FAO GAEZ crop suitability class</h3>
          <p className="text-sm text-muted-foreground mt-2">Trained AI crop-suitability predictions are not currently available. This assessment uses published FAO data and documented requirements: it reads one GAEZ v5 suitability class (RES05-SIX) for the cell under your farm point.</p>
        </div>
        <Tag kind="observed">FAO GAEZ v5 · 2001–2020</Tag>
      </div>

      {catalog.isLoading ? (
        <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3"><Skeleton className="h-10 rounded-md" /><Skeleton className="h-10 rounded-md" /><Skeleton className="h-10 w-32 rounded-full" /></div>
      ) : catalog.isError || !catalog.data ? (
        <div className="rounded-2xl border-2 border-dashed border-input furrows p-6 text-center" role="alert">
          <p className="font-display text-xl text-primary">FAO catalog could not be loaded</p>
          <p className="text-sm text-muted-foreground mt-1">{errMessage(catalog.error)} No suitability class is shown.</p>
          <Button variant="outline" className="mt-3 rounded-full" onClick={() => catalog.refetch()} data-testid="gaez-catalog-retry"><RotateCcw className="h-4 w-4" />Retry</Button>
        </div>
      ) : (
        <>
          <Warnings items={catalog.data.warnings} />
          {unavailable && <p role="status" className="rounded-xl bg-muted px-3 py-2 text-sm">The FAO source is marked unavailable. Lookups may fail; no fallback class is used.</p>}
          <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
            <div className="space-y-1.5 min-w-0">
              <Label htmlFor="gaez-crop" className="text-xs uppercase tracking-wider text-muted-foreground">Crop</Label>
              <select id="gaez-crop" value={crop} onChange={(e) => { setCropPick(e.target.value); assess.reset(); }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" data-testid="gaez-crop">
                <option value="" disabled>Select a crop</option>
                {crops.map((c) => <option key={c.code} value={c.code}>{c.name} ({c.code})</option>)}
              </select>
            </div>
            <div className="space-y-1.5 min-w-0">
              <Label htmlFor="gaez-scenario" className="text-xs uppercase tracking-wider text-muted-foreground">Input and water scenario</Label>
              <select id="gaez-scenario" value={scenario} onChange={(e) => { setScenarioPick(e.target.value); assess.reset(); }}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" data-testid="gaez-scenario">
                {scenarios.map((s) => <option key={s.code} value={s.code}>{s.name} ({s.code})</option>)}
              </select>
            </div>
            <Button type="button" onClick={run} disabled={!crop || !scenario || assess.isPending} className="rounded-full" data-testid="gaez-assess">
              {assess.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}Look up class
            </Button>
          </div>
          {riceHint && <p className="text-xs text-muted-foreground -mt-2">Your crop is listed as rice. FAO separates dryland rice (RCD) and wetland rice (RCW); choose the type you actually grow.</p>}
          <p className="text-xs text-muted-foreground -mt-2">Both irrigated low-input and high-input assessments assume irrigation, not water availability at your farm. Your water access, priorities and costs decide what is feasible.</p>

          {assess.isPending ? <Skeleton className="h-40 rounded-2xl" />
            : assess.isError ? (
              <div className="rounded-2xl border-2 border-dashed border-input furrows p-6" role="alert">
                <p className="font-display text-xl text-primary">Lookup failed</p>
                <p className="text-sm text-muted-foreground mt-1">{errMessage(assess.error)} No class is shown.</p>
                <Button variant="outline" className="mt-3 rounded-full" onClick={run} data-testid="gaez-retry"><RotateCcw className="h-4 w-4" />Retry</Button>
              </div>
            ) : assess.data ? <ResultCard a={assess.data} onRetry={run} retrying={assess.isPending} />
            : (
              <div className="rounded-2xl border-2 border-dashed border-input p-6 text-center">
                <MapPin className="h-6 w-6 mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground mt-2">Pick a crop and scenario to read the published FAO class at this farm point.</p>
              </div>
            )}
          <ClassLegend classes={catalog.data.classes} />
          <ScopeNotes dataset={catalog.data.dataset} />
          <div className="flex flex-wrap items-end justify-between gap-2">
            <Citation dataset={catalog.data.dataset} />
            <span className="font-mono text-[10.5px] uppercase text-muted-foreground">{catalog.data.dataset.variable} · {catalog.data.cachedLayers} layers cached</span>
          </div>
        </>
      )}
    </section>
  );
}

export function GaezReport({ evidence }: { evidence: GaezReportEvidence }) {
  const cropOrder: string[] = [];
  const scenOrder: string[] = [];
  const scenLabel: Record<string, string> = {};
  const cropName: Record<string, string> = {};
  const grid: Record<string, GaezAssessment> = {};
  for (const r of evidence.results) {
    if (!cropOrder.includes(r.cropCode)) cropOrder.push(r.cropCode);
    if (!scenOrder.includes(r.scenario)) scenOrder.push(r.scenario);
    scenLabel[r.scenario] = r.scenarioLabel;
    cropName[r.cropCode] = r.cropName;
    grid[`${r.cropCode}|${r.scenario}`] = r;
  }
  const available = evidence.results.filter((r) => r.status === "available").length;
  const ctx = evidence.context ?? {};

  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 md:p-6 space-y-5" data-testid="gaez-snapshot" data-status={evidence.status}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-3xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Saved FAO GAEZ snapshot</p>
          <h3 className="font-display text-2xl text-primary mt-1">Published suitability classes at this point</h3>
          <p className="text-sm text-muted-foreground mt-2">Recorded {fmt(evidence.generatedAt)}. {available} of {evidence.results.length} crop and scenario lookups returned a class. This is published FAO data, not a Field Shift ML prediction or yield forecast. Compare scenarios within a crop; do not rank crops against each other.</p>
        </div>
        <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider",
          evidence.status === "available" ? "bg-secondary border-[hsl(92_20%_70%)] text-secondary-foreground" : "bg-[hsl(38_70%_50%/.14)] text-[hsl(30_60%_30%)] border-[hsl(38_70%_50%/.35)]")}>{humanize(evidence.status)}</span>
      </div>
      <Warnings items={evidence.warnings} />

      {evidence.results.length === 0 ? (
        <p className="rounded-2xl border-2 border-dashed border-input p-6 text-sm text-muted-foreground text-center">No FAO classes were recorded in this snapshot. Nothing has been substituted.</p>
      ) : (
        <>
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm border-separate border-spacing-0">
              <thead><tr>
                <th className="text-left text-xs uppercase tracking-wider text-muted-foreground font-normal pb-2 pr-3">Crop</th>
                {scenOrder.map((s) => <th key={s} className="text-left text-xs text-muted-foreground font-normal pb-2 px-2"><span className="font-mono">{s}</span><span className="block normal-case">{scenLabel[s]}</span></th>)}
              </tr></thead>
              <tbody>{cropOrder.map((c) => (
                <tr key={c} className="border-t border-border">
                  <td className="py-2 pr-3 border-t border-border"><span className="font-semibold">{cropName[c]}</span> <span className="font-mono text-[10.5px] text-muted-foreground">{c}</span></td>
                  {scenOrder.map((s) => { const a = grid[`${c}|${s}`]; return (
                    <td key={s} className="py-2 px-2 border-t border-border" data-testid={`gaez-cell-${c}-${s}`}>{a ? <ClassChip a={a} compact /> : <span className="text-xs text-muted-foreground">not run</span>}</td>
                  ); })}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="md:hidden space-y-3">
            {cropOrder.map((c) => (
              <div key={c} className="rounded-2xl border border-border p-3">
                <p className="font-semibold">{cropName[c]} <span className="font-mono text-[10.5px] text-muted-foreground">{c}</span></p>
                <ul className="mt-2 space-y-1.5">{scenOrder.map((s) => { const a = grid[`${c}|${s}`]; return (
                  <li key={s} className="flex items-center justify-between gap-2 text-xs"><span className="text-muted-foreground">{scenLabel[s]}</span>{a ? <ClassChip a={a} compact /> : <span className="text-muted-foreground">not run</span>}</li>
                ); })}</ul>
              </div>
            ))}
          </div>
        </>
      )}

      {evidence.planningNotes.length > 0 && (
        <div><p className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Planning notes</p>
          <ul className="list-disc pl-5 space-y-1 text-sm">{evidence.planningNotes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>
      )}
      <p className="text-sm">Your priorities and irrigation access constrain how these classes apply. An irrigated high-input class is not automatically feasible or preferred. The baseline and two alternatives above remain the planning scenarios.</p>
      <ClassLegend />
      <ScopeNotes dataset={evidence.dataset} />
      <details className="text-sm">
        <summary className="cursor-pointer font-semibold text-accent">Per-lookup provenance ({evidence.results.length})</summary>
        <div className="mt-2 grid lg:grid-cols-2 gap-3">{evidence.results.map((a) => <ResultCard key={`${a.cropCode}-${a.scenario}`} a={a} />)}</div>
      </details>
      {Object.keys(ctx).length > 0 && (
        <details className="text-sm"><summary className="cursor-pointer font-semibold text-accent">Context recorded with this snapshot</summary>
          <div className="mt-2 rounded-xl bg-muted/60 p-3"><RecordView record={ctx} /></div></details>
      )}
      <Citation dataset={evidence.dataset} />
    </section>
  );
}
