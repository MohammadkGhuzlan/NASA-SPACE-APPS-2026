import { Loader2 } from "lucide-react";
import type { ExperimentalJob } from "@workspace/api-client-react";

export const ML_WARNING = "Unvalidated ML prediction. These models failed scientific acceptance, have no calibrated confidence, and are not safe for farming decisions.";

const rec = (v: unknown): Record<string, unknown> | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const show = (v: unknown): string => {
  if (v === null || v === undefined) return "not reported";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 1 ? 4 : 2);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};
export function formatIndex(v: number): string {
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const CROP_NAMES: Record<string, string> = {
  WHE: "Wheat",
  BRL: "Barley",
  MZE: "Maize",
  RCD: "Rice · dryland",
  RCW: "Rice · wetland",
};
const cropName = (code: string) => CROP_NAMES[code] ?? code;

function inputQualityLabel(value: string) {
  if (value === "original_inputs") return "Original source inputs";
  if (value === "estimated_soil") return "Estimated soil inputs";
  return value.replaceAll("_", " ");
}

function jobStatusLabel(status: ExperimentalJob["status"]) {
  const labels: Record<string, string> = {
    preparing: "Preparing inputs",
    experimental_output: "Experimental result",
    missing_inputs: "Inputs missing",
    unavailable: "Unavailable",
    interrupted: "Run interrupted",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function Kv({ k, v, testid }: { k: string; v: string; testid?: string }) {
  return <div className="min-w-0"><dt className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{k}</dt><dd className="font-mono text-xs break-all [overflow-wrap:anywhere]" data-testid={testid}>{v}</dd></div>;
}

function Provenance({ job }: { job: ExperimentalJob }) {
  const s = rec(job.inputSummary);
  const estimated = job.inputQuality === "estimated_soil" || s?.estimatedInputs === true;
  const compatible = s?.compatible;
  const est = rec(s?.soilEstimation);
  const method = typeof est?.method === "string" ? est.method : null;
  const coords = rec(est?.sourceCoordinates);
  const fractions = est?.validAreaFractions;
  if (!estimated && compatible !== false && !est) {
    return job.inputQuality === "original_inputs"
      ? <p className="text-xs rounded-xl bg-secondary px-3 py-2" data-testid={`text-ml-inputs-${job.jobId}`}>Inputs: original training-contract inputs (SoilGrids cell means and 2001–2020 NASA POWER climate). The model itself still failed validation.</p>
      : null;
  }
  return (
    <div className="rounded-xl border border-[hsl(38_70%_50%/.5)] bg-[hsl(38_70%_50%/.12)] px-3 py-2 text-xs space-y-1.5" data-testid={`text-ml-estimated-${job.jobId}`}>
      {estimated && <p className="font-semibold text-sm">Estimated soil inputs were used. Soil values were not measured at this farm.</p>}
      {method === "nearest_recorded_training_cell" && <p>Soil was estimated from the nearest recorded training location{typeof est?.distanceKm === "number" ? `, ${est.distanceKm.toFixed(1)} km away` : ""}.</p>}
      {method === "partial_native_cell_coverage" && <p>Soil was estimated using only the SoilGrids pixels available in this cell; the cell was not fully covered.</p>}
      {method && method !== "nearest_recorded_training_cell" && method !== "partial_native_cell_coverage" && <p>Soil estimation method: {method.replaceAll("_", " ")}.</p>}
      {compatible === false && <p>The available inputs did not match the model's original input requirements. The model still ran on substituted inputs, so the result is even less reliable.</p>}
      {(est?.sourceCellId !== undefined || coords || fractions !== undefined || est?.sourceEvidence !== undefined) && (
        <details data-testid={`details-ml-source-coverage-${job.jobId}`}>
          <summary className="cursor-pointer text-accent">Source location and coverage details</summary>
          <div className="mt-1 space-y-1 break-all [overflow-wrap:anywhere]">
            {est?.sourceCellId !== undefined && <p>Source cell identifier: {show(est.sourceCellId)}</p>}
            {coords && <p>Source coordinates: {Object.entries(coords).map(([k, v]) => `${k} ${show(v)}`).join(", ")}</p>}
            {fractions !== undefined && <p>Available area fractions: {show(fractions)}</p>}
            {est?.sourceEvidence !== undefined && <p>Source evidence: {show(est.sourceEvidence)}</p>}
          </div>
        </details>
      )}
      <p>{s?.climateRetrieved === true ? "Climate inputs are authentic 2001–2020 NASA POWER data; no climate was synthesised." : "No complete historical climate retrieval was recorded for this run; no climate was synthesised."}</p>
    </div>
  );
}

export function MlJobView({ job, saved = false }: { job: ExperimentalJob; saved?: boolean }) {
  const ood = job.geographicSupport === "out_of_domain";
  const coords = job.requestedCoordinates ? Object.entries(job.requestedCoordinates) : [];
  const hasValue = job.status === "experimental_output" && job.value !== null;
  return (
    <div className="min-w-0 max-w-full rounded-2xl border border-[hsl(38_70%_50%/.45)] bg-[hsl(38_70%_50%/.06)] p-4 space-y-3" data-testid={`ml-job-${job.jobId}`} aria-live={saved ? undefined : "polite"}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-[hsl(38_70%_50%/.5)] px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider">Unvalidated · {jobStatusLabel(job.status)}</span>
        <span className="text-xs">Crop: {cropName(job.cropCode)}</span>
        {job.inputQuality && <span className="text-xs">Inputs: {inputQualityLabel(job.inputQuality)}</span>}
      </div>
      <p className="text-sm font-semibold" role="note">{job.warning || ML_WARNING}</p>
      {job.status === "preparing" && <p className="text-sm flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Preparing inputs. Checking job status...</p>}
      {hasValue && (
        <div className="min-w-0">
          {ood && <p role="alert" className="mb-2 rounded-xl bg-destructive/90 text-destructive-foreground px-3 py-2 text-sm">Out of domain: this location falls outside the development support screen. The value below is especially unreliable.</p>}
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Experimental suitability index · scale 0–10,000</p>
          <p className="font-display text-3xl sm:text-4xl text-primary tabular-nums" data-testid={`text-ml-value-${job.jobId}`}>{formatIndex(job.value!)} <span className="text-base font-sans">{job.unit}</span></p>
          <details className="text-xs mt-1"><summary className="cursor-pointer text-muted-foreground">Exact raw value</summary><p className="font-mono break-all mt-1" data-testid={`text-ml-raw-${job.jobId}`}>{String(job.value)}</p></details>
          <p className="text-xs text-muted-foreground mt-1">This index is not a percentage, yield, profit, probability, or crop ranking. No calibrated confidence exists.</p>
          {job.target && <details className="text-xs mt-1" data-testid={`details-ml-target-${job.jobId}`}><summary className="cursor-pointer text-accent">Technical target definition</summary><p className="mt-1 text-muted-foreground">{job.target}</p></details>}
        </div>
      )}
      {(job.status === "missing_inputs" || job.status === "unavailable" || job.status === "interrupted" || (job.status === "experimental_output" && job.value === null)) && (
        <div className="text-sm space-y-1">
          <p className="font-semibold">No prediction was produced for {cropName(job.cropCode)}.</p>
          {job.reasons.map((reason) => <p key={reason}>{reason.replaceAll("_", " ")}</p>)}
        </div>
      )}
      {job.status !== "preparing" && <Provenance job={job} />}
      {(job.reasons.length > 0 || (job.supportReasons?.length ?? 0) > 0) && <details className="text-sm" data-testid={`details-ml-input-checks-${job.jobId}`}>
        <summary className="cursor-pointer font-semibold text-accent">Input and location checks</summary>
        <ul className="mt-2 list-disc pl-5 space-y-0.5">{[...job.reasons, ...(job.supportReasons ?? [])].map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}</ul>
      </details>}
      {job.warnings && job.warnings.length > 0 && <ul className="space-y-1">{job.warnings.map((w, i) => <li key={i} className="rounded-lg bg-[hsl(38_70%_50%/.12)] px-2.5 py-1.5 text-xs">{w}</li>)}</ul>}
      {job.inputSummary && <details className="text-xs">
        <summary className="cursor-pointer font-semibold">Full input provenance</summary>
        <pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(job.inputSummary, null, 2)}</pre>
      </details>}
      <details className="text-xs"><summary className="cursor-pointer font-semibold">Job details</summary>
        <dl className="grid sm:grid-cols-2 gap-2 mt-2">
          <Kv k="Job" v={job.jobId} />
          {job.geographicSupport && <Kv k="Geographic support" v={job.geographicSupport} />}
          {coords.map(([k, v]) => <Kv key={k} k={`Requested ${k}`} v={show(v)} />)}
          {job.inputPolicy && <Kv k="Input policy" v={job.inputPolicy} />}
          {job.allowEstimatedInputs !== undefined && <Kv k="Estimated inputs allowed" v={String(job.allowEstimatedInputs)} />}
          <Kv k="Estimator executed" v={String(job.estimatorExecuted)} />
          <Kv k="Scientifically accepted" v={String(job.productionAccepted)} />
          {job.modelVersion && <Kv k="Model version" v={job.modelVersion} />}
          {job.datasetHash && <Kv k="Dataset hash" v={job.datasetHash} />}
          {job.artifactSha256 && <Kv k="Artifact sha256" v={job.artifactSha256} />}
          {job.createdAt && <Kv k="Created" v={job.createdAt} />}
          {job.completedAt && <Kv k="Completed" v={job.completedAt} />}
        </dl>
      </details>
    </div>
  );
}
