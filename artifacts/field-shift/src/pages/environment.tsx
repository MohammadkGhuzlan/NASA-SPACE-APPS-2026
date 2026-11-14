import { useSearch, Link } from "wouter";
import { useListCaseStudies } from "@workspace/api-client-react";
import { PageHead, Shell } from "@/components/shell";
import { EnvironmentAnalysis } from "@/components/environment-analysis";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { fmtCoord } from "@/lib/field";

export default function Explore() {
  const sp = new URLSearchParams(useSearch());
  const studies = useListCaseStudies();
  const la = Number(sp.get("latitude")), lo = Number(sp.get("longitude"));
  const given = sp.get("latitude") !== null && sp.get("longitude") !== null && Number.isFinite(la) && Number.isFinite(lo) && Math.abs(la) <= 90 && Math.abs(lo) <= 180;
  const first = studies.data?.[0];
  const lat = given ? la : first?.latitude, lon = given ? lo : first?.longitude;
  const name = sp.get("name") || (given ? fmtCoord(la, lo) : first ? `${first.name}, ${first.country}` : "");
  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        <PageHead eyebrow="Explore before saving" title={<>{name || "Choose a location"}</>}
          actions={<Link href="/select" className="rounded-full border border-input px-5 py-2.5 text-sm font-semibold hover:bg-secondary" data-testid="link-back-select">Pick on map</Link>}>
          Gridded NASA POWER context for {lat !== undefined && lon !== undefined ? <span className="font-mono text-xs">{fmtCoord(lat, lon)}</span> : "a location"}. These are regional estimates, not measurements of your field.
        </PageHead>
        <div className="flex flex-wrap gap-2 mb-6" data-testid="list-study-choices">
          {studies.isLoading ? <Skeleton className="h-9 w-80 rounded-full" /> : (studies.data ?? []).map((c) => {
            const active = lat === c.latitude && lon === c.longitude;
            return (
              <Link key={c.name} href={`/environment?latitude=${c.latitude}&longitude=${c.longitude}&name=${encodeURIComponent(`${c.name}, ${c.country}`)}`}
                className={cn("rounded-full px-4 py-2 text-sm font-medium", active ? "bg-primary text-primary-foreground" : "border border-input hover:bg-secondary")} data-testid={`link-study-${c.name}`}>{c.name}</Link>
            );
          })}
        </div>
        {lat !== undefined && lon !== undefined ? <EnvironmentAnalysis key={`${lat},${lon}`} latitude={lat} longitude={lon} />
          : studies.isLoading ? <Skeleton className="h-80 rounded-3xl" />
          : <p className="text-muted-foreground">Choose a location on the map to explore.</p>}
      </div>
    </Shell>
  );
}
