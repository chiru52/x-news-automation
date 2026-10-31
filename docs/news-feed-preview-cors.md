# SignalDesk shared news feed: preview-origin read access

The read-only Cloudflare news Worker previously returned a fixed `Access-Control-Allow-Origin` for `https://news.littlekingchess.com`, blocking `https://signaldesk-preview.pages.dev` browser requests. The dashboard then legitimately falls back to its static daily news file.

This change lets the **existing** shared collector respond to both **exact** dashboard origins (production and preview), using the requesting Origin only when it matches the list. No wildcard, Access-Control-Allow-Credentials, secrets, new endpoints, paid APIs or extra RSS requests. Unauthorized origins receive no CORS allowance. The existing `Vary: Origin` stays in place, so cached responses can be handled correctly.

## Deployment safety

**Merging this PR into `chiru52/x-news-automation` does not deploy the shared news Worker.** The Cloudflare Pages preview build only generates the static website; the live collector is a separate Worker. Keep the current deployed Worker and its scheduled Cron unchanged until an explicit deployment approval and verification of the exact Worker service/bindings. Do not deploy the repository's unrelated `wrangler.toml`: it refers to the *editorial inbox* Worker, not the public news collector.

When deployment is separately approved:
1. Confirm the exact `signaldesk-news-feed` Worker and the existing `NEWS_CACHE` KV binding, schedule, and worker entrypoint in Cloudflare before deployment. Preserve these bindings and the schedule.
2. Deploy **only** the reviewed `news-collector/worker.mjs` bundle and test no other services changed.
3. Browser-test both origins with the public `/health` and `/feed` endpoints. An allowed Origin must receive the same exact `Access-Control-Allow-Origin` value.
4. Verify `/feed` returns a recent schema v1 snapshot (at least 5 news records and its real `generated_at`). The CORS fix alone does not make an unavailable, stale or empty collector healthy.
5. In preview, confirm the *Last refreshed* time uses live data, navigate India/Global/Trending and News Archive, then test that production remains healthy.
6. If the Worker is not healthy, retain the static fallback and investigate Cron, RSS failures, or KV state; don't make freshness claims based on a header fix.

There is no X publishing or AI billing. New traffic uses the same existing read-only API and stays subject to Cloudflare account free-plan usage limits.
