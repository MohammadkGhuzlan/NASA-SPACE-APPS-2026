import { useGetAnalysisModelStatus, type AnalysisIntegration } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";

/** An evidence lane, not a suitability dashboard. Saved reports retain their snapshot. */
export function AnalysisStatus({ evidence }: { evidence?: AnalysisIntegration }) {
  const query = useGetAnalysisModelStatus({
    query: { enabled: !evidence, staleTime: 60_000, retry: 1 },
  });
  const status = evidence?.model ?? query.data;
  const reasons = evidence?.featurePreparation.unavailableReasons;
  return (
    <section className="rounded-3xl border border-card-border bg-card p-5 space-y-3"
      aria-labelledby={evidence ? "saved-analysis-status" : "analysis-status"} data-testid="analysis-status">
      <h3 id={evidence ? "saved-analysis-status" : "analysis-status"}
        className="font-display text-xl text-primary">Is the crop model ready?</h3>
      {!status ? (
        <div role="status">
          <p className="text-sm text-muted-foreground">{query.isError
            ? "Model availability could not be checked. Reference planning remains available."
            : "Checking model availability. This does not run a prediction."}</p>
          {query.isError && <Button type="button" variant="outline" className="mt-2"
            onClick={() => query.refetch()}>Retry availability check</Button>}
        </div>
      ) : <>
        <p className="text-sm font-semibold">
          {status.state === "unvalidated_enabled" ? "The test model can run, but it may be wrong."
            : status.state === "insufficiently_validated" ? "The model test did not pass its checks."
            : status.state === "validated_ready" ? "A model passed review and is ready."
            : status.state === "temporarily_unavailable" ? "The model is not ready right now."
            : status.state === "incompatible" ? "The model cannot use these inputs."
            : "No crop model is ready."}
        </p>
        <p className="text-sm text-muted-foreground">
          {status.state === "unvalidated_enabled"
            ? "It failed its checks. Do not use its number to choose crops. Saved test numbers keep their warning. Crop plans use crop-guide facts, not this model."
            : status.state === "insufficiently_validated"
              ? "The model did not pass its checks."
              : status.state === "validated_ready" ? "This model passed review."
              : status.state === "temporarily_unavailable" ? "Try again later."
              : status.state === "incompatible" ? "This model does not fit the data it was given."
              : "The app has no crop model to use right now."}{" "}
          NASA weather and FAO crop maps are still available. This does not predict how much you will harvest.
        </p>
        {status.message && <details className="text-xs">
          <summary className="cursor-pointer font-semibold">More model details</summary>
          <p className="mt-2 text-muted-foreground">{status.message}</p>
        </details>}
        {evidence && <>
          <p className="text-xs text-muted-foreground">Saved evidence snapshot: {new Date(evidence.generatedAt).toLocaleString()}.
            {" "}Reopened reports keep the inputs and availability recorded when generated.</p>
          <p className="text-sm">{evidence.plannerUse}</p>
          <details className="text-sm">
            <summary className="cursor-pointer font-semibold">Model status reasons</summary>
            <p className="mt-2 text-muted-foreground">Environmental data access:{" "}
              {String((evidence.featurePreparation.environmentRetrieval as Record<string, unknown> | undefined)?.mode ?? "recorded in environmental provenance").replaceAll("_", " ")}.
              {" "}Original source timestamps remain in the environmental dashboard.</p>
            <ul className="list-disc pl-5 mt-2 space-y-1">
              {status.reasons.map((r) => <li key={r}>{r.replaceAll("_", " ")}</li>)}
              {Array.isArray(reasons) && reasons.filter((r): r is string => typeof r === "string")
                .map((r) => <li key={r}>{r.replaceAll("_", " ")}</li>)}
            </ul>
            <p className="mt-3 text-muted-foreground">
              Farmer soil entries remain self-reported. Nearby SoilGrids proxies are not farm tests.
              POWER modeled wetness is not SMAP. The planner’s 2019–2025 data are not relabeled as
              the research model’s 2001–2020 inputs. No farm-boundary climate aggregation was calculated.
            </p>
            <ul className="mt-3 space-y-1">
              {evidence.coverage.map((c) => <li key={c.crop}>
                <span className="font-semibold">{c.crop}:</span> {c.status.replaceAll("_", " ")}{c.available ? "" : " (no prediction in this lane)"}
              </li>)}
            </ul>
          </details>
        </>}
      </>}
    </section>
  );
}
