/** Keep first-time NASA retrieval in the loading state; never retry forever. */
function statusOf(error: unknown): number | undefined {
  return typeof error === "object" && error !== null && "status" in error
    && typeof error.status === "number" ? error.status : undefined;
}

export function retryEnvironment(failureCount: number, error: unknown): boolean {
  const status = statusOf(error);
  if (status === 409) return failureCount < 6;
  // In particular, respect the shared 429 admission limit rather than
  // automatically sending the same expensive request again.
  if (status !== undefined && status >= 400 && status < 500) return false;
  return failureCount < 1;
}

export function environmentRetryDelay(attempt: number, error: unknown): number {
  return statusOf(error) === 409 ? Math.min(2000 * 2 ** attempt, 20_000) : 1000;
}
