import { ExternalLink } from "lucide-react";
import { useListSources } from "@workspace/api-client-react";
import { ImportStatus } from "@/components/import-status";
import { PageHead, Shell } from "@/components/shell";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

const limits = [
  "Climate values are NASA POWER daily data aggregated to months, seasons and years for 2019 to 2025. They describe a grid cell, not your specific field.",
  "Heat days count days with daily maximum temperature at or above 35 °C. Thresholds that matter differ by crop.",
  "Soil wetness is the NASA POWER modeled GWETTOP/GWETROOT fraction, not a field reading. SMAP soil moisture and MODIS vegetation indices are not connected and show as unavailable.",
  "Soil properties are SoilGrids 0-5 cm proxies sampled near study regions only. They are demonstration proxies, never substituted across regions.",
  "Climate CSV time standard is unknown while wetness is UTC, so daily comparisons between them may be offset by a day.",
  "Soil moisture, pH and crop history are farmer reported and are not verified.",
  "Rotation alternatives are farmer drafts. No crop requirement database or assessment engine is in use.",
  "No AI model has been trained or deployed in this prototype.",
  "Case-study locations are starting points only, not measured farms.",
];

export default function Sources() {
  const sources = useListSources();
  return (
    <Shell>
      <div className="mx-auto max-w-5xl px-5 py-12">
        <PageHead eyebrow="Provenance" title={<>Where every number <span className="italic text-accent">comes from</span></>}>
          And, as importantly, where it does not.
        </PageHead>
        <div className="space-y-3">
          {sources.isLoading ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-3xl" />) : sources.isError ? (
            <div className="rounded-3xl border border-card-border bg-card p-8">
              <p className="font-display text-2xl text-primary">Sources could not be loaded</p>
              <Button className="mt-4 rounded-full" onClick={() => sources.refetch()} data-testid="button-retry-sources">Retry</Button>
            </div>
          ) : !sources.data?.length ? (
            <p className="text-muted-foreground">No sources registered.</p>
          ) : sources.data.map((s) => (
            <div key={s.id} className="lift rounded-3xl border border-card-border bg-card p-6 grid md:grid-cols-[1fr_auto] gap-4" data-testid={`card-source-${s.id}`}>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-display text-2xl text-primary">{s.name}</h2>
                  <span className="rounded-full border border-input px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">{s.status}</span>
                </div>
                <p className="text-sm text-foreground/75 mt-2 leading-relaxed">{s.description}</p>
              </div>
              <a href={s.url} target="_blank" rel="noreferrer" className="self-start inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline" data-testid={`link-source-${s.id}`}>Visit <ExternalLink className="h-3.5 w-3.5" /></a>
            </div>
          ))}
        </div>
        <ImportStatus />
        <section className="mt-12 rounded-[2rem] bg-primary text-primary-foreground p-8 md:p-10 furrows">
          <h2 className="font-display text-3xl">Known limitations</h2>
          <ol className="mt-6 space-y-4">
            {limits.map((l, i) => (
              <li key={i} className="flex gap-4 border-t border-primary-foreground/15 pt-4"><span className="font-mono text-sm text-[hsl(92_24%_66%)]">{String(i + 1).padStart(2, "0")}</span><span className="opacity-90 leading-relaxed">{l}</span></li>
            ))}
          </ol>
        </section>
      </div>
    </Shell>
  );
}
