import { useMemo, useState, type FormEvent, type ReactElement } from "react";
import { ExternalLink, MapPin } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  useGetEnvironmentalHistory, useGetEnvironmentalSummary, useGetSoilProperties, useGetSoilWetness,
  getGetEnvironmentalHistoryQueryKey, getGetEnvironmentalSummaryQueryKey, getGetSoilPropertiesQueryKey, getGetSoilWetnessQueryKey,
  type ClimateAggregate, type EnvironmentalSummary, type SoilProperties,
} from "@workspace/api-client-react";
import { Tag } from "@/components/shell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { axisTick, errMessage, fmtNum, Note, Section, SectionSkeleton, tooltipStyle, Unavailable, Warnings } from "@/components/env-kit";

const YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025];
const LONG = { staleTime: 30 * 60 * 1000, retry: 1 };

const unitFor = (name: string) => {
  const n = name.toLowerCase();
  if (n.includes("wetness") || n.includes("gwet")) return "fraction";
  if (n.includes("rain") || n.includes("precip")) return "mm";
  if (n.includes("humid")) return "%";
  if (n.includes("day") || n.includes("spell")) return "days";
  return "°C";
};
const tipFmt = (v: unknown, n: unknown) => {
  const name = String(n);
  const u = unitFor(name);
  return [typeof v === "number" ? (u === "fraction" ? `${v.toFixed(3)} (0–1)` : `${v.toFixed(u === "days" ? 0 : 1)} ${u}`) : "no value", name];
};

function Chart({ children, h = 300, testid }: { children: ReactElement; h?: number; testid?: string }) {
  return <div style={{ height: h }} className="-ml-2" data-testid={testid}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>;
}

function coverage(a: ClimateAggregate, p: string) {
  const v = a.validDays?.[p];
  return typeof v === "number" ? `${v}/${a.expectedDays}` : `?/${a.expectedDays}`;
}

/* ---------- summary-driven sections ---------- */

