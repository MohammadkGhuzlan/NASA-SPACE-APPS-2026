import { useMemo, useState } from "react";
import { Link } from "wouter";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useCompareRegions, type ClimateAggregate } from "@workspace/api-client-react";
import { PageHead, Shell } from "@/components/shell";
import { axisTick, errMessage, Note, Section, SectionSkeleton, tooltipStyle, Unavailable } from "@/components/env-kit";
import { cn } from "@/lib/utils";

const COLORS = ["hsl(var(--chart-1))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))"];
const METRICS: { key: keyof ClimateAggregate; label: string; unit: string }[] = [
  { key: "PRECTOTCORR", label: "Annual rainfall", unit: "mm" },
  { key: "T2M", label: "Mean temperature", unit: "°C" },
  { key: "hotDays35", label: "Days > 35 °C", unit: "days" },
  { key: "hotDays30", label: "Days > 30 °C", unit: "days" },
  { key: "RH2M", label: "Relative humidity", unit: "%" },
  { key: "GWETROOT", label: "Root-zone wetness", unit: "fraction 0–1" },
  { key: "longestDrySpell", label: "Longest dry spell", unit: "days" },
];

export default function Compare() {
  const q = useCompareRegions({ query: { staleTime: 30 * 60 * 1000 } });
  const [metric, setMetric] = useState(0);
  const m = METRICS[metric]!;
  const data = useMemo(() => {
    const years = new Map<string, Record<string, number | string | null>>();
    for (const r of q.data ?? []) for (const a of r.summary?.annual ?? []) {
      const row = years.get(a.period) ?? { period: a.period };
      const v = a[m.key];
      row[r.studyId] = typeof v === "number" ? v : null;
      years.set(a.period, row);
    }
    return [...years.values()].sort((x, y) => String(x.period).localeCompare(String(y.period)));
  }, [q.data, m.key]);
  return (
    <Shell>
      <div className="mx-auto max-w-7xl px-5 py-12">
        <PageHead eyebrow="Four study regions" title={<>Regional <span className="italic text-accent">comparison</span></>}>
          Same grid-cell summaries, 2019 to 2025, side by side. Regional reference points, not farm centers.
        </PageHead>
        {q.isLoading ? <SectionSkeleton note="Assembling four regional summaries. Uncached regions can take up to about 100 seconds." />
          : q.isError || !q.data ? <Unavailable title="Comparison unavailable" detail={errMessage(q.error)} onRetry={() => q.refetch()} testid="compare" />
          : (
            <div className="space-y-6">
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {q.data.map((r, i) => (
                  <Link key={r.studyId} href={`/environment?latitude=${r.latitude}&longitude=${r.longitude}&name=${encodeURIComponent(r.name)}`} className="lift rounded-3xl border border-card-border bg-card p-5 block" data-testid={`card-region-${r.studyId}`}>
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLORS[i % 4] }} />
                    <p className="font-display text-xl text-primary mt-2">{r.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{r.latitude.toFixed(4)}, {r.longitude.toFixed(4)}</p>
                    <p className="text-xs mt-2">{r.summary ? `${r.summary.status} · ${r.summary.annual.length} years` : "Summary unavailable"}</p>
                    <p className="text-xs font-semibold text-accent mt-2">Explore in detail</p>
                  </Link>
                ))}
              </div>
              <Section eyebrow="Annual values" title={`${m.label} (${m.unit})`} testid="section-compare-chart"
                actions={<div className="flex flex-wrap gap-1">{METRICS.map((x, i) => <button key={x.key} onClick={() => setMetric(i)} data-testid={`button-metric-${x.key}`} className={cn("rounded-full px-3 py-1 text-xs", i === metric ? "bg-primary text-primary-foreground" : "border border-input hover:bg-secondary")}>{x.label}</button>)}</div>}>
                {data.length ? (
                  <div className="h-[340px] -ml-2" data-testid="chart-compare">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data}>
                        <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
                        <XAxis dataKey="period" tick={axisTick} axisLine={false} tickLine={false} />
                        <YAxis tick={axisTick} axisLine={false} tickLine={false} width={56} />
                        <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [typeof v === "number" ? `${v.toFixed(m.unit.startsWith("fraction") ? 3 : 1)} ${m.unit}` : "no value", String(n)]} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        {q.data.map((r, i) => <Bar key={r.studyId} dataKey={r.studyId} name={r.name} fill={COLORS[i % 4]} radius={[3, 3, 0, 0]} />)}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : <Unavailable title="No annual values" detail="None of the regions returned annual aggregates." />}
                <Note>Missing years appear as gaps. Hot-day counts are strictly above the threshold. Wetness is a modeled unitless fraction.</Note>
              </Section>
            </div>
          )}
      </div>
    </Shell>
  );
}
