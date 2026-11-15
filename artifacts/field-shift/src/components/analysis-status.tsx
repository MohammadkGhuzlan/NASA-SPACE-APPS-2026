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
        className="font-display text-xl text-primary">AI crop-suitability availability</h3>
      {!status ? (
        <div role="status">
          <p className="text-sm text-muted-foreground">{query.isError
            ? "Model availability could not be checked. No prediction is enabled; reference planning remains available."
            : "Checking model availability. This does not run a prediction."}</p>
          {query.isError && <Button type="button" variant="outline" className="mt-2"
            onClick={() => query.refetch()}>Retry availability check</Button>}
        </div>
      ) : <>
        <p className="text-sm font-semibold">{status.message}</p>
        <p className="text-sm text-muted-foreground">
          Stage A only. {status.state === "insufficiently_validated"
            ? "Research candidates were trained but did not pass validation."
            : "No reviewed, accepted model is active."}
          Historical NASA data and agricultural reference rules remain available.
          No suitability value, confidence percentage, or similar-region estimate is being supplied.
        </p>
        {evidence && <>
          <p className="text-xs text-muted-foreground">Saved evidence snapshot: {new Date(evidence.generatedAt).toLocaleString()}.
            {" "}Reopened reports keep the inputs and availability recorded when generated.</p>
          <p className="text-sm">{evidence.plannerUse}</p>
          <details className="text-sm">
            <summary className="cursor-pointer font-semibold">Why predictions were withheld</summary>
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
                <span className="font-semibold">{c.crop}:</span> insufficient evidence — no prediction
              </li>)}
            </ul>
          </details>
        </>}
      </>}
    </section>
  );
}
