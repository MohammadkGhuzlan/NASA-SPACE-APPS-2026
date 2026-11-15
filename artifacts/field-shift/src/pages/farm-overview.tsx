import type { ReactNode } from "react";
import { EnvironmentAnalysis } from "@/components/environment-analysis";
import { Measurements, FeatureInputs } from "@/components/measurements";
import { Link, useParams } from "wouter";
import { Pencil, Route as RouteIcon } from "lucide-react";
import { useGetFarm, type Farm } from "@workspace/api-client-react";
import { Shell, Tag } from "@/components/shell";
import { LocationMap } from "@/components/location-map";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { fmtCoord, goalLabel, irrigationLabel } from "@/lib/field";

export function FarmMissing({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-3xl border border-card-border bg-card p-10 text-center">
      <h1 className="font-display text-3xl text-primary">This farm could not be loaded</h1>
      <p className="text-muted-foreground mt-2">It may belong to another session, or the service is unreachable.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Button className="rounded-full" onClick={onRetry} data-testid="button-retry">Retry</Button>
        <Link href="/farms" className="rounded-full border border-input px-5 py-2 text-sm font-semibold hover:bg-secondary">Back to farms</Link>
      </div>
    </div>
  );
}

function FarmerFacts({ farm }: { farm: Farm }) {
  const rows: [string, ReactNode][] = [
    ["Current crop", farm.currentCrop],
    ["Crop history", farm.cropHistory || "Not provided"],
    ["Irrigation", irrigationLabel[farm.irrigation]],
    ["Goal", goalLabel[farm.goal]],
    ["Soil type", farm.soilType || "Not provided"],
    ["Soil moisture", farm.soilMoisture != null ? `${farm.soilMoisture}% vol.` : "Not measured"],
    ["Soil pH", farm.soilPh != null ? farm.soilPh : "Not measured"],
    ["Farm size", farm.farmSize != null ? `${farm.farmSize} ha` : "Not provided"],
    ["Water constraints", farm.waterConstraints || "Not provided"],
    ["Water resources", farm.waterResources || "Not provided"],
    ["Agricultural constraints", farm.agriculturalConstraints || "Not provided"],
  ];
  return (
    <div className="rounded-3xl border border-card-border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-display text-2xl text-primary">Farm profile</h2><Tag kind="farmer">Farmer reported</Tag></div>
      <p className="mt-1 text-xs text-muted-foreground">Blank fields are shown as not provided or not measured. Profile values are not independently verified.</p>
      <dl className="mt-4 divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="py-2.5 grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-3 text-sm">
            <dt className="text-muted-foreground">{k}</dt><dd className="font-medium break-words">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function FarmOverview() {
  const id = Number(useParams<{ id: string }>().id);
  const farm = useGetFarm(id);

  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        {farm.isLoading ? (
          <div className="space-y-5"><Skeleton className="h-20 w-1/2 rounded-2xl" /><Skeleton className="h-80 rounded-3xl" /></div>
        ) : farm.isError || !farm.data ? (
          <FarmMissing onRetry={() => farm.refetch()} />
        ) : (
          <>
            <div className="rise flex flex-col md:flex-row md:items-end justify-between gap-5 pb-8">
              <div>
                <Link href="/farms" className="font-mono text-xs uppercase tracking-[0.18em] text-accent hover:underline">Saved farms /</Link>
                <h1 className="font-display text-4xl md:text-6xl text-primary mt-2" data-testid="text-farm-name">{farm.data.name}</h1>
                <p className="text-muted-foreground mt-2">{farm.data.locationName} · <span className="font-mono text-xs">{fmtCoord(farm.data.latitude, farm.data.longitude)}</span></p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`/farms/${id}/edit`} className="inline-flex items-center gap-2 rounded-full border border-input px-5 py-2.5 text-sm font-semibold hover:bg-secondary transition-colors" data-testid="link-edit"><Pencil className="h-4 w-4" />Edit profile</Link>
                <Link href={`/farms/${id}/planner`} className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground active:scale-[.97] transition-transform" data-testid="link-planner"><RouteIcon className="h-4 w-4" />Rotation planner</Link>
              </div>
            </div>
            <div className="grid lg:grid-cols-[1.6fr_1fr] items-start gap-6">
              <div className="space-y-6 min-w-0">
                <EnvironmentAnalysis latitude={farm.data.latitude} longitude={farm.data.longitude} />
              </div>
              <div className="space-y-6">
                <div className="overflow-hidden rounded-3xl border border-card-border">
                  <LocationMap point={[farm.data.latitude, farm.data.longitude]} drawing={false} closed
                    vertices={farm.data.boundary?.coordinates[0]?.slice(0, -1).map(([lo, la]) => [la, lo] as [number, number]) ?? []}
                    className="h-60 w-full" />
                </div>
                <FarmerFacts farm={farm.data} />
                <Measurements farmId={id} />
                <FeatureInputs farmId={id} />
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