function AnnualSection({ s }: { s: EnvironmentalSummary }) {
  const rows = s.annual;
  return (
    <Section eyebrow="Annual comparison · 2019–2025" title="Year by year at this grid cell" testid="section-annual">
      <div className="overflow-x-auto -mx-1">
        <table className="w-full min-w-[720px] text-sm" data-testid="table-annual">
          <thead><tr className="text-left font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
            {["Year", "Mean °C", "Max °C", "Min °C", "Rain mm", "Rain anomaly mm", "RH %", `>${s.hotThreshold} °C days`, ">30 °C", ">35 °C", "Longest dry spell", "Coverage (T2M)"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-border">
            {rows.map((a) => (
              <tr key={a.period} data-testid={`row-annual-${a.period}`}>
                <td className="py-2 pr-3 font-mono">{a.period}</td>
                <td className="pr-3">{fmtNum(a.T2M)}</td>
                <td className="pr-3">{fmtNum(a.maximumTemperature)}</td>
                <td className="pr-3">{fmtNum(a.minimumTemperature)}</td>
                <td className="pr-3">{fmtNum(a.PRECTOTCORR)}</td>
                <td className={cn("pr-3", typeof a.PRECTOTCORRAnomaly === "number" && (a.PRECTOTCORRAnomaly < 0 ? "text-accent" : "text-[hsl(200_45%_30%)]"))}>{typeof a.PRECTOTCORRAnomaly === "number" ? `${a.PRECTOTCORRAnomaly > 0 ? "+" : ""}${a.PRECTOTCORRAnomaly.toFixed(1)}` : "no value"}</td>
                <td className="pr-3">{fmtNum(a.RH2M)}</td>
                <td className="pr-3">{a.hotDays ?? "no value"}</td>
                <td className="pr-3">{a.hotDays30 ?? "no value"}</td>
                <td className="pr-3">{a.hotDays35 ?? "no value"}</td>
                <td className="pr-3">{typeof a.longestDrySpell === "number" ? `${a.longestDrySpell} d` : "no value"}</td>
                <td className="pr-3 font-mono text-xs text-muted-foreground">{coverage(a, "T2M")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Note>Hot-day counts use strictly greater than the threshold on daily maximum temperature. Dry spell: {s.drySpellDefinition}. Rain anomaly is the departure from the complete-year reference ({s.referencePeriod}). Coverage is valid days over expected days.</Note>
    </Section>
  );
}

function MonthlySection({ s }: { s: EnvironmentalSummary }) {
  return (
    <Section eyebrow="Monthly profile · 84 months" title="Temperature range and rainfall" testid="section-monthly">
      <Chart h={340} testid="chart-monthly">
        <ComposedChart data={s.monthly}>
          <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} minTickGap={24} />
          <YAxis yAxisId="r" tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={62} />
          <YAxis yAxisId="t" orientation="right" tick={axisTick} axisLine={false} tickLine={false} unit="°C" width={46} />
          <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} labelFormatter={(l) => `Month ${l}`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar yAxisId="r" dataKey="PRECTOTCORR" name="Rainfall total" fill="hsl(var(--chart-1))" radius={[3, 3, 0, 0]} />
          <Line yAxisId="t" dataKey="T2M_MAX" name="Mean daily high" stroke="hsl(var(--chart-2))" dot={false} strokeWidth={1.8} connectNulls={false} />
          <Line yAxisId="t" dataKey="T2M" name="Mean temperature" stroke="hsl(var(--chart-5))" dot={false} strokeWidth={1.8} connectNulls={false} />
          <Line yAxisId="t" dataKey="T2M_MIN" name="Mean daily low" stroke="hsl(var(--chart-3))" dot={false} strokeWidth={1.8} connectNulls={false} />
        </ComposedChart>
      </Chart>
      <Note>Monthly means of daily values; rainfall is the monthly total in mm. Gaps mean the month had no valid data, not zero.</Note>
    </Section>
  );
}

function SeasonalSection({ s }: { s: EnvironmentalSummary }) {
  return (
    <Section eyebrow="Seasonal" title="Seasonal rainfall and humidity" testid="section-seasonal">
      <Chart h={300} testid="chart-seasonal">
        <ComposedChart data={s.seasonal}>
          <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} minTickGap={16} />
          <YAxis yAxisId="r" tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={62} />
          <YAxis yAxisId="h" orientation="right" domain={[0, 100]} tick={axisTick} axisLine={false} tickLine={false} unit="%" width={42} />
          <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar yAxisId="r" dataKey="PRECTOTCORR" name="Rainfall total" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
          <Line yAxisId="h" dataKey="RH2M" name="Relative humidity" stroke="hsl(var(--chart-4))" strokeWidth={2} dot={{ r: 2 }} connectNulls={false} />
        </ComposedChart>
      </Chart>
    </Section>
  );
}

function HeatSection({ s }: { s: EnvironmentalSummary }) {
  return (
    <Section eyebrow="Heat history" title="Days above temperature thresholds" testid="section-heat">
      <Chart h={280} testid="chart-heat">
        <BarChart data={s.annual}>
          <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} />
          <YAxis tick={axisTick} axisLine={false} tickLine={false} unit=" d" width={48} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} labelFormatter={(l) => `Year ${l}`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="hotDays30" name="Days > 30 °C" fill="hsl(var(--chart-4))" radius={[4, 4, 0, 0]} />
          <Bar dataKey="hotDays35" name="Days > 35 °C" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} />
          <Bar dataKey="hotDays" name={`Days > ${s.hotThreshold} °C (custom)`} fill="hsl(var(--chart-5))" radius={[4, 4, 0, 0]} />
        </BarChart>
      </Chart>
    </Section>
  );
}

function AnomalySection({ s }: { s: EnvironmentalSummary }) {
  return (
    <Section eyebrow="Departures" title="Rainfall and wetness anomalies" testid="section-anomaly">
      <div className="grid md:grid-cols-2 gap-6">
        <div>
          <p className="text-sm font-semibold">Annual rainfall anomaly (mm)</p>
          <Chart h={240} testid="chart-rain-anomaly">
            <BarChart data={s.annual}>
              <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={62} />
              <ReferenceLine y={0} stroke="hsl(var(--foreground)/.4)" />
              <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} />
              <Bar dataKey="PRECTOTCORRAnomaly" name="Rainfall anomaly" fill="hsl(var(--chart-1))" radius={[4, 4, 4, 4]} />
            </BarChart>
          </Chart>
        </div>
        <div>
          <p className="text-sm font-semibold">Annual modeled wetness anomaly (fraction 0–1)</p>
          <Chart h={240} testid="chart-wetness-anomaly">
            <BarChart data={s.annual}>
              <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} />
              <YAxis tick={axisTick} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => v.toFixed(2)} />
              <ReferenceLine y={0} stroke="hsl(var(--foreground)/.4)" />
              <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="GWETTOPAnomaly" name="Surface wetness anomaly" fill="hsl(var(--chart-3))" />
              <Bar dataKey="GWETROOTAnomaly" name="Root-zone wetness anomaly" fill="hsl(var(--chart-5))" />
            </BarChart>
          </Chart>
        </div>
      </div>
      <Note>Anomalies compare each year against the mean of complete reference years ({s.referencePeriod}). Reference year counts: rainfall {s.annual[0]?.PRECTOTCORRReferenceYears ?? "n/a"}, surface wetness {s.annual[0]?.GWETTOPReferenceYears ?? "n/a"}, root-zone wetness {s.annual[0]?.GWETROOTReferenceYears ?? "n/a"}. Wetness anomalies stay in fraction units.</Note>
    </Section>
  );
}

