import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Lock, RotateCcw } from "lucide-react";
import {
  getGetExperimentalJobQueryKey, getGetExperimentalStatusQueryKey,
  useGetExperimentalJob, useGetExperimentalStatus, useRunExperimentalPrediction,
  type ExperimentalJob, type ExperimentalPredictionInputCropCode,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const WARNING = "Experimental model — failed validation. Predictions may be inaccurate and should not be used for real farming decisions.";
const CROPS: { code: ExperimentalPredictionInputCropCode; label: string }[] = [
  { code: "WHE", label: "Wheat (WHE)" },
  { code: "BRL", label: "Barley (BRL)" },
  { code: "MZE", label: "Maize (MZE)" },
  { code: "RCD", label: "Rice, dryland (RCD)" },
  { code: "RCW", label: "Rice, wetland (RCW)" },
];
const TERMINAL_STOP = new Set([401, 403, 404, 409]);
const storeKey = (farmId: number, crop: string) => `fieldshift:expml:${farmId}:${crop}`;
const cropKey = (farmId: number) => `fieldshift:expml:${farmId}:crop`;
function restoreCrop(farmId: number): ExperimentalPredictionInputCropCode | "" {
  try {
    const v = sessionStorage.getItem(cropKey(farmId));
    return CROPS.some((c) => c.code === v) ? (v as ExperimentalPredictionInputCropCode) : "";
  } catch { return ""; }
}

function errStatus(e: unknown): number | undefined { return (e as { status?: number } | null)?.status; }
function errText(e: unknown): string {
  const o = e as { status?: number; data?: unknown } | null;
  const d = o?.data as Record<string, unknown> | string | undefined;
  let msg = "";
  if (typeof d === "string") msg = d;
  else if (d && typeof d === "object") for (const k of ["error", "message", "detail"]) if (typeof d[k] === "string") { msg = d[k] as string; break; }
  const s = o?.status;
  if (s === 429) return `Too many experimental runs recently. Wait a little, then retry.${msg ? ` (${msg})` : ""}`;
  if (s === 401 || s === 403) return "Development access is required for experimental predictions.";
  if (s === 404) return "This experimental job was not found. It may have expired.";
  if (s === 409) return "The farm location changed since this job was requested. The old result was cleared; run again for the current location.";
  return msg || "The experimental request could not be completed. Try again.";
}
const num = (n: number | null | undefined) => (n === null || n === undefined ? "not reported" : String(n));

function Kv({ k, v, testid }: { k: string; v: string; testid?: string }) {
  return <div className="min-w-0"><dt className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{k}</dt><dd className="font-mono text-xs break-all [overflow-wrap:anywhere]" data-testid={testid}>{v}</dd></div>;
}

function JobView({ job }: { job: ExperimentalJob }) {
  const ood = job.geographicSupport === "out_of_domain";
  const coords = job.requestedCoordinates ? Object.entries(job.requestedCoordinates) : [];
  return (
    <div className="min-w-0 max-w-full rounded-2xl border border-[hsl(38_70%_50%/.45)] bg-[hsl(38_70%_50%/.08)] p-4 space-y-3" data-testid={`experimental-job-${job.jobId}`} aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-[hsl(38_70%_50%/.5)] px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider">Experimental · {job.status.replaceAll("_", " ")}</span>
        <span className="font-mono text-xs">Crop {job.cropCode}</span>
        <span className="font-mono text-xs">estimatorExecuted: {String(job.estimatorExecuted)}</span>
        <span className="font-mono text-xs">productionAccepted: {String(job.productionAccepted)}</span>
      </div>
      <p className="text-sm font-semibold" role="note">{job.warning || WARNING}</p>
      {job.status === "preparing" && <p className="text-sm flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Preparing inputs. Checking job status...</p>}
      {job.status === "experimental_output" && job.value !== null && (
        <div>
          {ood && <p role="alert" className="mb-2 rounded-xl bg-destructive/90 text-destructive-foreground px-3 py-2 text-sm">Out of domain: this location falls outside the development support screen for geography and/or environmental features. No geographic domain passed validation. The value below is especially unreliable and is not ranked or recommended.</p>}
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Experimental model output{job.target ? ` (${job.target})` : ""}</p>
          <p className="min-w-0 max-w-full font-display text-3xl sm:text-4xl text-primary [overflow-wrap:anywhere]" data-testid="text-experimental-value">{job.value} <span className="text-base font-sans">{job.unit}</span></p>
          <p className="text-xs text-muted-foreground mt-1">A raw research estimate. Not a confidence, probability, ranking or recommendation, and never used by saved reports.</p>
        </div>
      )}
      {(job.status === "missing_inputs" || job.status === "unavailable" || job.status === "interrupted" || (job.status === "experimental_output" && job.value === null)) && (
        <div className="text-sm space-y-1">
          <p className="font-semibold">No prediction was produced for {job.cropCode}.</p>
          <p className="text-muted-foreground">The research model requires 2001–2020 climate inputs and SoilGrids soil inputs for this exact location. Planner data from other periods are not substituted.</p>
        </div>
      )}
      {job.reasons.length > 0 && <ul className="list-disc pl-5 text-sm space-y-0.5">{job.reasons.map((r) => <li key={r}>{r.replaceAll("_", " ")}</li>)}</ul>}
      {job.supportReasons && job.supportReasons.length > 0 && <ul className="list-disc pl-5 text-sm space-y-0.5">{job.supportReasons.map((r) => <li key={r}>{r.replaceAll("_", " ")}</li>)}</ul>}
      {job.warnings && job.warnings.length > 0 && <ul className="list-disc pl-5 text-sm space-y-0.5">{job.warnings.map((r) => <li key={r}>{r}</li>)}</ul>}
      <p className="text-xs text-muted-foreground">Model inputs use 2001–2020 NASA POWER climate at the containing five-arc-minute label-cell center and native SoilGrids area means over that cell. These are not farm soil tests or farm-boundary averages.</p>
      {job.inputSummary && <details className="text-xs">
        <summary className="cursor-pointer font-semibold">Model input provenance</summary>
        <pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(job.inputSummary, null, 2)}</pre>
      </details>}
      <dl className="grid sm:grid-cols-2 gap-2">
        <Kv k="Job" v={job.jobId} />
        {job.geographicSupport && <Kv k="Geographic support" v={job.geographicSupport} />}
        {coords.map(([k, v]) => <Kv key={k} k={`Requested ${k}`} v={String(v)} testid={`text-requested-${k}`} />)}
        {job.status === "experimental_output" && <>
          <Kv k="modelVersion" v={job.modelVersion ?? "not reported"} />
          <Kv k="datasetHash" v={job.datasetHash ?? "not reported"} />
          <Kv k="artifactSha256" v={job.artifactSha256 ?? "not reported"} />
        </>}
        {job.createdAt && <Kv k="Created" v={job.createdAt} />}
        {job.completedAt && <Kv k="Completed" v={job.completedAt} />}
      </dl>
    </div>
  );
}

export function ExperimentalMl({ farmId }: { farmId: number }) {
  const status = useGetExperimentalStatus(farmId, { query: { queryKey: getGetExperimentalStatusQueryKey(farmId), retry: false, staleTime: 60_000 } });
  const [crop, setCrop] = useState<ExperimentalPredictionInputCropCode | "">(() => restoreCrop(farmId));
  const qc = useQueryClient();
  const selection = useRef({ farmId, crop });
  selection.current = { farmId, crop };
  const [ack, setAck] = useState(false);
  const [jobId, setJobId] = useState("");
  const [initial, setInitial] = useState<ExperimentalJob | null>(null);
  const [error, setError] = useState("");
  const [stopped, setStopped] = useState(false);
  const run = useRunExperimentalPrediction();

  // Reset on farm/crop change; rehydrate only the stored jobId for this exact farm+crop.
  useEffect(() => {
    setInitial(null); setError(""); setAck(false); setStopped(false); run.reset();
    setJobId(crop ? sessionStorage.getItem(storeKey(farmId, crop)) ?? "" : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [farmId, crop]);

  const job = useGetExperimentalJob(farmId, jobId, {
    query: {
      queryKey: getGetExperimentalJobQueryKey(farmId, jobId),
      enabled: !!jobId && !stopped,
      retry: false,
      refetchInterval: (q) => (q.state.data ? q.state.data.status === "preparing" : initial?.status === "preparing") ? 3000 : false,
    },
  });

  useEffect(() => {
    if (!job.isError) return;
    const s = errStatus(job.error);
    setError(errText(job.error));
    if (s !== undefined && TERMINAL_STOP.has(s)) {
      setStopped(true); setInitial(null);
      if (crop) sessionStorage.removeItem(storeKey(farmId, crop));
      setJobId("");
    }
  }, [job.isError, job.error, farmId, crop]);

  const current = (job.data && job.data.jobId === jobId ? job.data : null) ?? (initial && initial.jobId === jobId ? initial : null);
  const shown = current && current.cropCode === crop ? current : null;

  function submit(retry = false) {
    if (!crop || !ack) return;
    const forCrop = crop;
    const forFarm = farmId;
    const isActive = () => selection.current.farmId === forFarm && selection.current.crop === forCrop;
    setError("");
    run.mutate({ id: farmId, data: { cropCode: forCrop, acknowledgeWarning: true, ...(retry ? { retry: true } : {}) } }, {
      onSuccess: (j) => {
        sessionStorage.setItem(storeKey(forFarm, forCrop), j.jobId);
        // Seed cache so a reused jobId's old terminal data cannot override the fresh response.
        qc.setQueryData(getGetExperimentalJobQueryKey(forFarm, j.jobId), j);
        if (!isActive()) return;
        setStopped(false); setInitial(j); setJobId(j.jobId);
      },
      onError: (e) => { if (isActive()) setError(errText(e)); },
    });
  }

  const s = status.data;
  return (
    <section className="min-w-0 max-w-full rounded-3xl border-2 border-dashed border-[hsl(38_70%_50%/.55)] bg-card p-5 md:p-6 space-y-4" aria-labelledby="experimental-ml-heading" data-testid="experimental-ml">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2"><FlaskConical className="h-5 w-5 text-accent" aria-hidden /><h3 id="experimental-ml-heading" className="font-display text-xl text-primary">Experimental ML predictions</h3></div>
        <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => status.refetch()} disabled={status.isFetching} data-testid="button-refresh-experimental">
          {status.isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}Refresh status
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">Separate research surface. Results here are never used by saved reports, reference planning, or any recommendation.</p>
      <p className="text-xs text-muted-foreground">Target: historical GAEZ-style suitability, 0–10,000 index points, rain-fed low-input management (LRLM). MAE uses index points; the metrics below describe development validation before the failed geographic-support screen, not final-test or local-farm accuracy.</p>
      <p role="note" className="rounded-xl bg-[hsl(38_70%_50%/.14)] px-3 py-2 text-sm font-semibold" data-testid="text-experimental-warning">{WARNING}</p>

      {status.isLoading ? <Skeleton className="h-24 rounded-2xl" />
        : status.isError || !s ? (
          errStatus(status.error) === 401 || errStatus(status.error) === 403 ? (
            <p className="flex items-center gap-2 text-sm" data-testid="text-experimental-locked"><Lock className="h-4 w-4" />Locked: development access only.</p>
          ) : <p role="alert" className="text-sm text-destructive">{errText(status.error)}</p>
        ) : !s.authorized ? (
          <div className="flex items-start gap-2 text-sm" data-testid="text-experimental-locked"><Lock className="h-4 w-4 mt-0.5 shrink-0" /><div><p className="font-semibold">Locked: development access only.</p><p className="text-muted-foreground">{s.reason}</p></div></div>
        ) : !s.available ? (
          <div className="text-sm" role="status" data-testid="text-experimental-unavailable"><p className="font-semibold">Experimental models are unavailable.</p><p className="text-muted-foreground">{s.reason}</p><p className="text-muted-foreground mt-1">Use Refresh status to check again.</p></div>
        ) : (
          <>
            <p className="text-xs font-mono text-muted-foreground">productionPredictionsEnabled: {String(s.productionPredictionsEnabled)} · {s.reason}</p>
            <div className="grid md:grid-cols-2 gap-3">
              {s.models.map((m) => (
                <div key={m.cropCode} className="rounded-2xl border border-border p-3 space-y-2" data-testid={`experimental-model-${m.cropCode}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-sm">{m.name} ({m.cropCode})</span><span className="rounded-full bg-destructive/10 text-destructive px-2 py-0.5 font-mono text-[10.5px] uppercase">{m.validationStatus.replaceAll("_", " ")}</span></div>
                  <dl className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    <Kv k="Selected" v={m.selected} /><Kv k="Validation MAE" v={num(m.validationMae)} /><Kv k="Validation R²" v={num(m.validationR2)} />
                    <Kv k="Mean baseline MAE" v={num(m.meanBaselineMae)} /><Kv k="Median baseline MAE" v={num(m.medianBaselineMae)} /><Kv k="Cells train / valid" v={`${m.trainedCells} / ${m.validationCells}`} />
                  </dl>
                  {m.rejectionReasons.length > 0 && <ul className="list-disc pl-5 text-xs space-y-0.5">{m.rejectionReasons.map((r) => <li key={r}>{r.replaceAll("_", " ")}</li>)}</ul>}
                  <p className="text-xs text-muted-foreground"><span className="font-semibold">Geographic limits:</span> {m.geographicLimitations}</p>
                </div>
              ))}
            </div>
            <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
              <div className="space-y-1.5">
                <Label htmlFor="exp-crop" className="text-xs uppercase tracking-wider">Crop (explicit selection required)</Label>
                <select id="exp-crop" value={crop} onChange={(e) => {
                  const v = e.target.value as ExperimentalPredictionInputCropCode | "";
                  if (v) sessionStorage.setItem(cropKey(farmId), v); else sessionStorage.removeItem(cropKey(farmId));
                  setCrop(v);
                }} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" data-testid="select-experimental-crop">
                  <option value="">Select a crop...</option>
                  {CROPS.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
              </div>
              <Button type="button" onClick={() => submit(false)} disabled={!crop || !ack || run.isPending} className="rounded-full" data-testid="button-run-experimental">
                {run.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Run experimental model
              </Button>
            </div>
            <div className="flex items-start gap-2">
              <Checkbox id="exp-ack" checked={ack} onCheckedChange={(v) => setAck(v === true)} disabled={!crop} data-testid="checkbox-experimental-ack" />
              <Label htmlFor="exp-ack" className="text-sm font-normal leading-snug">I understand this model failed validation and its output must not be used for real farming decisions.</Label>
            </div>
            {error && (
              <div role="alert" className="rounded-xl bg-destructive/10 text-destructive px-3 py-2 text-sm flex flex-wrap items-center justify-between gap-2" data-testid="text-experimental-error">
                <span>{error}</span>
                {crop && ack && <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => submit(true)} disabled={run.isPending} data-testid="button-retry-experimental">Retry</Button>}
              </div>
            )}
            {shown && <JobView job={shown} />}
            {shown && shown.status === "interrupted" && ack && <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => submit(true)} disabled={run.isPending} data-testid="button-rerun-experimental">Retry interrupted job</Button>}
          </>
        )}
    </section>
  );
}
