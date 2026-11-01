# SignalDesk Phase 1B: controlled Worker release readiness

This is a **preparation-only** checklist. No repo merge, green unit test or
read-only inventory run is an authorization to change production.

## Confirmed gap (as of 2026-11-01)

- Latest tested RSS Worker code is on `chiru52/x-news-automation`.
- Production at `signaldesk-news-feed.littlekingchess.workers.dev` was observed
  with **outdated health contract**, **preview-origin CORS failure**, and
  **untrusted-origin CORS erroneously allowed** in the read-only audit.
- Its live snapshot failed strict validation on Global/India region labels.
- The daily preview previously had **50 Global / 25 India**. Static counts are
  not proof that the **live** Worker also has those articles.
- Current `.github/workflows/deploy-news-collector.yml` is scoped to the old
  `varadachiru` repository and could deploy Worker, provision KV, enable a
  public route and dispatch a Pages rebuild if its guard were bypassed.
  **Do not simply change its repository guard.** That is not a safe upgrade plan.

## Gate A — Read-only Cloudflare inventory

1. On the active `chiru52` repository, run the manually triggered
   **SignalDesk Cloudflare Worker inventory — READ ONLY** action.
2. Configure a dedicated `SIGNALDESK_CLOUDFLARE_READ_TOKEN` GitHub secret with
   **Workers Metadata Read-Only** (and only the minimum related read
   permissions needed by Cloudflare). Use existing account ID as a secret.
   Never paste tokens into chat or logs; do not substitute a write-scoped
   deployment token for this audit.
3. This workflow uses only GET requests to four fixed API paths for the
   dedicated `signaldesk-news-feed` script: `settings`, `schedules`,
   `deployments`, and `subdomain`. It never fetches Worker script content,
   KV contents, article pages, customer records or unrelated Worker services.
4. Require all checks to PASS: one dedicated `NEWS_CACHE` KV binding, one
   `*/15 * * * *` Cron, enabled Workers.dev route and a single 100% active
   deployment version. If Cloudflare permissions or response shapes are
   insufficient, result is **BLOCKED** rather than guessed.
5. Download and preserve the sanitized seven-day `signaldesk-worker-baseline`
   Actions artifact containing the **current deployment and version UUIDs**.
   This is a rollback *candidate*, not a tested rollback. Verify the
   Cloudflare dashboard can show and restore the exact previously active
   version before modifying production.

## Gate B — Candidate verification (offline, no writes)

1. Confirm the release commit and the exact intended Cloudflare account.
   Run all repository tests and inspect the Worker diff for changes outside
   `signaldesk-news-feed`. Verify the `news-collector/wrangler.template.jsonc`
   binding and Cron match the inventory.
2. Check live `/health`, `/feed` and `/archive?days=7` GET-only diagnostics.
   The **currently deployed older** Worker may fail these tests. Log all
   failures rather than making the preflight pass by weakening checks.
3. In a browser, confirm the preview `https://signaldesk-preview.pages.dev`
   and production `https://news.littlekingchess.com` both receive only their
   own exact `Access-Control-Allow-Origin`. An unapproved origin must receive
   none. Confirm the Worker allows GET/HEAD only.
4. Ensure a rollback choice is confirmed from the inventory, and preserve
   current Pages/static preview behavior as fallback. Do not overwrite
   browser-local draft storage or enable X publishing.

## Gate C — Separate deployment approval (NOT GRANTED)

Before any live Worker deployment, ask for a **new explicit approval** naming:
- Worker `signaldesk-news-feed`, release commit SHA and Cloudflare account;
- permission to update only this Worker, preserving its existing dedicated KV
  namespace and 15-minute Cron (no namespace creation, no other Workers);
- preservation of the previous Worker version for rollback;
- no Pages deployment, no route-enabling side effect, no RSS-to-X publishing,
  no secrets exposure, and no change to external customer messaging.

Deploy from a reviewed, manual-only release workflow after these gates.
The legacy automatic deploy workflow is **not** suitable to reuse unchanged.

## Gate D — After a separately approved release

- Verify `/health` includes `rss-v2-india72-exact-origin`, is read-only,
  and has AI generation and X publishing disabled.
- Validate CORS for both approved origins plus untrusted; audit all article
  publication timestamps (Global 36h, India 72h), exact region mapping,
  story ID/source link uniqueness, source failure counters and archive.
- Observe the first scheduled collection, check no extra KV writes or
  duplicate events, compare live and static counts without padding stories.
- **If any safety/CORS/collector check fails**, stop and select the preserved
  previous version via Cloudflare's Worker deployment rollback controls.
  Re-run read-only checks and preserve the static fallback. Never modify KV
  data as part of rollback.

## Explicitly out of scope

This phase does not enable auto-posting to X, bill customers, use AI models,
modify website CSS/UI, change Meta/Instagram settings, or guarantee exactly 50
India headlines on every day. Missing source permissions and publisher
licensing require separate review.
