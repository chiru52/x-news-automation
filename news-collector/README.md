# SignalDesk shared 15-minute news collector

This is a separate Cloudflare Worker, not a change to X posting or the AI gateway.

- A Cloudflare Cron Trigger runs every 15 minutes (UTC).
- Each scheduled run reads up to 14 configured public RSS feeds, with 9-second timeouts and up to 400 KB per source.
- It selects up to 30 relevant, nonduplicate headlines, prepares attributed rule-based writing suggestions, and writes ONE public JSON snapshot into a dedicated KV namespace.
- All visitors share that snapshot. A browser GET reads KV only; a browser never starts upstream RSS collection.
- The existing daily static dashboard and AI draft library remain the fallback when the Worker is not ready.
- RSS preview snippets are unverified; no full article fetching, AI calls, X APIs or automatic posting.

## Activation

The GitHub Action in .github/workflows/deploy-news-collector.yml provisions or reuses exactly the namespace named signaldesk-news-shared-cache, deploys the separate Worker signaldesk-news-feed, verifies its /health endpoint, and dispatches a public Pages rebuild.

The Pages build discovers the verified Worker URL and adds the exact origin to the generated Content Security Policy. If Cloudflare permissions or endpoint verification fail, frontend feed-config.json remains disabled and the static website keeps working.

Worker activation requires account-scoped Cloudflare API permissions Workers Scripts Edit and Workers KV Storage Edit. An existing Pages-only token may receive HTTP 403. Do not replace it with a Global API key or grant unrelated privileges. The dedicated Worker URL may take up to one cron interval to receive its first data.

## Cost and usage

At 15-minute intervals there are around 96 runs and 96 KV writes per day, plus around 14 upstream RSS fetches per run. According to Cloudflare October 2026 docs, the free Workers KV tier offers 1,000 writes and 100,000 reads daily, and Workers Free offers 100,000 requests daily with 50 external subrequests/invocation. These are account-wide limits, not guarantees of remaining capacity or adequate free-plan CPU time. Each browser fetch counts as a read. Monitor actual usage and review billing before scaling.

https://developers.cloudflare.com/workers/configuration/cron-triggers/
https://developers.cloudflare.com/workers/platform/limits/
https://developers.cloudflare.com/kv/platform/limits/

## Testing

Run with Node 22:
- npm install --prefix news-collector --no-audit --no-fund
- node --test tests/signaldesk-news-collector.test.mjs
- python -m unittest discover -s tests -v

All these tests are local/fake; no Cloudflare writes or AI/X calls.
