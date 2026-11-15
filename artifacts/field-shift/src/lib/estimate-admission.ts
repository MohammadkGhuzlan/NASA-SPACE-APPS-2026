import type { EstimateAdmissionError } from "@workspace/api-client-react";

type Wait = EstimateAdmissionError["detail"];

// Do not automatically resubmit paid/source requests. The timer only unlocks
// an explicit retry. Structured admission errors are not data-preparation errors.
export function estimateAdmission(error: unknown): Wait | null {
  const e = error as { status?: number; data?: { detail?: unknown }; headers?: Headers } | null;
  if (e?.status !== 429) return null;
  const detail = e.data?.detail;
  if (detail && typeof detail === "object") {
    const d = detail as Partial<Wait>;
    if ((d.code === "estimate_busy" || d.code === "estimate_cooldown")
      && typeof d.retryAfterSeconds === "number" && Number.isFinite(d.retryAfterSeconds) && d.retryAfterSeconds > 0) {
      return { code: d.code, retryAfterSeconds: Math.ceil(d.retryAfterSeconds),
        message: typeof d.message === "string" ? d.message : "Run admission is temporarily limited; source inputs have not failed." };
    }
  }
  const seconds = Number(e.headers?.get("Retry-After"));
  return { code: "estimate_cooldown", retryAfterSeconds: Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : 30,
    message: typeof detail === "string" ? detail : "Wait before trying another run. This is not a source-data failure." };
}

export function secondsUntil(deadline: number, now: number): number {
  return Math.max(0, Math.ceil((deadline - now) / 1000));
}
