# SignalDesk production collector: read-only release preflight

This checklist is deliberately independent of deployment. A passing workflow
cannot and does not authorize a production change.

## Baseline from read-only GitHub Actions on 2026-11-01 07:51 UTC

- Static public preview `data.json`: **50 Global, 25 India**, 38 story image
  URLs across both regions, generated 2026-11-01 07:44:49 UTC.
- Current live Worker `/feed`: **30 news records**; India live count was not
  separately printed by that older audit. Worker snapshot age ~6 minutes.
- Health endpoint returned HTTP 200. **Preview origin CORS failed** and
  **untrusted origin CORS was incorrectly allowed**, according to the public
  GET audit. HTTP 200 alone is insufficient to claim browser access is safe.
- The active source code is `chiru52/x-news-automation`, but
  `.github/workflows/deploy-news-collector.yml` runs the actual deploy only
  when `github.repository == 'varadachiru/x-news-automation'`. It also
  dispatches a Pages rebuild, so changing that guard is not a safe shortcut.
- PR #28 added India's 72h live freshness and official PIB RSS to **code**.
  GitHub merging it did NOT deploy the production Worker.

## Safe steps before any deployment

1. In **chiru52/x-news-automation > Actions**, manually run
   **SignalDesk deployment readiness — GET-only (never deploy)**. It uses
   only the hardcoded public Worker and public preview URLs; no credentials,
   Cloudflare API requests, KV writes or X actions.
2. Read the run summary. Its five health/CORS/feed/archive checks must all
   PASS **after a candidate deployment**. Before an approved rollout, the
   currently deployed older Worker may intentionally fail the contract/CORS
   checks. That failure confirms the deployed version needs an update; it is
   **not permission to bypass controls** or to auto-deploy.
3. In the Cloudflare dashboard (read-only), confirm actual Worker identity,
   account, installed `NEWS_CACHE` binding, 15-minute Cron, routes, existing
   last known good deployment, and the preview/production CORS allowlist.
   Identify why the deployed Worker is returning incorrect CORS headers;
   the repository Worker code currently includes a narrow origin allowlist.
   Preserve a tested rollback target and avoid changing other Workers.
4. Check the live Worker serves 5–50 Global and 0–50 India dated stories.
   Confirm publisher timestamps and 72h India/36h Global caps, no fake
   headline padding, official PIB labels and headline/link-only treatment.
   Verify source failures, archive and images, and live CORS from an actual
   browser. Publisher photo counts cannot prove an image has the right licence.
5. Obtain **separate explicit approval** to deploy production Worker changes.
   Deploy ONLY the approved dedicated news collector after confirming all
   Cloudflare safeguards. Do not automatically dispatch the legacy Pages
   deployment, migrate private drafts, use X credentials or enable auto-send.
6. Repeat read-only checks after deployment and one scheduled collection
   cycle; compare India counts and monitor feed errors. Roll back on a failing
   CORS/safety check or unexpectedly missing reporting.

## Limits

- Live checks use GET-only public endpoints and bounded responses. No third
  party article URLs or user-provided URLs are fetched.
- The ready/not-ready result is a **preflight signal**, not proof of Cron,
  KV health, feed licensing, live publishing provenance or Cloudflare quotas.
- This preflight does **not** modify production and makes **no guarantee**
  that India reaches 50 valid articles.

## Phase 1A: Story-integrity and deployed-code fingerprint (2026-11-01)

- A recent `generated_at` alone does **not** prove recent reporting. The
  read-only release probe now checks all at-most-100 article objects: valid
  attributed HTTPS source links, unique IDs and URLs, exact region labels,
  category allowlist, unverified state, safe image URLs, and actual publisher
  timestamps (Global <=36 hours, India <=72 hours, future allowance 10 min).
  The audit logs only bounded error categories and counts, **never** titles,
  URLs or other source text.
- `/health` exposes a fixed, public, non-secret contract marker
  `rss-v2-india72-exact-origin`. A 200 response with an outdated or absent
  marker cannot pass live release verification. This catches GitHub/Pages code
  being newer than the actual Worker deployment.
- No new Cloudflare requests or KV writes are added to the scheduled Worker;
  existing browser GETs remain cached, no RSS is fetched per visitor.
- The checks and contract live in source until a separate operator-approved
  Worker deployment. **Merging this PR does not change Cloudflare.**
- Candidate code validation (green offline tests), current-deployment diagnosis
  (possibly red), explicit production authorization, controlled Worker deploy,
  then post-deployment read-only green validation are **separate gates**.
