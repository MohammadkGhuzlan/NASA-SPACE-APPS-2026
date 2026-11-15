import { useState, type FormEvent, type ReactNode } from "react";
import { AnalysisStatus } from "@/components/analysis-status";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { FileText, Loader2, RotateCcw } from "lucide-react";
import {
  getGetFarmingPlanQueryKey, getListFarmingPlansQueryKey, useGenerateFarmingPlan, useGetFarmingPlan, useListFarmingPlans,
  type FarmingPlanInput, type FarmingPlanReport,
} from "@workspace/api-client-react";
import { Tag } from "@/components/shell";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { Findings, RecordView, humanize } from "@/components/record-view";

const split = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
const fmt = (d: string) => { const t = new Date(d); return isNaN(t.getTime()) ? d : t.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); };

function errorMessage(e: unknown): string {
  const o = e as { data?: unknown; message?: string; status?: number } | null;
  const d = o?.data as Record<string, unknown> | string | undefined;
  if (typeof d === "string" && d) return d;
  if (d && typeof d === "object") {
    for (const k of ["error", "message", "detail"]) if (typeof d[k] === "string") return d[k] as string;
  }
  return o?.message || "The report could not be generated.";
}

function StatusTag({ s }: { s: string }) {
  const ok = s === "reference_based_plan" || s === "conditional_candidate";
  return <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider",
    ok ? "bg-secondary border-[hsl(92_20%_70%)] text-secondary-foreground" : "bg-[hsl(38_70%_50%/.14)] text-[hsl(30_60%_30%)] border-[hsl(38_70%_50%/.35)]")}>{humanize(s)}</span>;
}

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4"><h3 className="font-display text-2xl text-primary">{title}</h3>{aside}</div>
      {children}
    </section>
  );
}

const priorityOptions = [
  { value: "conserve_water", label: "Conserve water" },
  { value: "soil_health", label: "Support soil health" },
  { value: "reduce_risk", label: "Reduce rotation risks" },
  { value: "productivity", label: "Improve productivity" },
] as const;