function ProvenanceSection({ s }: { s: EnvironmentalSummary }) {
  return (
    <Section eyebrow="Provenance" title="Where these numbers come from" testid="section-provenance">
      <div className="grid sm:grid-cols-2 gap-3">
        {s.provenance.map((p) => (
          <div key={p.parameter} className="rounded-2xl border border-border p-4 text-sm" data-testid={`card-provenance-${p.parameter}`}>
            <div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-semibold">{p.parameter}</span><span className="font-mono text-[10.5px] text-muted-foreground">{p.unit}</span></div>
            <p className="mt-1">{p.source} · {p.product}</p>
            <p className="text-xs text-muted-foreground">{p.classification} · retrieved or imported {p.retrievedAt}</p>
            <p className="text-xs text-muted-foreground">Original download date: {typeof p.metadata?.originalRetrievalDate === "string" ? p.metadata.originalRetrievalDate : "not recorded"} · time standard: {typeof p.metadata?.timeStandard === "string" ? p.metadata.timeStandard : "unknown"}</p>
            {p.sourceUrl && <a href={p.sourceUrl} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">Source<ExternalLink className="h-3 w-3" /></a>}
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Location key {s.location.key} · matching: {s.location.matchingPolicy} · parameters: {s.availableParameters.join(", ") || "none"}</p>
    </Section>
  );
}

/* ---------- daily history ---------- */

function DailySection({ latitude, longitude }: { latitude: number; longitude: number }) {
  const [year, setYear] = useState(2025);
  const params = { latitude, longitude, year };
  const h = useGetEnvironmentalHistory(params, { query: { queryKey: getGetEnvironmentalHistoryQueryKey(params), ...LONG } });
  const picker = (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Year">
      {YEARS.map((y) => (
        <button key={y} onClick={() => setYear(y)} data-testid={`button-year-${y}`}
          className={cn("rounded-full px-3 py-1 font-mono text-xs transition-colors", y === year ? "bg-primary text-primary-foreground" : "border border-input hover:bg-secondary")}>{y}</button>
      ))}
    </div>
  );
  return (
    <Section eyebrow="Daily records" title={`Daily highs, lows and rain in ${year}`} actions={picker} testid="section-daily">
      {h.isLoading ? <SectionSkeleton note="Loading daily records for the selected year." />
        : h.isError || !h.data ? <Unavailable title="Daily records unavailable" detail={errMessage(h.error)} onRetry={() => h.refetch()} testid="daily" />
        : !h.data.daily.length ? <Unavailable title="No daily records" detail={`No daily rows exist for ${year} at this location.`} />
        : (
          <>
            <Chart h={300} testid="chart-daily-temp">
              <ComposedChart data={h.data.daily}>
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="date" tick={axisTick} axisLine={false} tickLine={false} minTickGap={40} tickFormatter={(d: string) => d.slice(5)} />
                <YAxis yAxisId="t" tick={axisTick} axisLine={false} tickLine={false} unit="°C" width={46} />
                <YAxis yAxisId="r" orientation="right" tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={52} />
                <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} labelFormatter={(l) => `Date ${l}`} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="r" dataKey="PRECTOTCORR" name="Daily rainfall" fill="hsl(var(--chart-1))" />
                <Line yAxisId="t" dataKey="T2M_MAX" name="Daily high" stroke="hsl(var(--chart-2))" dot={false} strokeWidth={1.3} connectNulls={false} />
                <Line yAxisId="t" dataKey="T2M_MIN" name="Daily low" stroke="hsl(var(--chart-3))" dot={false} strokeWidth={1.3} connectNulls={false} />
              </ComposedChart>
            </Chart>
            <p className="mt-6 text-sm font-semibold">Daily rainfall versus modeled wetness</p>
            <Chart h={260} testid="chart-daily-wetness">
              <ComposedChart data={h.data.daily}>
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="date" tick={axisTick} axisLine={false} tickLine={false} minTickGap={40} tickFormatter={(d: string) => d.slice(5)} />
                <YAxis yAxisId="w" domain={[0, 1]} tick={axisTick} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => v.toFixed(1)} />
                <YAxis yAxisId="r" orientation="right" tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={52} />
                <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} labelFormatter={(l) => `Date ${l}`} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="r" dataKey="PRECTOTCORR" name="Daily rainfall" fill="hsl(var(--chart-1)/.6)" />
                <Line yAxisId="w" dataKey="GWETTOP" name="Surface wetness" stroke="hsl(var(--chart-3))" dot={false} strokeWidth={1.5} connectNulls={false} />
                <Line yAxisId="w" dataKey="GWETROOT" name="Root-zone wetness" stroke="hsl(var(--chart-5))" dot={false} strokeWidth={1.5} connectNulls={false} />
              </ComposedChart>
            </Chart>
            <div className="mt-3"><Warnings items={[
              "Alignment caution: the original time standard of the climate CSV is unknown while wetness records are in UTC. Same-day pairs may be offset by up to a day; read daily co-movement loosely.",
              ...(h.data.warning ? [h.data.warning] : []),
            ]} testid="list-daily-warnings" /></div>
            <Note>Units: {Object.entries(h.data.units).map(([k, v]) => `${k} ${v}`).join(" · ")}. Wetness is a unitless 0–1 modeled fraction, not volumetric moisture.</Note>
          </>
        )}
    </Section>
  );
}

/* ---------- wetness ---------- */

function WetnessSection({ latitude, longitude, summary }: { latitude: number; longitude: number; summary?: EnvironmentalSummary }) {
  const params = { latitude, longitude };
  const w = useGetSoilWetness(params, { query: { queryKey: getGetSoilWetnessQueryKey(params), ...LONG } });
  const combined = useMemo(() => {
    if (!w.data) return [];
    const rain = new Map((summary?.monthly ?? []).map((m) => [m.period, m.PRECTOTCORR]));
    return w.data.monthly.map((m) => ({ period: m.period, GWETTOP: m.GWETTOP, GWETROOT: m.GWETROOT, PRECTOTCORR: rain.get(m.period) ?? null }));
  }, [w.data, summary]);
  return (
    <Section eyebrow="Modeled soil wetness" title="Surface and root-zone wetness history" testid="section-wetness"
      actions={w.data ? <Tag kind="observed">{w.data.classification}</Tag> : undefined}>
      {w.isLoading ? <SectionSkeleton />
        : w.isError || !w.data ? <Unavailable title="Wetness unavailable" detail={errMessage(w.error)} onRetry={() => w.refetch()} testid="wetness" />
        : !w.data.monthly.length ? <Unavailable title="No wetness records" detail="No modeled wetness values exist for this location." />
        : (
          <>
            <Chart h={300} testid="chart-wetness">
              <ComposedChart data={combined}>
                <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} minTickGap={24} />
                <YAxis yAxisId="w" domain={[0, 1]} tick={axisTick} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => v.toFixed(1)} />
                {summary && <YAxis yAxisId="r" orientation="right" tick={axisTick} axisLine={false} tickLine={false} unit=" mm" width={56} />}
                <Tooltip contentStyle={tooltipStyle} formatter={tipFmt} labelFormatter={(l) => `Month ${l}`} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {summary && <Bar yAxisId="r" dataKey="PRECTOTCORR" name="Monthly rainfall" fill="hsl(var(--chart-1)/.45)" />}
                <Line yAxisId="w" dataKey="GWETTOP" name="Surface wetness" stroke="hsl(var(--chart-3))" dot={false} strokeWidth={2} connectNulls={false} />
                <Line yAxisId="w" dataKey="GWETROOT" name="Root-zone wetness" stroke="hsl(var(--chart-5))" dot={false} strokeWidth={2} connectNulls={false} />
              </ComposedChart>
            </Chart>
            {w.data.seasonal.length > 0 && (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[420px] text-sm" data-testid="table-wetness-seasonal">
                  <thead><tr className="text-left font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground"><th className="py-1.5">Season</th><th>Surface</th><th>Root zone</th><th>Valid days</th></tr></thead>
                  <tbody className="divide-y divide-border">
                    {w.data.seasonal.map((r) => <tr key={r.period}><td className="py-1.5 font-mono">{r.period}</td><td>{fmtNum(r.GWETTOP, 3)}</td><td>{fmtNum(r.GWETROOT, 3)}</td><td className="font-mono text-xs text-muted-foreground">{coverage(r, "GWETTOP")}</td></tr>)}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-3"><Warnings items={w.data.warnings} /></div>
            <Note>Unit: {w.data.unit}. Values are modeled 0–1 fractions of a grid cell, not field moisture readings and not percentages. Rainfall bars are monthly totals; monthly aggregation reduces but does not remove the time-standard uncertainty between sources.</Note>
          </>
        )}
    </Section>
  );
}

/* ---------- soil ---------- */

const SOIL_LABEL: Record<string, string> = { clay_pct: "Clay", sand_pct: "Sand", silt_pct: "Silt", ph: "pH", soc_g_kg: "Soil organic carbon" };

function haversine(a: number, b: number, c: number, d: number) {
  const r = (x: number) => (x * Math.PI) / 180;
  const dl = r(c - a), dn = r(d - b);
  const h = Math.sin(dl / 2) ** 2 + Math.cos(r(a)) * Math.cos(r(c)) * Math.sin(dn / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

export function SoilSection({ latitude, longitude }: { latitude: number; longitude: number }) {
  const params = { latitude, longitude };
  const q = useGetSoilProperties(params, { query: { queryKey: getGetSoilPropertiesQueryKey(params), ...LONG } });
  return (
    <Section eyebrow="Soil estimate · 0–5 cm" title="SoilGrids proxy properties" testid="section-soil">
      {q.isLoading ? <SectionSkeleton /> : q.isError || !q.data ? <Unavailable title="Soil estimate unavailable" detail={errMessage(q.error)} onRetry={() => q.refetch()} testid="soil" /> : <SoilBody d={q.data} />}
    </Section>
  );
}

function SoilBody({ d }: { d: SoilProperties }) {
  const e = d.estimate;
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-[hsl(38_70%_50%/.4)] bg-[hsl(38_70%_50%/.1)] p-4 text-sm leading-relaxed" data-testid="text-soil-notice">{d.notice}</div>
      {!e ? <Unavailable title="No soil estimate for this location" detail="Soil proxies exist only for the study regions. No other region's values are substituted." /> : (
        <>
          <div className="flex flex-wrap gap-2"><Tag kind="unassessed">{e.classification}</Tag><Tag kind="observed">Depth {e.depthCm} cm</Tag></div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {Object.entries(e.properties).map(([k, v]) => (
              <div key={k} className="rounded-2xl border border-border p-3" data-testid={`text-soil-${k}`}>
                <p className="text-xs text-muted-foreground">{SOIL_LABEL[k] ?? k}</p>
                <p className="font-display text-2xl text-primary">{v.value ?? "n/a"}<span className="text-xs font-sans text-muted-foreground ml-1">{v.unit}</span></p>
                <p className="font-mono text-[10px] text-muted-foreground">{v.quality}</p>
              </div>
            ))}
          </div>
          <div className="grid sm:grid-cols-3 gap-3 text-sm">
            <div className="rounded-2xl bg-secondary/60 p-3"><p className="text-xs text-muted-foreground flex items-center gap-1"><MapPin className="h-3 w-3" />Requested position</p><p className="font-mono text-xs mt-1">{e.originalLatitude.toFixed(5)}, {e.originalLongitude.toFixed(5)}</p></div>
            <div className="rounded-2xl bg-secondary/60 p-3"><p className="text-xs text-muted-foreground flex items-center gap-1"><MapPin className="h-3 w-3" />Sampled position</p><p className="font-mono text-xs mt-1">{e.sampleLatitude.toFixed(5)}, {e.sampleLongitude.toFixed(5)}</p></div>
            <div className="rounded-2xl bg-secondary/60 p-3" data-testid="text-soil-offset"><p className="text-xs text-muted-foreground">Distance</p><p className="text-xs mt-1">Source reported <b>{e.offsetKm.toFixed(3)} km</b></p><p className="text-xs">Computed from coordinates <b>{(typeof e.provenance.calculatedOffsetKm === "number" ? e.provenance.calculatedOffsetKm : haversine(e.originalLatitude, e.originalLongitude, e.sampleLatitude, e.sampleLongitude)).toFixed(3)} km</b></p>
              {e.provenance.quality === "distance_discrepancy" && <p className="text-xs text-accent font-semibold mt-1">Distances disagree; both shown as supplied.</p>}</div>
          </div>
          <details className="text-xs text-muted-foreground"><summary className="cursor-pointer font-semibold">Raw provenance record</summary>
            <dl className="mt-2 space-y-1">{Object.entries(e.provenance).map(([k, v]) => <div key={k} className="grid grid-cols-[minmax(110px,auto)_1fr] gap-x-3"><dt className="font-mono">{k}</dt><dd className="break-words">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>)}</dl>
            <p className="mt-2">Retrieved or imported {e.retrievedAt} (ingestion time; original download date {typeof e.provenance.originalRetrievalDate === "string" ? e.provenance.originalRetrievalDate : "not recorded"})</p>
          </details>
        </>
      )}
      <Warnings items={d.warnings} testid="list-soil-warnings" />
    </div>
  );
}

/* ---------- top-level ---------- */

export function EnvironmentAnalysis({ latitude, longitude }: { latitude: number; longitude: number }) {
  const [hot, setHot] = useState("32");
  const [dry, setDry] = useState("1");
  const [applied, setApplied] = useState({ hot: 32, dry: 1 });
  const [formErr, setFormErr] = useState("");
  const params = { latitude, longitude, hot_threshold: applied.hot, dry_threshold: applied.dry };
  const s = useGetEnvironmentalSummary(params, { query: { queryKey: getGetEnvironmentalSummaryQueryKey(params), ...LONG } });

  const apply = (e: FormEvent) => {
    e.preventDefault();
    const h = Number(hot), d = Number(dry);
    if (!hot || !dry || Number.isNaN(h) || Number.isNaN(d) || h < -20 || h > 60 || d < 0 || d > 50) { setFormErr("Heat threshold must be -20 to 60 °C; dry threshold 0 to 50 mm."); return; }
    setFormErr(""); setApplied({ hot: h, dry: d });
  };

  return (
    <div className="space-y-6">
      <form onSubmit={apply} className="rounded-3xl border border-card-border bg-card p-5 flex flex-col md:flex-row md:items-end gap-4" data-testid="form-thresholds">
        <div className="flex-1">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Thresholds</p>
          <p className="text-sm text-muted-foreground mt-1">Choose the heat level that matters to you and the daily rainfall below which a day counts as dry.</p>
        </div>
        <label className="text-xs font-semibold">Heat threshold (°C)<Input value={hot} onChange={(e) => setHot(e.target.value)} inputMode="decimal" className="mt-1 w-32" data-testid="input-hot-threshold" /></label>
        <label className="text-xs font-semibold">Dry day below (mm)<Input value={dry} onChange={(e) => setDry(e.target.value)} inputMode="decimal" className="mt-1 w-32" data-testid="input-dry-threshold" /></label>
        <Button type="submit" className="rounded-full" data-testid="button-apply-thresholds">Apply</Button>
        {formErr && <p className="text-sm text-destructive md:basis-full" role="alert">{formErr}</p>}
      </form>

      {s.isLoading ? (
        <div className="space-y-4">
          <SectionSkeleton note="Building the 2019–2025 summary. For a location not yet cached this can take up to about 100 seconds while daily records are fetched and aggregated. Leave this page open; other sections below load independently." />
          <SectionSkeleton />
        </div>
      ) : s.isError || !s.data ? (
        <Unavailable title="Climate summary unavailable" detail={`${errMessage(s.error)} Uncached locations can time out on first request; retrying often succeeds once the data is cached.`} onRetry={() => s.refetch()} testid="summary" />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2" data-testid="status-summary">
            <span className="font-mono text-xs uppercase tracking-wider">{s.data.status}</span><Tag kind="observed">Gridded estimate</Tag>
            <span className="text-xs text-muted-foreground">{s.data.location.name} · {s.data.monthly.length} months · {s.data.annual.length} years</span>
          </div>
          <Warnings items={s.data.warnings} testid="list-summary-warnings" />
          {s.data.annual.length ? <AnnualSection s={s.data} /> : <Unavailable title="No annual aggregates" detail="No complete annual values for this location." />}
          {s.data.monthly.length ? <MonthlySection s={s.data} /> : <Unavailable title="No monthly aggregates" detail="No monthly values were returned." />}
          {s.data.seasonal.length > 0 && <SeasonalSection s={s.data} />}
          {s.data.annual.length > 0 && <HeatSection s={s.data} />}
          {s.data.annual.length > 0 && <AnomalySection s={s.data} />}
        </>
      )}
      <DailySection latitude={latitude} longitude={longitude} />
      <WetnessSection latitude={latitude} longitude={longitude} summary={s.data} />
      <SoilSection latitude={latitude} longitude={longitude} />
      {s.data && s.data.provenance.length > 0 && <ProvenanceSection s={s.data} />}
      <Section eyebrow="Not connected" title="Satellite products not in use" testid="section-unavailable-products">
        <div className="flex flex-wrap gap-2"><Tag kind="unassessed">SMAP soil moisture · unavailable</Tag><Tag kind="unassessed">MODIS vegetation · unavailable</Tag></div>
        <Note>These products are not connected. Nothing is estimated in their place.</Note>
      </Section>
    </div>
  );
}
