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
import { ML_WARNING as WARNING, MlJobView } from "@/components/ml-job-view";
import { estimateAdmission, secondsUntil } from "@/lib/estimate-admission";

const CROPS: { code: ExperimentalPredictionInputCropCode; label: string }[] = [
  { code: "WHE", label: "Wheat" },
  { code: "BRL", label: "Barley" },
  { code: "MZE", label: "Maize" },
  { code: "RCD", label: "Rice · dryland" },
  { code: "RCW", label: "Rice · wetland" },
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
const num = (n: number | null | undefined) => (n === null || n === undefined ? "not reported" : Number.isInteger(n) ? String(n) : n.toFixed(3));
function Kv({ k, v }: { k: string; v: string }) {
  return <div className="min-w-0"><dt className="text-[10.5px] uppercase tracking-wider text-muted-foreground">{k}</dt><dd className="font-mono text-xs break-all [overflow-wrap:anywhere]">{v}</dd></div>;
}

export function ExperimentalMl({ farmId }: { farmId: number }) {
  const status = useGetExperimentalStatus(farmId, { query: { queryKey: getGetExperimentalStatusQueryKey(farmId), retry: false, staleTime: 60_000 } });
  const [crop, setCrop] = useState<ExperimentalPredictionInputCropCode | "">(() => restoreCrop(farmId));
  const qc = useQueryClient();
  const selection = useRef({ farmId, crop });
  selection.current = { farmId, crop };
  const [ack, setAck] = useState(false);
  const [allowEst, setAllowEst] = useState(true);
  const [jobId, setJobId] = useState("");
  const [initial, setInitial] = useState<ExperimentalJob | null>(null);
  const [error, setError] = useState("");
  const [stopped, setStopped] = useState(false);
  const [wait, setWait] = useState<{ deadline: number; message: string } | null>(null);
  const [clock, setClock] = useState(Date.now);
  const waitSeconds = wait ? secondsUntil(wait.deadline, clock) : 0;
  const run = useRunExperimentalPrediction();

  useEffect(() => {
    if (!wait) return;
    const timer = window.setInterval(() => setClock(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [wait]);
  useEffect(() => { setWait(null); }, [farmId]);

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
    const st = errStatus(job.error);
    setError(errText(job.error));
    if (st !== undefined && TERMINAL_STOP.has(st)) {
      setStopped(true); setInitial(null);
      if (crop) sessionStorage.removeItem(storeKey(farmId, crop));
      setJobId("");
    }
  }, [job.isError, job.error, farmId, crop]);

  const current = (job.data && job.data.jobId === jobId ? job.data : null) ?? (initial && initial.jobId === jobId ? initial : null);
  const shown = current && current.cropCode === crop ? current : null;
  const preparing = shown?.status === "preparing";
  const failed = !!shown && ["missing_inputs", "unavailable", "interrupted"].includes(shown.status);

  function submit(retry = false) {
    if (!crop || !ack || run.isPending || preparing || (wait && secondsUntil(wait.deadline, Date.now()) > 0)) return;
    const forCrop = crop;
    const forFarm = farmId;
    const isActive = () => selection.current.farmId === forFarm && selection.current.crop === forCrop;
    setError("");
    setWait(null);
    run.mutate({ id: farmId, data: { cropCode: forCrop, acknowledgeWarning: true, allowEstimatedInputs: allowEst, ...(retry ? { retry: true } : {}) } }, {
      onSuccess: (j) => {
        sessionStorage.setItem(storeKey(forFarm, forCrop), j.jobId);
        // Seed cache so a reused jobId's old terminal data cannot override the fresh response.
        qc.setQueryData(getGetExperimentalJobQueryKey(forFarm, j.jobId), j);
        if (!isActive()) return;
        setStopped(false); setInitial(j); setJobId(j.jobId);
      },
      onError: (e) => {
        // Admission is per workspace, not crop. Preserve the wait when the
        // user changes crop while the request is in flight.
        const admission = estimateAdmission(e);
        if (admission && selection.current.farmId === forFarm) {
          const now = Date.now();
          setClock(now);
          setWait({ deadline: now + admission.retryAfterSeconds * 1000, message: admission.message });
        } else if (isActive()) setError(errText(e));
      },
    });
  }

  const s = status.data;
  return (
    <section className="min-w-0 max-w-full rounded-3xl border-2 border-dashed border-[hsl(38_70%_50%/.55)] bg-card p-5 md:p-6 space-y-4" aria-labelledby="experimental-ml-heading" data-testid="experimental-ml">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2"><FlaskConical className="h-5 w-5 text-accent" aria-hidden /><h3 id="experimental-ml-heading" className="font-display text-xl text-primary">Unvalidated ML predictions</h3></div>
        <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => status.refetch()} disabled={status.isFetching} data-testid="button-refresh-experimental">
          {status.isFetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}Refresh status
        </Button>
      </div>
      <ol className="rounded-2xl bg-secondary/60 px-4 py-3 text-sm space-y-1 list-decimal pl-8" data-testid="text-ml-workflow">
        <li>Choose a crop, confirm the warning and run the model here. Repeat for each crop you want.</li>
        <li>Wait until each run finishes, then use <span className="font-semibold">Generate and save report</span> below. Completed outputs for this farm location are snapshotted into that new report with their warnings.</li>
      </ol>
      <p className="text-xs text-muted-foreground">Nothing runs automatically: a report only contains model outputs you ran first. Agronomic reference rules still choose the three rotation strategies; the models do not rank rotations.</p>
      <p className="text-sm text-muted-foreground">This experiment estimates a historical crop-suitability index for rain-fed, low-input conditions. It is not a percentage, yield, probability, or assessment of this farm. The model did not pass scientific acceptance.</p>
      <p role="note" className="rounded-xl bg-[hsl(38_70%_50%/.14)] px-3 py-2 text-sm font-semibold" data-testid="text-experimental-warning">{WARNING}</p>
      <div role="note" className="rounded-xl border border-border bg-secondary/50 px-3 py-2 text-sm" data-testid="text-ml-input-contract">
        <span className="font-semibold">Inputs used in this experiment:</span> the selected farm point, chosen crop, observed historical NASA POWER climate data (2001–2020), and topsoil estimates from ISRIC SoilGrids (0–5 cm). SoilGrids values are regional proxies, not measurements at this farm. Farm-entered soil values, crop history, irrigation, and priorities are stored separately and are not inputs to this model.
      </div>

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
            <p className="text-sm" data-testid="text-ml-status">{s.productionPredictionsEnabled ? "Experimental predictions are enabled for testing." : "Experimental predictions are not currently enabled."}{" "}{s.scientificallyValidated ? "" : "They are not validated for farming decisions and have no calibrated confidence."}</p>
            <details className="text-xs" data-testid="details-experimental-availability"><summary className="cursor-pointer text-accent">Availability details</summary><p className="mt-1 font-mono text-muted-foreground break-all">{s.reason.replaceAll("_", " ")}</p></details>
            <div className="grid md:grid-cols-2 gap-3">
              {s.models.map((m) => (
                <div key={m.cropCode} className="rounded-2xl border border-border p-3 space-y-2" data-testid={`experimental-model-${m.cropCode}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-sm">{m.name}</span><span className="rounded-full bg-destructive/10 text-destructive px-2 py-0.5 text-[10.5px] font-semibold uppercase">Not validated</span></div>
                  <details className="text-xs" data-testid={`details-model-metrics-${m.cropCode}`}><summary className="cursor-pointer font-semibold text-accent">Validation metrics and limits</summary>
                    <p className="mt-2 text-muted-foreground">MAE is the average size of prediction errors, measured in index points. R² describes fit to the development data. These are not local-farm accuracy estimates.</p>
                    <dl className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
                      <Kv k="Model variant" v={m.selected} /><Kv k="Validation MAE" v={num(m.validationMae)} /><Kv k="Validation R²" v={num(m.validationR2)} />
                      <Kv k="Mean baseline MAE" v={num(m.meanBaselineMae)} /><Kv k="Median baseline MAE" v={num(m.medianBaselineMae)} /><Kv k="Training / validation cells" v={`${m.trainedCells} / ${m.validationCells}`} />
                    </dl>
                    <p className="mt-2 text-muted-foreground">These development metrics are not estimates of accuracy for a local farm. The model also failed its geographic-support screen.</p>
                    {m.rejectionReasons.length > 0 && <ul className="mt-2 list-disc pl-5 space-y-0.5">{m.rejectionReasons.map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}</ul>}
                    <p className="mt-2 text-muted-foreground"><span className="font-semibold">Geographic limits:</span> {m.geographicLimitations}</p>
                    <p className="mt-2 font-mono text-muted-foreground">Crop code: {m.cropCode} · Validation status: {m.validationStatus.replaceAll("_", " ")}</p>
                  </details>
                </div>
              ))}
            </div>
            <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end">
              <div className="space-y-1.5">
                <Label htmlFor="exp-crop" className="text-xs uppercase tracking-wider">Choose a crop for the test</Label>
                <select id="exp-crop" value={crop} onChange={(e) => {
                  const v = e.target.value as ExperimentalPredictionInputCropCode | "";
                  if (v) sessionStorage.setItem(cropKey(farmId), v); else sessionStorage.removeItem(cropKey(farmId));
                  setCrop(v);
                }} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" data-testid="select-experimental-crop">
                  <option value="">Select a crop...</option>
                  {CROPS.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
              </div>
              <Button type="button" onClick={() => submit(failed)} disabled={!crop || !ack || run.isPending || preparing || waitSeconds > 0} className="rounded-full" data-testid="button-run-experimental">
                {run.isPending && <Loader2 className="h-4 w-4 animate-spin" />}{waitSeconds > 0 ? `Retry in ${waitSeconds}s` : preparing ? "Estimate running" : failed ? "Retry experimental model" : "Run experimental model"}
              </Button>
            </div>
            {wait && <div role="status" className="rounded-xl border border-border bg-secondary/60 px-3 py-2 text-sm" data-testid="text-estimate-admission">
              <p>{wait.message}</p>
              <p className="font-semibold">{waitSeconds > 0 ? `Retry in ${waitSeconds} second${waitSeconds === 1 ? "" : "s"}.` : "You can retry now. No run has been started automatically."}</p>
            </div>}
            <div className="flex items-start gap-2">
              <Checkbox id="exp-ack" checked={ack} onCheckedChange={(v) => setAck(v === true)} disabled={!crop} data-testid="checkbox-experimental-ack" />
              <Label htmlFor="exp-ack" className="text-sm font-normal leading-snug">I understand this model failed validation and its output must not be used for real farming decisions.</Label>
            </div>
            <div className="flex items-start gap-2 rounded-xl border border-border p-3">
              <Checkbox id="exp-est" checked={allowEst} onCheckedChange={(v) => setAllowEst(v === true)} data-testid="checkbox-allow-estimated" />
              <Label htmlFor="exp-est" className="text-sm font-normal leading-snug"><span className="font-semibold">Allow estimated soil inputs.</span> If SoilGrids does not fully cover this cell, use partial coverage or the nearest recorded training cell. Results are flagged as estimated. Untick to require original inputs only.</Label>
            </div>
            {error && (
              <div role="alert" className="rounded-xl bg-destructive/10 text-destructive px-3 py-2 text-sm flex flex-wrap items-center justify-between gap-2" data-testid="text-experimental-error">
                <span>{error}</span>
                {crop && ack && <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => submit(true)} disabled={run.isPending || preparing || waitSeconds > 0} data-testid="button-retry-experimental">Retry</Button>}
              </div>
            )}
            {shown && <MlJobView job={shown} />}
            {shown && shown.allowEstimatedInputs !== allowEst && <p className="text-sm text-muted-foreground" data-testid="text-estimate-inputs-changed">The displayed run used a different estimated-soil setting. Run again to apply the current setting; the previous result has not been changed.</p>}
            {failed && ack && <Button type="button" size="sm" variant="outline" className="rounded-full" onClick={() => submit(true)} disabled={run.isPending || waitSeconds > 0} data-testid="button-rerun-experimental">Retry with current input settings</Button>}
          </>
        )}
    </section>
  );
}
