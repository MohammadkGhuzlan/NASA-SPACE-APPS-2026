import { ExternalLink } from "lucide-react";
import { useGetAgriculturalKnowledge } from "@workspace/api-client-react";
import { PageHead, Shell, Tag } from "@/components/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { humanize } from "@/components/record-view";

const range = (r?: number[]) => (r?.length ? `${r[0]} to ${r[1] ?? r[0]}` : "Not stated");

export default function Knowledge() {
  const k = useGetAgriculturalKnowledge();
  return (
    <Shell>
      <div className="mx-auto max-w-6xl px-5 py-12">
        <PageHead eyebrow="Reference library" title={<>The facts the rules <span className="italic text-accent">are allowed to use</span></>}
          actions={k.data ? <Tag kind="observed">Version {k.data.version}</Tag> : undefined}>
          Thirteen crops with FAO ECOCROP constraints, NASA context and USDA NRCS rotation guidance. ECOCROP values are expert estimates—not farm measurements, locally validated calendars, suitability scores or yield predictions.
        </PageHead>
        {k.isLoading ? (
          <div className="grid md:grid-cols-2 gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-64 rounded-3xl" />)}</div>
        ) : k.isError || !k.data ? (
          <div className="rounded-3xl border border-card-border bg-card p-8">
            <p className="font-display text-2xl text-primary">The reference library could not be loaded</p>
            <p className="text-sm text-muted-foreground mt-2">Nothing is shown in its place.</p>
            <Button className="mt-4 rounded-full" onClick={() => k.refetch()} data-testid="button-retry-knowledge">Retry</Button>
          </div>
        ) : (
          <>
            {k.data.crops.length === 0 ? (
              <p className="rounded-3xl border-2 border-dashed border-input p-8 text-muted-foreground">No reference crops are published in this version.</p>
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {k.data.crops.map((c, i) => {
                  const eco = c.ecologicalRequirements as Record<string, unknown>;
                  const ecoRange = (key: string) => range(eco[key] as number[] | undefined);
                  return (
                  <article key={c.id} className="rise lift rounded-3xl border border-card-border bg-card p-6 flex flex-col gap-4" style={{ animationDelay: `${i * 60}ms` }} data-testid={`card-crop-${c.id}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">{c.group} / ECOCROP {String(eco.ecoPortCode ?? "—")}</p>
                        <h2 className="font-display text-3xl text-primary">{c.name}</h2>
                        <p className="text-sm text-muted-foreground italic">{String(eco.scientificName ?? "")}</p>
                      </div>
                      <Tag kind="observed">Reference</Tag>
                    </div>
                    <dl className="grid sm:grid-cols-2 gap-3 rounded-2xl bg-muted/70 p-4">
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Crop cycle estimate (days)</dt><dd className="font-mono text-lg">{range(c.growingDays)}</dd></div>
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">FAO crop-water reference (mm)</dt><dd className="font-mono text-lg">{range(c.waterMm)}</dd></div>
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Broad temperature limits</dt><dd className="font-mono text-lg">{ecoRange("broadTemperatureLimitsC")} °C</dd></div>
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Broad soil pH limits</dt><dd className="font-mono text-lg">{ecoRange("broadSoilPhLimits")}</dd></div>
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Optimal temperature estimate</dt><dd className="font-mono text-lg">{ecoRange("optimalTemperatureC")} °C</dd></div>
                      <div><dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Annual rainfall range</dt><dd className="font-mono text-lg">{ecoRange("optimalAnnualRainfallMm")} mm</dd></div>
                    </dl>
                    <p className="text-xs text-muted-foreground">ECOCROP annual rainfall estimates are shown in saved reports where relevant, but are not directly compared with NASA rainfall or seasonal farm water.</p>
                    {c.limitations.length > 0 && (
                      <ul className="text-sm text-muted-foreground space-y-1 list-disc pl-5">{c.limitations.map((l, j) => <li key={j}>{l}</li>)}</ul>
                    )}
                    <div className="mt-auto flex flex-wrap gap-2">
                      {c.sourceIds.map((sid) => {
                        const r = k.data!.references.find((x) => x.id === sid);
                        return r ? <a key={sid} href={r.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-full border border-input px-3 py-1 text-xs hover:bg-secondary" data-testid={`link-crop-source-${c.id}-${sid}`}>{sid}<ExternalLink className="h-3 w-3" /></a> : <span key={sid} className="rounded-full border border-dashed border-input px-3 py-1 text-xs">{sid}</span>;
                      })}
                    </div>
                  </article>
                  );
                })}
              </div>
            )}
            <div className="mt-10 grid lg:grid-cols-[1.3fr_1fr] gap-5">
              <section className="rounded-3xl border border-card-border bg-card p-6">
                <h2 className="font-display text-2xl text-primary">Citations</h2>
                <ul className="mt-4 divide-y divide-border">
                  {k.data.references.map((r) => (
                    <li key={r.id} className="py-3">
                      <a href={r.url} target="_blank" rel="noreferrer" className="font-semibold text-primary hover:text-accent inline-flex items-start gap-1.5" data-testid={`link-reference-${r.id}`}>{r.title}<ExternalLink className="h-3.5 w-3.5 mt-1 shrink-0" /></a>
                      <p className="text-sm text-muted-foreground mt-1">{r.scope}</p>
                      <p className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground mt-1">{r.id} / checked {r.checkedOn}</p>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="rounded-3xl bg-primary text-primary-foreground furrows p-6">
                <h2 className="font-display text-2xl">Limits of this library</h2>
                <ul className="mt-4 space-y-2 text-sm opacity-90 list-disc pl-5">
                  {k.data.limitations.map((l, i) => <li key={i}>{l}</li>)}
                  <li>Cool and warm season labels come from University of Minnesota Extension material, not a global local-adaptation assessment.</li>
                  <li>No machine-learning model is trained. No suitability score or yield prediction exists.</li>
                </ul>
              </section>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
