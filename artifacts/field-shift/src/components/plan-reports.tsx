import { useState, type FormEvent, type ReactNode } from "react";
import { AnalysisStatus } from "@/components/analysis-status";
import { ExperimentalMl } from "@/components/experimental-ml";
import { ML_WARNING, MlJobView } from "@/components/ml-job-view";
import { GaezEvidence, GaezReport } from "@/components/gaez-evidence";
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
  const label = ({
    reference_based_plan: "Crop facts found",
    conditional_candidate: "Check this",
    insufficient_evidence: "Not enough facts",
  } as Record<string, string>)[s] ?? humanize(s);
  return <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider",
    ok ? "bg-secondary border-[hsl(92_20%_70%)] text-secondary-foreground" : "bg-[hsl(38_70%_50%/.14)] text-[hsl(30_60%_30%)] border-[hsl(38_70%_50%/.35)]")}>{label}</span>;
}

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4"><h3 className="font-display text-2xl text-primary">{title}</h3>{aside}</div>
      {children}
    </section>
  );
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function profileText(value: unknown, empty = "Not provided"): string {
  return typeof value === "string" && value.trim() ? value.trim() : empty;
}

function ReportSummary({ report }: { report: FarmingPlanReport }) {
  const planning = recordValue(report.inputs.planning ?? report.inputs);
  const farm = recordValue(report.inputs.farmerProfile);
  const rotation = textList(planning.currentRotation);
  const currentCrop = profileText(farm.currentCrop, rotation[0] || "Not recorded in this snapshot");
  const previousCrops = textList(planning.previousCrops);
  const profileHistory = profileText(farm.cropHistory);
  const priorityValue = report.priorityApplied ?? planning.priority ?? farm.goal;
  const priority = typeof priorityValue === "string" ? humanize(priorityValue) : "";
  const water = typeof planning.availableSeasonalWaterMm === "number" ? planning.availableSeasonalWaterMm : null;
  const findings = [...report.management, ...report.scenarios.flatMap((scenario) => [...scenario.benefits, ...scenario.risks])]
    .filter((finding, index, all) => all.findIndex((candidate) => candidate.message === finding.message) === index)
    .slice(0, 3);
  const cropsToReview = [currentCrop, ...rotation, ...previousCrops, ...report.scenarios.flatMap((scenario) => scenario.crops)];
  const includesRice = cropsToReview.some((crop) => /rice/i.test(crop));
  const missing = report.missingInformation;
  const soilMoisture = typeof farm.soilMoisture === "number" ? `${farm.soilMoisture}% vol. · profile entry` : "Not measured";
  const soilPh = typeof farm.soilPh === "number" ? `${farm.soilPh} · profile entry` : "Not measured";
  const farmSize = typeof farm.farmSize === "number" ? `${farm.farmSize} ha · profile entry` : "Not provided";

  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 md:p-6" aria-labelledby="report-summary-heading" data-testid="report-summary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="report-summary-heading" className="font-display text-2xl text-primary">Your report</h3>
        <Tag kind="farmer">Saved farm and plan details</Tag>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        {report.status === "insufficient_evidence"
          ? "We did not have enough crop facts to make this report. We did not fill in missing facts."
          : "This report uses crop facts and the details you shared. It is not a promise, a crop score, or a harvest guess."}
        {" "}{report.mlPredictions
          ? "The test model number below may be wrong. It did not choose or rank your crop plans."
          : "This report has no test model number."}
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-muted/60 p-4">
          <h4 className="text-sm font-semibold">About the farm</h4>
          <dl className="mt-2 space-y-2 text-sm">
            <div><dt className="text-xs text-muted-foreground">Farm</dt><dd>{profileText(farm.name)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Location</dt><dd>{profileText(farm.locationName)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Crop now</dt><dd>{currentCrop}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Past crops</dt><dd>{profileHistory}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Watering</dt><dd>{profileText(farm.irrigation, "Not added").replaceAll("_", " ")}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Soil type, pH and wetness</dt><dd>{profileText(farm.soilType)} · pH {soilPh} · wetness {soilMoisture}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Farm size</dt><dd>{farmSize}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Water sources and limits</dt><dd className="break-words">{profileText(farm.waterResources)} · {profileText(farm.waterConstraints)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Other farm limits</dt><dd className="break-words">{profileText(farm.agriculturalConstraints)}</dd></div>
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">These details came from you. We have not checked them. Empty boxes stay empty.</p>
        </div>
        <div className="rounded-2xl bg-muted/60 p-4">
          <h4 className="text-sm font-semibold">Your plan</h4>
          <dl className="mt-2 space-y-2 text-sm">
            <div><dt className="text-xs text-muted-foreground">Crop order</dt>
              <dd>{rotation.length ? rotation.map((crop, index) => `${index + 1}. ${crop}`).join(" → ") : `Based on the crop you grow now: ${currentCrop}`}</dd></div>
            {previousCrops.length > 0 && <div><dt className="text-xs text-muted-foreground">Past crops</dt><dd>{previousCrops.join(", ")}</dd></div>}
            {priority && <div><dt className="text-xs text-muted-foreground">What matters most</dt><dd>{priority}</dd></div>}
            {water !== null && <div><dt className="text-xs text-muted-foreground">Your water guess</dt><dd>{water} mm · your estimate, not a measurement</dd></div>}
          </dl>
        </div>
        <div className="rounded-2xl bg-muted/60 p-4">
          <h4 className="text-sm font-semibold">What we found</h4>
          {findings.length
            ? <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm">{findings.map((finding, index) => <li key={`${finding.code}-${index}`}>{finding.message}</li>)}</ul>
            : <p className="mt-2 text-sm text-muted-foreground">We found no crop facts to show. This does not mean the plan will work.</p>}
        </div>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold">Details still needed</h4>
          {missing.length
            ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{missing.slice(0, 4).map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
            : <p className="mt-2 text-sm text-muted-foreground">No empty details were found. We still have not checked if they are true.</p>}
          {missing.length > 4 && <p className="mt-1 text-xs text-muted-foreground">{missing.length - 4} more details are listed below.</p>}
        </div>
        <div>
          <h4 className="text-sm font-semibold">Things to check</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Check how much water you can use and what your soil is like.</li>
            {includesRice && <li>Check if the rice grows in dry ground or under water.</li>}
            <li>Ask a local farm helper before changing your plan.</li>
          </ul>
        </div>
      </div>
      {report.mlPredictions && (
        <p role="note" className="mt-4 rounded-xl border border-[hsl(38_70%_50%/.5)] bg-[hsl(38_70%_50%/.14)] px-3 py-2 text-sm font-semibold">
          This report has a test model number. It has not passed its checks and may be wrong. Do not use it to choose what to grow.
        </p>
      )}
    </section>
  );
}

const priorityOptions = [
  { value: "conserve_water", label: "Use less water" },
  { value: "soil_health", label: "Help the soil" },
  { value: "reduce_risk", label: "Lower risk" },
  { value: "productivity", label: "Grow more" },
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
    if (data.currentRotation!.length > 6) return setError("Use 6 crops or fewer in your plan.");
    if (data.previousCrops!.length > 12) return setError("Add 12 past crops or fewer.");
    if (data.excludedCrops!.length > 20) return setError("Leave out 20 crops or fewer.");
    if (plantingDate) data.plantingDate = plantingDate;
    if (water.trim() !== "") {
      const n = Number(water);
      if (!Number.isFinite(n) || n < 0 || n > 10000) return setError("Water must be a number from 0 to 10,000 mm.");
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
      <div><h3 className="font-display text-2xl">Make and save a report</h3><p className="text-sm opacity-80 mt-1">This saves a copy of your answers and the crop facts we have now. Water is your guess, not a measurement. Your other plans will not change.</p></div>
      {[
        { id: "rotation", l: "Crops in your plan, in order", v: rotation, s: setRotation, p: "Example: wheat, then pea" },
        { id: "previous", l: "Past crops, oldest first", v: previous, s: setPrevious, p: "Example: barley, then potato" },
        { id: "excluded", l: "Crops to leave out", v: excluded, s: setExcluded, p: "Use names from the crop guide" },
      ].map((f) => (
        <div key={f.id} className="space-y-1.5"><Label htmlFor={`plan-${f.id}`} className="text-xs uppercase tracking-wider opacity-80">{f.l}</Label>
          <Input id={`plan-${f.id}`} value={f.v} onChange={(e) => f.s(e.target.value)} placeholder={f.p} className="bg-primary-foreground/95 text-foreground" data-testid={`input-plan-${f.id}`} /></div>
      ))}
      <div className="space-y-1.5">
        <Label htmlFor="plan-priority" className="text-xs uppercase tracking-wider opacity-80">What matters most?</Label>
        <select id="plan-priority" value={priority} onChange={(e) => setPriority(e.target.value)}
          className="h-10 w-full rounded-md border border-input bg-primary-foreground/95 px-3 text-sm text-foreground"
          data-testid="select-plan-priority">
          {priorityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <p className="text-xs opacity-75">This helps choose which crop facts to show first. It cannot tell which crop will give the biggest harvest.</p>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1.5"><Label htmlFor="plan-date" className="text-xs uppercase tracking-wider opacity-80">When might you plant? (optional)</Label>
          <Input id="plan-date" type="date" value={plantingDate} onChange={(e) => setPlantingDate(e.target.value)} className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-date" /></div>
        <div className="space-y-1.5"><Label htmlFor="plan-water" className="text-xs uppercase tracking-wider opacity-80">Water for the whole season, in mm (optional)</Label>
          <Input id="plan-water" type="number" min={0} max={10000} step="any" value={water} onChange={(e) => setWater(e.target.value)} className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-water" /></div>
      </div>
      <p className="text-xs opacity-75 -mt-2">mm is a way to measure water. Add your guess for rain, saved water and watering. This is not a measurement. The planting day is your guess, not local advice.</p>
      <div className="space-y-1.5"><Label htmlFor="plan-limits" className="text-xs uppercase tracking-wider opacity-80">Farm limits</Label>
        <Textarea id="plan-limits" rows={2} maxLength={2000} value={limits} onChange={(e) => setLimits(e.target.value)} placeholder="Machines, workers or markets..." className="bg-primary-foreground/95 text-foreground" data-testid="input-plan-limits" /></div>
      {error && <p role="alert" className="rounded-xl bg-destructive/90 text-destructive-foreground px-3 py-2 text-sm" data-testid="text-plan-error">{error}</p>}
      <Button type="submit" variant="secondary" disabled={gen.isPending} className="rounded-full" data-testid="button-generate-report">
        {gen.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Make report
      </Button>
    </form>
  );
}

function ReportView({ r }: { r: FarmingPlanReport }) {
  const refs = r.references;
  return (
    <div className="space-y-4 rise" data-testid={`report-${r.id}`}>
      <div className="rounded-3xl border border-card-border bg-card p-6">
        <div className="flex flex-wrap items-center gap-2"><StatusTag s={r.status} /><Tag kind="unassessed">{r.mlPredictions ? "Test number included" : "Crop facts only"}</Tag></div>
        <h3 className="font-display text-3xl text-primary mt-3">Saved report</h3>
        <p className="text-sm text-muted-foreground mt-1">{fmt(r.createdAt)}</p>
        <details className="mt-3 text-sm" data-testid={`details-report-technical-${r.id}`}>
          <summary className="cursor-pointer font-semibold text-accent">Extra report details</summary>
          <dl className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
            <div><dt className="text-muted-foreground">Report number</dt><dd className="font-mono">{r.id}</dd></div>
            <div><dt className="text-muted-foreground">Reference set</dt><dd className="font-mono break-all">{r.knowledgeVersion}</dd></div>
            <div><dt className="text-muted-foreground">Planning engine</dt><dd className="font-mono break-all">{r.engineVersion}</dd></div>
            <div><dt className="text-muted-foreground">Priority applied</dt><dd>{humanize(r.priorityApplied ?? "not recorded")}</dd></div>
          </dl>
        </details>
      </div>

      <ReportSummary report={r} />

      <Section title="Crop plan ideas">
        <p className="mb-4 text-sm text-muted-foreground">These are ideas to check, not a list of best crops. Crop facts cannot tell how much you will grow or earn.</p>
        {r.scenarios.length === 0 ? <p className="text-sm text-muted-foreground italic">No crop plans were saved in this report.</p> : (
          <div className="grid xl:grid-cols-3 gap-4">
            {r.scenarios.map((s) => {
              const total = s.waterRequirementMm?.length ? s.waterRequirementMm : null;
              return (
                <div key={s.slot} className="min-w-0 rounded-2xl border border-border p-4 flex flex-col gap-3" data-testid={`scenario-${s.slot}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-display text-xl">{s.title}</span><StatusTag s={s.status} /></div>
                  <ol className="flex flex-wrap gap-1.5">{s.crops.map((c, i) => <li key={i} className="rounded-full bg-secondary px-2.5 py-1 text-sm"><span className="font-mono text-[10px] mr-1 opacity-60">{i + 1}</span>{c}</li>)}</ol>
                  {total && <p className="text-sm"><span className="font-semibold">{total.length >= 2 ? `${total[0]}–${total[1]}` : total[0]} mm</span> <span className="text-muted-foreground">a broad crop-guide guess, not a farm measurement or watering rule</span></p>}
                  <div><p className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">What may help</p><Findings items={s.benefits} refs={refs} tone="benefit" empty="Nothing listed." testid={`benefit-${s.slot}`} /></div>
                  <div><p className="text-xs uppercase tracking-wider text-muted-foreground mb-1.5">Things to watch</p><Findings items={s.risks} refs={refs} tone="risk" empty="Nothing listed." testid={`risk-${s.slot}`} /></div>
                  {s.schedule.length > 0 && (
                    <details className="group"><summary className="cursor-pointer text-sm font-semibold text-accent">When crops may grow ({s.schedule.length})</summary>
                      <div className="mt-2 space-y-2">{s.schedule.map((row, i) => <div key={i} className="rounded-xl bg-muted/60 p-3"><RecordView record={row} /></div>)}</div>
                      <p className="text-xs text-muted-foreground mt-2">These dates use your guess and broad crop facts. They are not a local planting calendar.</p>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {r.gaezEvidence && <GaezReport evidence={r.gaezEvidence} />}

      {r.mlPredictions && <Section title="Unvalidated experimental model output" aside={<Tag kind="unassessed">Unsafe for farm decisions</Tag>}>
        <div className="space-y-3" data-testid="report-ml-predictions">
          <p role="note" className="rounded-xl border border-[hsl(38_70%_50%/.5)] bg-[hsl(38_70%_50%/.14)] px-3 py-2 text-sm font-semibold">{r.mlPredictions.warning || ML_WARNING}</p>
          <p className="text-sm text-muted-foreground">These outputs failed scientific acceptance, have no calibrated confidence, and were saved as experimental evidence only. They did not rank the rotation scenarios.</p>
          {r.mlPredictions.jobs.length === 0 ? <p className="text-sm italic text-muted-foreground">No completed model runs were available when this report was saved.</p>
            : <div className="grid xl:grid-cols-2 gap-3">{r.mlPredictions.jobs.map((j) => <MlJobView key={j.jobId} job={j} saved />)}</div>}
          <details className="text-sm" data-testid="details-report-model-snapshot">
            <summary className="cursor-pointer font-semibold text-accent">Model snapshot details</summary>
            <p className="mt-2 text-xs text-muted-foreground">Saved {fmt(r.mlPredictions.generatedAt)} · status: {humanize(r.mlPredictions.status)} · scope: {humanize(r.mlPredictions.scope)}</p>
            {r.mlPredictions.plannerUse && <p className="mt-1 text-xs text-muted-foreground">{r.mlPredictions.plannerUse}</p>}
          </details>
        </div>
      </Section>}

      <Section title="Crops checked" aside={<span className="text-xs text-muted-foreground">{r.candidates.length} crops</span>}>
        {r.candidates.length === 0 ? <p className="text-sm text-muted-foreground italic">No crops were checked.</p> : (
          <div className="grid lg:grid-cols-2 gap-4">
            {r.candidates.map((c) => (
              <div key={c.crop.id} className="rounded-2xl border border-border p-4 space-y-3" data-testid={`candidate-${c.crop.id}`}>
                <div className="flex items-center justify-between gap-2"><span className="font-display text-xl">{c.crop.name} <span className="text-sm text-muted-foreground font-sans">{humanize(c.crop.group)}</span></span><StatusTag s={c.status} /></div>
                <Findings items={c.reasons} refs={refs} empty="No reasons recorded." testid={`reason-${c.crop.id}`} />
                <Findings items={c.risks} refs={refs} tone="risk" empty="No risks recorded." testid={`crisk-${c.crop.id}`} />
                 {c.modelEstimates && c.modelEstimates.length > 0 && <details><summary className="cursor-pointer text-sm font-semibold text-accent">Test model numbers ({c.modelEstimates.length})</summary>
                  <div className="mt-2 space-y-2">{c.modelEstimates.map((j) => <MlJobView key={j.jobId} job={j} saved />)}</div></details>}
                {c.screen && <details data-testid={`details-candidate-screen-${c.crop.id}`}><summary className="cursor-pointer text-sm font-semibold text-accent">Detailed screening record</summary><div className="mt-2 rounded-xl bg-muted/60 p-3"><RecordView record={c.screen as Record<string, unknown>} /></div></details>}
                 <details><summary className="cursor-pointer text-sm font-semibold text-accent">Growing time and place</summary>
                  <div className="mt-2 space-y-3"><RecordView record={c.calendar} /><RecordView record={c.environmentalContext} /></div>
                </details>
              </div>
            ))}
          </div>
        )}
      </Section>

      <details className="rounded-3xl border border-card-border bg-card p-5 md:p-6" data-testid={`details-report-evidence-${r.id}`}>
        <summary className="cursor-pointer font-display text-2xl text-primary">More facts and where they came from</summary>
        <div className="mt-4 space-y-4">
          {r.aiIntegration && <AnalysisStatus evidence={r.aiIntegration} />}
          {r.warnings.length > 0 && <Section title={`What we do not know (${r.warnings.length})`}>
            <ul className="list-disc space-y-2 pl-5 text-sm">{r.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
          </Section>}
          <Section title="All farm notes"><Findings items={r.management} refs={refs} empty="No notes saved." testid="management" /></Section>
          <Section title="Details not added">
            {r.missingInformation.length ? <ul className="list-disc pl-5 space-y-1 text-sm">{r.missingInformation.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="text-sm text-muted-foreground italic">No missing details were noted.</p>}
          </Section>
          <Section title="Weather and land data" aside={<Tag kind="observed">Saved copy</Tag>}><RecordView record={r.environmentalEvidence} /></Section>
          <Section title="Your saved answers" aside={<Tag kind="farmer">Farm and plan details</Tag>}><RecordView record={r.inputs} /></Section>
          <Section title={`Where facts came from (${refs.length})`}>
            <ul className="space-y-3 text-sm">{refs.map((reference) => <li key={reference.id}>
              <a href={reference.url} target="_blank" rel="noreferrer" className="font-semibold text-primary hover:text-accent">{reference.title}</a>
              <span className="block text-xs text-muted-foreground">{reference.scope}</span>
              <details className="mt-1 text-xs"><summary className="cursor-pointer text-accent">Extra source code</summary><span className="font-mono">{reference.id}</span></details>
            </li>)}</ul>
          </Section>
        </div>
      </details>
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
        <p className="text-muted-foreground mt-2 max-w-3xl">These reports compare your farm details with facts in the <Link href="/knowledge" className="text-accent hover:underline" data-testid="link-planner-knowledge">crop guide</Link>. They are not expert advice and do not rank crops. FAO maps and test model numbers are shown separately.</p>
      </div>
      <div className="grid lg:grid-cols-[22rem_1fr] gap-5 items-start">
        <div className="space-y-5 min-w-0">
          <ReportForm farmId={farmId} defaultCrop={defaultCrop} defaultPriority={defaultPriority} onCreated={setPicked} />
          <div className="rounded-3xl border border-card-border bg-card p-4">
            <p className="text-sm font-semibold mb-2 px-1">Saved reports</p>
            {list.isLoading ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-xl" />)}</div>
              : list.isError ? <div className="px-1"><p className="text-sm text-destructive">Reports could not be listed.</p><Button size="sm" variant="outline" className="mt-2 rounded-full" onClick={() => list.refetch()} data-testid="button-retry-plans"><RotateCcw className="h-3.5 w-3.5" />Retry</Button></div>
              : sorted.length === 0 ? <p className="text-sm text-muted-foreground px-1">No saved reports yet.</p>
              : <ul className="space-y-1 max-h-80 overflow-auto">{sorted.map((p) => (
                  <li key={p.id}><button type="button" onClick={() => setPicked(p.id)} aria-current={p.id === selected}
                    className={cn("w-full text-left rounded-xl px-3 py-2 transition-colors", p.id === selected ? "bg-secondary" : "hover:bg-muted")} data-testid={`button-open-plan-${p.id}`}>
                    <span className="flex items-center justify-between gap-2"><span className="font-semibold text-sm">Saved {fmt(p.createdAt)}</span><StatusTag s={p.status} /></span>
                    <span className="text-xs text-muted-foreground">Select to open this saved report</span>
                  </button></li>))}</ul>}
          </div>
        </div>
        <div className="min-w-0">
          {!selected ? (
            <div className="rounded-3xl border-2 border-dashed border-input p-10 text-center">
              <FileText className="h-8 w-8 mx-auto text-muted-foreground" />
              <p className="font-display text-2xl text-primary mt-3">No report open</p>
              <p className="text-sm text-muted-foreground mt-1">Make one to see crop facts and where they came from.</p>
            </div>
          ) : report.isLoading ? <div className="space-y-4"><Skeleton className="h-40 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></div>
            : report.isError || !report.data ? (
              <div className="rounded-3xl border border-card-border bg-card p-8"><p className="font-display text-2xl text-primary">This report could not be loaded</p>
                <Button className="mt-4 rounded-full" onClick={() => report.refetch()} data-testid="button-retry-plan">Retry</Button></div>
            ) : <ReportView key={report.data.id} r={report.data} />}
        </div>
      </div>
      <div className="mt-8 space-y-5" aria-label="More crop facts and test tools">
        <h3 className="font-display text-2xl text-primary">More crop facts and test tools</h3>
        <p className="text-sm text-muted-foreground">These tools show more facts. They do not change your crop plans above.</p>
        <AnalysisStatus />
        <GaezEvidence farmId={farmId} defaultCrop={defaultCrop} />
        <ExperimentalMl key={farmId} farmId={farmId} />
        <p className="text-sm font-semibold text-primary px-1">To save a test number in a report, run it here first. It will stay marked as a test result.</p>
      </div>
    </section>
  );
}
