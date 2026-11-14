import type { ReactNode } from "react";
import { Link, useParams } from "wouter";
import { AlertTriangle, ExternalLink, Pencil, RefreshCw, Route as RouteIcon } from "lucide-react";
import { format } from "date-fns";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useGetEnvironment, useGetFarm, type Environment, type Farm } from "@workspace/api-client-react";
import { Shell, Tag } from "@/components/shell";
import { LocationMap } from "@/components/location-map";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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

function Stat({ label, value, unit, tag, note, testid }: { label: string; value: ReactNode; unit?: string; tag: ReactNode; note: string; testid: string }) {
  return (
    <div className="rounded-3xl border border-card-border bg-card p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{label}</span>{tag}</div>
      <p className="font-display text-4xl text-primary" data-testid={testid}>{value}{unit && <span className="text-base text-muted-foreground ml-1 font-sans">{unit}</span>}</p>
      <p className="text-xs text-muted-foreground leading-relaxed">{note}</p>
    </div>
  );
}

function EnvPanel({ env }: { env: Environment }) {
  const hasData = env.monthly.some((m) => m.rainfall !== null || m.temperature !== null);
  const statusStyle = { available: "bg-chart-3", partial: "bg-chart-4", unavailable: "bg-destructive" }[env.status];
  const totalRain = env.monthly.every((m) => m.rainfall !== null) && env.monthly.length ? env.monthly.reduce((s, m) => s + (m.rainfall ?? 0), 0) : null;
  return (
    <div className="space-y-5">
      <div className="rounded-3xl border border-card-border bg-card p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className={cn("h-2.5 w-2.5 rounded-full", statusStyle)} />
              <span className="font-mono text-xs uppercase tracking-wider" data-testid="status-environment">{env.status}</span>
              <Tag kind="observed">Observed</Tag>
            </div>
            <h2 className="font-display text-2xl text-primary mt-2">Monthly rainfall and temperature</h2>
            <p className="text-sm text-muted-foreground">{env.dateRange}{totalRain !== null && <> · annual rain {totalRain.toFixed(1)} mm</>}</p>
          </div>
          <a href={env.sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline" data-testid="link-env-source">{env.source}<ExternalLink className="h-3.5 w-3.5" /></a>
        </div>
        {hasData ? (
          <div className="h-[320px] mt-6 -ml-3" data-testid="chart-climate">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={env.monthly}>
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="r" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} unit=" mm" width={62} />
                <YAxis yAxisId="t" orientation="right" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} axisLine={false} tickLine={false} unit="°C" width={46} />
                <Tooltip contentStyle={{ borderRadius: 14, border: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }}
                  formatter={(v, n) => (typeof v !== "number" ? ["missing", String(n)] : [String(n).startsWith("Rain") ? `${v.toFixed(1)} mm` : `${v.toFixed(1)} °C`, String(n)])} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="r" dataKey="rainfall" name="Rainfall" fill="hsl(var(--chart-1))" radius={[6, 6, 0, 0]} maxBarSize={28} />
                <Line yAxisId="t" dataKey="temperature" name="Mean temperature" stroke="hsl(var(--chart-2))" strokeWidth={2.5} dot={{ r: 3 }} connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border-2 border-dashed border-input furrows p-10 text-center">
            <p className="font-display text-xl text-primary">No observations to chart</p>
            <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">The data source did not return monthly values for this location. Nothing has been estimated in their place.</p>
          </div>
        )}
        {env.warnings.length > 0 && (
          <ul className="mt-5 space-y-2" data-testid="list-warnings">
            {env.warnings.map((w, i) => (
              <li key={i} className="flex gap-2 rounded-xl bg-[hsl(38_70%_50%/.12)] px-3 py-2 text-sm text-[hsl(30_60%_28%)]"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />{w}</li>
            ))}
          </ul>
        )}
        {env.fetchedAt && <p className="mt-4 font-mono text-[11px] text-muted-foreground">Retrieved {format(new Date(env.fetchedAt), "d MMM yyyy, HH:mm")}</p>}
      </div>
      <div className="grid sm:grid-cols-3 gap-4">
        <Stat label="Heat days" testid="text-heat-days" value={env.heatDays ?? "—"} unit={env.heatDays !== null ? "days" : undefined}
          tag={env.heatDays !== null ? <Tag kind="observed">Observed</Tag> : <Tag kind="unassessed">Unavailable</Tag>}
          note="Days in the period with daily maximum temperature at or above 35 °C." />
        <Stat label="Satellite soil moisture" testid="text-sat-moisture" value={env.soilMoisture ?? "—"} unit={env.soilMoisture !== null ? "%" : undefined}
          tag={env.soilMoisture !== null ? <Tag kind="observed">Observed</Tag> : <Tag kind="unassessed">Not connected</Tag>}
          note="No satellite soil moisture product is connected yet. Your own measurement is shown separately." />
        <Stat label="Vegetation index" testid="text-vegetation" value={env.vegetationIndex ?? "—"}
          tag={env.vegetationIndex !== null ? <Tag kind="observed">Observed</Tag> : <Tag kind="unassessed">Not connected</Tag>}
          note="No vegetation index source is connected yet." />
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
  ];
  return (
    <div className="rounded-3xl border border-card-border bg-card p-6">
      <div className="flex items-center justify-between"><h2 className="font-display text-2xl text-primary">Farmer reported</h2><Tag kind="farmer">Your input</Tag></div>
      <dl className="mt-4 divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="py-2.5 grid grid-cols-[130px_1fr] gap-3 text-sm">
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
  const env = useGetEnvironment(id);

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
            <div className="grid lg:grid-cols-[1.6fr_1fr] gap-6">
              <div>
                {env.isLoading ? (
                  <div className="space-y-4">
                    <div className="rounded-3xl border border-card-border bg-card p-6"><Skeleton className="h-6 w-60" /><Skeleton className="h-[300px] mt-6 rounded-2xl" /><p className="text-xs text-muted-foreground mt-3">Requesting daily records from NASA POWER. This can take a few seconds.</p></div>
                    <div className="grid sm:grid-cols-3 gap-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-36 rounded-3xl" />)}</div>
                  </div>
                ) : env.isError || !env.data ? (
                  <div className="rounded-3xl border border-card-border bg-card p-8">
                    <p className="font-display text-2xl text-primary">Environmental data request failed</p>
                    <p className="text-sm text-muted-foreground mt-1">No values are shown rather than placeholders.</p>
                    <Button variant="outline" className="mt-4 rounded-full" onClick={() => env.refetch()} data-testid="button-retry-env"><RefreshCw className="h-4 w-4" />Retry</Button>
                  </div>
                ) : <EnvPanel env={env.data} />}
              </div>
              <div className="space-y-6">
                <div className="overflow-hidden rounded-3xl border border-card-border">
                  <LocationMap point={[farm.data.latitude, farm.data.longitude]} drawing={false} closed
                    vertices={farm.data.boundary?.coordinates[0]?.slice(0, -1).map(([lo, la]) => [la, lo] as [number, number]) ?? []}
                    className="h-60 w-full" />
                </div>
                <FarmerFacts farm={farm.data} />
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
