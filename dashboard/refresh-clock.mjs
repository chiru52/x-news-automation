/**
 * Client-side snapshot checks are aligned with the backend's UTC quarter-hour
 * Cloudflare Cron schedule, but slightly delayed to allow RSS collection and
 * KV propagation. This does NOT start collection or post anything.
 */
export const FEED_CHECK_INTERVAL_MS = 15 * 60 * 1000;
export const FEED_CHECK_LAG_MS = 2 * 60 * 1000;
export const MIN_RETURN_CHECK_AGE_MS = 2 * 60 * 1000;
export const MAX_JITTER_MS = 45 * 1000;

export function nextFeedCheckAt(nowMs, jitterMs = 0) {
  if (!Number.isFinite(nowMs) || nowMs < 0) throw new RangeError("Invalid current time");
  const jitter = Number.isFinite(jitterMs)
    ? Math.min(MAX_JITTER_MS, Math.max(0, Math.trunc(jitterMs))) : 0;
  const phase = FEED_CHECK_LAG_MS + jitter;
  return (Math.floor((nowMs - phase) / FEED_CHECK_INTERVAL_MS) + 1)
    * FEED_CHECK_INTERVAL_MS + phase;
}

export function shouldCheckAfterReturn(nowMs, lastCheckAtMs) {
  return Number.isFinite(nowMs) && Number.isFinite(lastCheckAtMs) &&
    nowMs - lastCheckAtMs >= MIN_RETURN_CHECK_AGE_MS;
}