function ReportForm({ farmId, defaultCrop, defaultPriority, onCreated }: { farmId: number; defaultCrop: string; defaultPriority: string; onCreated: (id: number) => void }) {
  const [plantingDate, setPlantingDate] = useState("");
  const [priority, setPriority] = useState(defaultPriority);
  const [rotation, setRotation] = useState(defaultCrop);
  const [previous, setPrevious] = useState("");
  const [excluded, setExcluded] = useState("");
  const [limits, setLimits] = useState("");
  const [water, setWater] = useState("");
  const [error, setError] = useState("");
  const gen = useGenerateFarmingPlan();
  const qc = useQueryClient();
  const { toast } = useToast();

  function submit(e: FormEvent) {
    e.preventDefault();
    const data: FarmingPlanInput = { currentRotation: split(rotation), previousCrops: split(previous), excludedCrops: split(excluded), operationalLimitations: limits.trim(), priority: priority as FarmingPlanInput["priority"] };
    if (data.currentRotation!.length > 6) return setError("Planned rotation allows at most 6 crops.");
    if (data.previousCrops!.length > 12) return setError("Previous crops allows at most 12 entries.");
    if (data.excludedCrops!.length > 20) return setError("Excluded crops allows at most 20 entries.");
    if (plantingDate) data.plantingDate = plantingDate;
    if (water.trim() !== "") {
      const n = Number(water);
      if (!Number.isFinite(n) || n < 0 || n > 10000) return setError("Seasonal water must be a number from 0 to 10000 mm.");
      data.availableSeasonalWaterMm = n;
    }
    setError("");
    gen.mutate({ id: farmId, data }, {
      onSuccess: (r) => { qc.invalidateQueries({ queryKey: getListFarmingPlansQueryKey(farmId) }); qc.setQueryData(getGetFarmingPlanQueryKey(farmId, r.id), r); onCreated(r.id); toast({ title: "Report saved", description: "A new snapshot was added. Your drafts were not changed." }); },
      onError: (err) => setError(errorMessage(err)),
    });
  }

  return (
    <form onSubmit={submit} className="rounded-3xl bg-primary text-primary-foreground furrows p-6 flex flex-col gap-4" data-testid="form-generate-report">
      <div><h3 className="font-display text-2xl">New report</h3><p className="text-sm opacity-80 mt-1">Saved as an immutable snapshot. Manual drafts stay untouched.</p></div>
      {[
        { id: "rotation", l: "Current rotation (in order, comma separated)", v: rotation, s: setRotation, p: "e.g. Wheat, Pea" },
        { id: "previous", l: "Previous crops, oldest first", v: previous, s: setPrevious, p: "e.g. Barley, Potato" },
        { id: "excluded", l: "Crops to exclude", v: excluded, s: setExcluded, p: "Names from the reference library" },
      ].map((f) => (
        <div key={f.id} className="space-y-1.5"><Label htmlFor={`plan-${f.id}`} className="text-xs uppercase tracking-wider opacity-80">{f.l}</Label>
          <Input id={`plan-${f.id}`} value={f.v} onChange={(e) => f.s(e.target.value)} placeholder={f.p} className="bg-primary-foreground/95 text-foreground" data-testid={`input-plan-${f.id}`} /></div>
      ))}
      <div className="space-y-1.5">
        <Label htmlFor="plan-priority" className="text-xs uppercase tracking-wider opacity-80">Main planning priority</Label>
        <select id="plan-priority" value={priority} onChange={(e) => setPriority(e.target.value)}
          className="h-10 w-full rounded-md border border-input bg-primary-foreground/95 px-3 text-sm text-foreground"
          data-testid="select-plan-priority">
          {priorityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <p className="text-xs opacity-75">This changes transparent rule ordering only. Productivity cannot be optimized without verified yield or market data.</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1.5"><Label htmlFor="plan-date" className="text-xs uppercase tracking-wider opacity-80">Planting date (optional)</Label>
          <Input id="plan-date" type="date" value={plantingDate} onChange={(e) => setPlantingDate(e.target.value)} className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-date" /></div>
        <div className="space-y-1.5"><Label htmlFor="plan-water" className="text-xs uppercase tracking-wider opacity-80">Seasonal water, mm (optional)</Label>
          <Input id="plan-water" type="number" min={0} max={10000} step="any" value={water} onChange={(e) => setWater(e.target.value)} className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-water" /></div>
      </div>
      <p className="text-xs opacity-75 -mt-2">Water: your own estimate of total crop-available water for the season (rain, stored soil water and irrigation), not irrigation depth alone. The date is a scenario assumption, not validated local planting advice.</p>
      <div className="space-y-1.5"><Label htmlFor="plan-limits" className="text-xs uppercase tracking-wider opacity-80">Operational limitations</Label>
        <Textarea id="plan-limits" rows={2} maxLength={2000} value={limits} onChange={(e) => setLimits(e.target.value)} placeholder="Machinery, labour, markets..." className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-limits" /></div>
      {error && <p role="alert" className="rounded-xl bg-destructive/90 text-destructive-foreground px-3 py-2 text-sm" data-testid="text-plan-error">{error}</p>}
      <Button type="submit" variant="secondary" disabled={gen.isPending} className="rounded-full" data-testid="button-generate-report">
        {gen.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Generate and save report
      </Button>
    </form>
  );
}

function ReportView({ r }: { r: FarmingPlanReport }) {
  const refs = r.references;
  return (
    <div className="space-y-4 rise" data-testid={`report-${r.id}`}>
      <div className="rounded-3xl border border-card-border bg-card p-6">
        <div className="flex flex-wrap items-center gap-2"><StatusTag s={r.status} /><Tag kind="unassessed">Reference planner · no model used</Tag></div>
        <h3 className="font-display text-3xl text-primary mt-3">Report #{r.id}</h3>
        <p className="font-mono text-xs text-muted-foreground mt-1">{fmt(r.createdAt)} / knowledge {r.knowledgeVersion} / engine {r.engineVersion}</p>
        <p className="text-sm text-muted-foreground mt-3 max-w-3xl">
          {r.status === "insufficient_evidence" ? "There was not enough evidence to build a reference-based plan. Nothing has been guessed in its place." : "Conditional findings from limited reference-based rules."}
          {" "}No accepted model prediction is used: no suitability score, no yield prediction, no similar-region comparison.
        </p>
        <p className="text-sm mt-2"><span className="font-semibold">Priority applied:</span> {humanize(r.priorityApplied ?? "not recorded")}. NASA temperature and farmer-reported soil/water inputs can flag conflicts; they cannot establish crop suitability.</p>
        {r.warnings.length > 0 && <ul className="mt-4 space-y-1.5">{r.warnings.map((w, i) => <li key={i} className="rounded-xl bg-[hsl(38_70%_50%/.12)] px-3 py-2 text-sm">{w}</li>)}</ul>}
      </div>

      {r.aiIntegration && <AnalysisStatus evidence={r.aiIntegration} />}
      <Section title="Rotation scenarios">
        {r.scenarios.length === 0 ? <p className="text-sm text-muted-foreground italic">No scenarios in this report.</p> : (
          <div className="grid xl:grid-cols-3 gap-4">
            {r.scenarios.map((s) => {
              const total = s.waterRequirementMm && s.waterRequirementMm.length ? s.waterRequirementMm : null;
              return (
                <div key={s.slot} className="rounded-2xl border border-border p-4 flex flex-col gap-3" data-testid={`scenario-${s.slot}`}>
                  <div className="flex items-center justify-between gap-2"><span className="font-display text-xl">{s.title}</span><StatusTag s={s.status} /></div>
                  <ol className="flex flex-wrap gap-1.5">{s.crops.map((c, i) => <li key={i} className="rounded-full bg-secondary px-2.5 py-0.5 text-sm"><span className="font-mono text-[10px] mr-1 opacity-60">{i + 1}</span>{c}</li>)}</ol>
                  {total && <p className="text-sm"><span className="font-mono">{total.length >= 2 ? `${total[0]} to ${total[1]}` : total[0]} mm</span> <span className="text-muted-foreground">indicative summed crop water from references, not an irrigation recommendation</span></p>}
                  <div><p className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Benefits and tradeoffs</p><Findings items={s.benefits} refs={refs} tone="benefit" empty="None recorded." testid={`benefit-${s.slot}`} /></div>
                  <div><p className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Risk findings</p><Findings items={s.risks} refs={refs} tone="risk" empty="None recorded." testid={`risk-${s.slot}`} /></div>
                  {s.schedule.length > 0 && (
                    <details className="group"><summary className="cursor-pointer text-sm font-semibold text-accent">Per-crop schedule ({s.schedule.length})</summary>
                      <div className="mt-2 space-y-2">{s.schedule.map((row, i) => <div key={i} className="rounded-xl bg-muted/60 p-3"><RecordView record={row} /></div>)}</div>
                      <p className="text-xs text-muted-foreground mt-2">Dates derive only from your planting date and reference day ranges. This is not a local planting calendar.</p>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <Section title="Reference candidates" aside={<span className="text-xs text-muted-foreground">{r.candidates.length} crops evaluated</span>}>
        {r.candidates.length === 0 ? <p className="text-sm text-muted-foreground italic">No candidates.</p> : (
          <div className="grid lg:grid-cols-2 gap-4">
            {r.candidates.map((c) => (
              <div key={c.crop.id} className="rounded-2xl border border-border p-4 space-y-3" data-testid={`candidate-${c.crop.id}`}>
                <div className="flex items-center justify-between gap-2"><span className="font-display text-xl">{c.crop.name} <span className="text-sm text-muted-foreground font-sans">{humanize(c.crop.group)}</span></span><StatusTag s={c.status} /></div>
                <Findings items={c.reasons} refs={refs} empty="No reasons recorded." testid={`reason-${c.crop.id}`} />
                <Findings items={c.risks} refs={refs} tone="risk" empty="No risks recorded." testid={`crisk-${c.crop.id}`} />
                {c.screen && <div className="rounded-xl bg-muted/60 p-3"><p className="text-xs font-semibold uppercase tracking-wider mb-2">Reference screening details</p><RecordView record={c.screen as Record<string, unknown>} /></div>}
                <details><summary className="cursor-pointer text-sm font-semibold text-accent">Calendar and context</summary>
                  <div className="mt-2 space-y-3"><RecordView record={c.calendar} /><RecordView record={c.environmentalContext} /></div>
                </details>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Management findings"><Findings items={r.management} refs={refs} empty="None recorded." testid="management" /></Section>
        <Section title="Missing information">
          {r.missingInformation.length ? <ul className="list-disc pl-5 space-y-1 text-sm">{r.missingInformation.map((m, i) => <li key={i}>{m}</li>)}</ul> : <p className="text-sm text-muted-foreground italic">Nothing flagged.</p>}
        </Section>
      </div>
      <Section title="Environmental evidence" aside={<Tag kind="observed">Snapshot</Tag>}><RecordView record={r.environmentalEvidence} /></Section>
      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Inputs used" aside={<Tag kind="farmer">Farmer reported</Tag>}><RecordView record={r.inputs} /></Section>
        <Section title="References">
          <ul className="space-y-2 text-sm">{refs.map((x) => <li key={x.id}><a href={x.url} target="_blank" rel="noreferrer" className="font-semibold text-primary hover:text-accent">{x.title}</a><span className="block font-mono text-[10.5px] uppercase text-muted-foreground">{x.id} / {x.scope}</span></li>)}</ul>
        </Section>
      </div>
    </div>
  );
}

export function PlanReports({ farmId, defaultCrop, defaultPriority }: { farmId: number; defaultCrop: string; defaultPriority: string }) {
  const list = useListFarmingPlans(farmId);
  const [picked, setPicked] = useState<number | null>(null);
  const selected = picked ?? list.data?.[0]?.id ?? 0;
  const report = useGetFarmingPlan(farmId, selected, { query: { enabled: !!selected, queryKey: getGetFarmingPlanQueryKey(farmId, selected) } });
  const sorted = [...(list.data ?? [])].sort((a, b) => b.id - a.id);

  return (
    <section className="mt-14" aria-labelledby="reports-heading">
      <div className="pb-6">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">Reference-based reports</p>
        <h2 id="reports-heading" className="font-display text-3xl md:text-4xl text-primary mt-2">Saved farming <span className="italic">reports</span></h2>
        <p className="text-muted-foreground mt-2 max-w-3xl">Limited rules applied to the <Link href="/knowledge" className="text-accent hover:underline" data-testid="link-planner-knowledge">reference library</Link> and this farm's evidence. Every finding links to a source. No accepted ML predictions, suitability score or yield prediction.</p>
      </div>
      <div className="mb-5"><AnalysisStatus /></div>
      <div className="grid lg:grid-cols-[22rem_1fr] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          <ReportForm farmId={farmId} defaultCrop={defaultCrop} defaultPriority={defaultPriority} onCreated={setPicked} />
          <div className="rounded-3xl border border-card-border bg-card p-4">
            <p className="text-sm font-semibold mb-2 px-1">History</p>
            {list.isLoading ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>
              : list.isError ? <div className="px-1"><p className="text-sm text-destructive">Reports could not be listed.</p><Button size="sm" variant="outline" className="mt-2 rounded-full" onClick={() => list.refetch()} data-testid="button-retry-plans"><RotateCcw className="h-3.5 w-3.5" />Retry</Button></div>
              : sorted.length === 0 ? <p className="text-sm text-muted-foreground px-1">No saved reports yet.</p>
              : <ul className="space-y-1 max-h-80 overflow-auto">{sorted.map((p) => (
                  <li key={p.id}><button type="button" onClick={() => setPicked(p.id)} aria-current={p.id === selected}
                    className={cn("w-full text-left rounded-xl px-3 py-2 transition-colors", p.id === selected ? "bg-secondary" : "hover:bg-muted")} data-testid={`button-open-plan-${p.id}`}>
                    <span className="flex items-center justify-between gap-2"><span className="font-semibold text-sm">Report #{p.id}</span><StatusTag s={p.status} /></span>
                    <span className="font-mono text-[10.5px] text-muted-foreground">{fmt(p.createdAt)} / v{p.knowledgeVersion}</span>
                  </button></li>))}</ul>}
          </div>
        </div>
        <div className="min-w-0">
          {!selected ? (
            <div className="rounded-3xl border-2 border-dashed border-input p-10 text-center">
              <FileText className="h-8 w-8 mx-auto text-muted-foreground" />
              <p className="font-display text-2xl text-primary mt-3">No report open</p>
              <p className="text-sm text-muted-foreground mt-1">Generate one to see conditional, source-linked findings.</p>
            </div>
          ) : report.isLoading ? <div className="space-y-4"><Skeleton className="h-40 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></div>
            : report.isError || !report.data ? (
              <div className="rounded-3xl border border-card-border bg-card p-8"><p className="font-display text-2xl text-primary">This report could not be loaded</p>
                <Button className="mt-4 rounded-full" onClick={() => report.refetch()} data-testid="button-retry-plan">Retry</Button></div>
            ) : <ReportView key={report.data.id} r={report.data} />}
        </div>
      </div>
    </section>
  );
}
