# SignalDesk — public Cloudflare news dashboard

## News History — rolling 30-day public archive

**All Stories → Browse news history (30 days)** opens a read-only archive explorer without adding an eighth sidebar item. Choose Last 7 days, Last 30 days, or a single UTC date, and filter by India/Global, publisher, news category and keyword. Search is initiated explicitly (button or Enter), and the response returns up to 60 articles per page.

Every successful 15-minute RSS collection writes one additional UTC daily KV bucket, key prefix `signaldesk:news:archive:v1:`, containing deduplicated public RSS headlines only (up to 120 URLs per day). No GitHub issues, user edits, passwords, personal information, private drafts, or full articles enter this storage. The live KV snapshot is written independently before archiving; archive storage failure does not interrupt live news.

The Worker exposes only a read-only GET /archive endpoint. It reads up to 30 daily KV keys, rejects dates outside the rolling 30-day interval, and applies keyword, source, region and category filters before paginating results. Each day bucket has a 32-day expiration TTL. Dates older than 30 days are not accessible via the API.

**History starts when this collector version is deployed and a successful scheduled run writes its first bucket.** The feature cannot backfill 30 days of old stories from previous live snapshots. The UI clearly explains an empty history.

Cost estimate: up to 96 extra KV writes/day, plus existing 96 live snapshot writes/day, about 192 writes/day in total if all scheduled runs succeed. 7-day searches require up to seven KV reads, and 30-day searches up to 30 KV reads. These are account-wide Cloudflare quota resources; monitor usage. Browsers never poll the archive in the background. No paid AI or X posting.


## Navigation: seven distinct sections

The sidebar has one simple menu with precisely seven choices: **All Stories,
Trending News, Global News, India News, My Workflow, Copied Articles,
Saved for Later**. The redundant sidebar Topics menu is removed; optional
inline AI/SaaS/Markets filters remain available next to search.

- **All Stories:** All current, non-copied and non-archived news from both
  Global and India. News tagged Trending is part of this view, not added again;
  the browser deduplicates by normalized source URL. Prepared draft records are
  not news and do not inflate the article count.
- **Trending News:** Five highest editorial-scoring eligible articles from the
  same combined Global + India news pool, regardless of origin. The score is
  an RSS relevance/recency heuristic, not social-media popularity.
- **Global News:** Current news articles that are *not* classified as India
  related (including articles from non-Indian publishers about other regions).
- **India News:** Current news articles classified as India related, including
  relevant stories from international publishers. A story can belong to exactly
  one of Global/India, while also appearing in All/Trending.
- **My Workflow:** Personal workflow with New, Reviewing, Ready, Copied and
  Archived filters, plus a **Prepared drafts** tab. This preserves the existing
  approved AI draft issue display after removing its redundant sidebar menu.
- **Copied Articles:** Items personally marked Copied or copied to clipboard,
  retained only in browser-local storage. Copied means *not posted to X*.
- **Saved for Later:** User-bookmarked items, also browser-local.

The region classifier first uses an explicit public region tag from the
scheduled Worker, then relevant India keywords and tightly named India
startup-focused sources for the daily static fallback. Classification is
heuristic; publisher country alone never labels a generic global article
as Indian.

No changes to Worker Cron, Cloudflare account settings, paid AI, login,
publishing permissions or X APIs are required for this navigation.


## Browser refresh timing and independently generated news timestamps

The Worker Cron Trigger is scheduled for **:00, :15, :30 and :45 UTC**. A dashboard tab that checked 15 minutes after it was first opened could run immediately *before* the next collector snapshot, then not check again for almost 15 more minutes. To reduce that lag without increasing the typical number of reads, browser checks are now aligned to **:02, :17, :32, :47 UTC**, with 0–45 seconds of per-tab jitter. Timers can still be delayed by Cloudflare propagation, a suspended browser, and throttling.

The dashboard reports **two different clocks**: `Last refreshed` is the timestamp the latest published news snapshot was generated; `Browser checked` is the time the tab last successfully checked the shared static/Worker feeds. No browser check timestamp is represented as a new news collection. The tab also checks again when it becomes visible after at least two minutes away. It fetches only already-published public JSON, never each upstream RSS feed or an AI/X endpoint.

Example: opening at 10:13 results in a check around 10:17 rather than automatically at 10:28. A snapshot built around 10:29 should usually be discovered around 10:32, not 10:43. A fresh snapshot can also be found when returning to the tab. There is no real-time push guarantee; reported timestamps continue to reflect actual backend data.


## India News and Copied Articles

**India News:** Separate sidebar view for India-relevant startup, AI, technology, and markets coverage. The shared 15-minute collector reads four additional public Indian publisher RSS feeds, marking stories only when a feed specifically focuses on India's startups or a headline contains clear Indian context (e.g. India, Bengaluru, RBI, Nifty). The dynamic feed now includes up to 15 separately selected India articles, retaining the original up-to-30 global news selection, source diversity caps, and an unchanged public fallback. General Indian-hosted publisher articles about global technology are *not automatically* labelled India news. Publisher RSS content is unverified.

**Copied Articles:** After a successful clipboard write, an article moves out of All Stories, Trending, India News and Saved into a dedicated Copied Articles section. The Undo banner reverses the move to its prior workflow status. The section keeps up to 100 safely bounded story snapshots and personal statuses **in the same browser only**, allowing copied items to remain accessible after news feed refreshes. This does not indicate any post actually appeared on X.

Visitors do not need accounts. Neither feature triggers AI inference, X API calls, or server-side user writes. Cross-device synchronization remains a separate opt-in authentication feature requiring explicit user review.


## Shared collector recovery / current deployment troubleshooting

The dedicated Cloudflare Worker `signaldesk-news-feed` and KV namespace were
created successfully, but GitHub deployment workflow health checks initially
received HTTP 403. A later read-only diagnostic verified `/health` returns
HTTP 200 and found no matching Cloudflare Access application. This makes the
earlier 403 appear transient; it should not be treated as evidence that the
Worker was never uploaded. The `/feed` endpoint may still return HTTP 503
until the first scheduled collection saves at least five eligible articles.

The public Pages builder checks a verified Worker health endpoint and exposes
its URL through an exact-origin Content Security Policy when reachable. Browsers
continue using the daily static news snapshot and manual-copy workflow whenever
the scheduled cache has not been populated or is stale. The public site never
requests upstream RSS per user, invokes paid AI, or posts to X.

Diagnostics: `.github/workflows/diagnose-news-collector.yml` is read-only and
reports HTTP status and sanitized public feed metadata, never secret headers or
article bodies. The configured Cron schedule is `*/15 * * * *` in UTC, but
Cloudflare propagation may delay first collection. If the cache stays empty,
inspect Worker Cron and KV bindings rather than changing account-wide Access.


## Phase 2B — Source-specific RSS context (without paid AI)

The **Why it matters** panel now shows a short (up to 170 characters) sanitized excerpt of the public RSS feed's description **when provided**. It is labelled **"From the RSS preview (unverified)"**. A syndicated RSS description is not proof of publisher authorship, not the full article, and not an AI-generated or independently verified summary.

The research guide highlights relevant forecast language and numbers to verify against the original source. The **Use my notes as draft** action converts only the visitor's own research notes into an editable X-style post with an original source link. It does not call a model, post to X, or save notes on a server. The site refuses to display invalid/malformed context fields or unexpected private evidence and credential markers.

Missing, promotional, duplicate or malformed descriptions produce a clear headline-only fallback. The dashboard remains functional even when RSS context is unavailable.

**Next genuine AI milestone:** choose a provider, budget and evidence policy. Only then can an authenticated server-side model gateway be added with a strict daily cost cap, input/output bounds, validated article evidence, and independent safeguards. No model calls or spending are enabled by this phase.

## Phase 2 — Post Studio and Why It Matters (no-cost foundation)

The site now includes two additional tools within each story card:

- **Post Studio:** Four editorial writing starters (News brief, Professional, Analytical and Discussion) generated deterministically from the **attributed headline and source URL**, not from an AI provider. Select **Use this draft** to load it into the existing local editor. The browser asks before overwriting an existing local edit. Copying remains manual and never sends to X.
- **Why it matters:** A clearly labeled research guide showing the original publisher headline, safe original HTTPS link, category-specific verification questions, and notes you can save in **localStorage** on that browser/device. This is **not** an AI summary and does **not** analyze full-text article bodies.

No AI credits or inference calls are consumed by these features. No existing article evidence or private GitHub data is added to the public JSON. Notes are **not synchronized**, so avoid using a shared browser for sensitive research.

### Enabling a real AI-assisted Post Studio later

Do **not** add a paid model key to public static JavaScript or to the public JSON. A separate server-side, authenticated and rate-limited inference gateway is required. Before activation, the gateway must have default-deny behavior, a provider/model allowlist, bounded output/input tokens, per-user and global rate limits, a hard daily budget plus concurrent-request guard, abuse monitoring, and explicit deployment approval for the desired provider and estimated costs. Summaries must cite independently retrieved article evidence or clearly say the article is unavailable. Never describe headline-only output as fact checked, source-verified, or AI-generated.



SignalDesk is a public, read-only collection of news suggestions and AI-written post drafts. Visitors can read source links and copy post text, then manually post on X if they wish. **This site never posts to X, uses X tokens, or verifies the article's claims.**

## Current project

- GitHub: `varadachiru/x-news-automation` (private repo)
- Cloudflare Pages: `signaldesk-news`
- Production Pages hostname: https://signaldesk-news.pages.dev
- Optional custom domain: `news.littlekingchess.com` (must be explicitly attached to Pages)

## What is public

Only schema-versioned fields in `dist/signaldesk/data.json`: headline, original publisher HTTPS URL, category, publisher, short editorial-safe description, suggestion/draft text, review status, timestamp and opaque item ID. Private GitHub Issue content, analyses, publisher evidence snippets, Issue links, access tokens and credentials are not exported.

The Python exporter validates the allowlisted JSON structure and fails closed when private markers or token-looking strings are found. The client uses `textContent`, never dynamic HTML. **Do not add private notes or passwords to an X draft**, because the prepared post text is intentionally public.

## More stories and refresh behavior

The public dashboard export now selects **up to 30 news suggestions** per build (previously nine), retaining topic relevance, source diversity, forecast warnings, and duplicate removal. The original GitHub editorial quota of **nine** is unchanged, as are the Copilot workflow and X publishing controls. The display opens with 12 stories and offers **Show more** in groups of 12.

The static website checks its already-published \`data.json\` snapshot **every 15 minutes while the tab is visible**. The displayed **Last refreshed** time always comes from the server-generated snapshot and includes the local date and time. Checking does **not** trigger an RSS collection job for each visitor or a new Cloudflare deployment.

**Important:** Server-side RSS collection and Cloudflare publishing currently run **daily** (07:12 UTC), plus manual deployments and relevant merges. A site notice makes this distinction clear. For genuine shared 15-minute news collection, we must first decouple RSS ingestion from GitHub Actions/Cloudflare Pages deployments using a scheduled shared cache (e.g. Cloudflare Worker + KV/D1). Avoid scheduling the entire private GitHub Actions build/deploy every 15 minutes: it would mean roughly 2,880 runs per 30-day month, potentially exceeding private GitHub Actions minutes and Cloudflare Pages build/deployment quotas. Cloudflare/GitHub costs must be separately reviewed before activation.

## Daily refresh

The workflow `Build and publish public SignalDesk news dashboard (no X posting)` runs on:
- merges affecting the dashboard or exporter;
- the GitHub scheduled trigger at 07:12 UTC (may be delayed by GitHub);
- a manual `Run workflow` request.

It collects fresh RSS suggestions, reads existing GitHub AI drafts with the GitHub Actions token, exports only approved-to-display fields, validates the public package, and deploys `dist/signaldesk` via the existing Cloudflare Pages token. If a validation or deployment step fails, the previous live version remains in place.

AI-written Copilot drafts are **not** regenerated by this workflow. The existing Copilot draft generator runs only with separate credit approval, while RSS-based suggestions refresh daily at no Copilot usage.

The GitHub Actions token is never embedded in the site. Cloudflare secrets are injected only into the deployment step, not page assets. X publishing remains disabled.

## Add your custom subdomain

1. Open Cloudflare > Workers & Pages > `signaldesk-news` > **Custom domains**.
2. Click **Set up a domain** and enter `news.littlekingchess.com`.
3. Confirm the domain association and follow Cloudflare's DNS CNAME instructions. If the domain is in the same Cloudflare account, Cloudflare often creates the DNS record automatically.
4. Wait for domain and certificate to become active, then verify `https://news.littlekingchess.com`.

Do not add only a DNS CNAME without also associating it with the Pages project.

Official documentation: https://developers.cloudflare.com/pages/configuration/custom-domains/

## Checks

The public build is verified offline in `tests/test_dashboard_export.py`. From GitHub Actions, open the latest **Build and publish public SignalDesk news dashboard** run and check its summary for success. You can also visit `https://signaldesk-news.pages.dev/data.json` to see the *public-only* feed. No tokens or private evidence belong there.

To inspect sources before sharing, always open the original publisher link. News suggestions and AI drafts are not fact-checked or automatically published.

## Shared collector recovery / current deployment troubleshooting

The dedicated Cloudflare Worker `signaldesk-news-feed` and KV namespace were
created successfully, but GitHub deployment workflow health checks initially
received HTTP 403. A later read-only diagnostic verified `/health` returns
HTTP 200 and found no matching Cloudflare Access application. This makes the
earlier 403 appear transient; it should not be treated as evidence that the
Worker was never uploaded. The `/feed` endpoint may still return HTTP 503
until the first scheduled collection saves at least five eligible articles.

The public Pages builder checks a verified Worker health endpoint and exposes
its URL through an exact-origin Content Security Policy when reachable. Browsers
continue using the daily static news snapshot and manual-copy workflow whenever
the scheduled cache has not been populated or is stale. The public site never
requests upstream RSS per user, invokes paid AI, or posts to X.

Diagnostics: `.github/workflows/diagnose-news-collector.yml` is read-only and
reports HTTP status and sanitized public feed metadata, never secret headers or
article bodies. The configured Cron schedule is `*/15 * * * *` in UTC, but
Cloudflare propagation may delay first collection. If the cache stays empty,
inspect Worker Cron and KV bindings rather than changing account-wide Access.


## Phase 2B — Source-specific RSS context (without paid AI)

The **Why it matters** panel now shows a short (up to 170 characters) sanitized excerpt of the public RSS feed's description **when provided**. It is labelled **"From the RSS preview (unverified)"**. A syndicated RSS description is not proof of publisher authorship, not the full article, and not an AI-generated or independently verified summary.

The research guide highlights relevant forecast language and numbers to verify against the original source. The **Use my notes as draft** action converts only the visitor's own research notes into an editable X-style post with an original source link. It does not call a model, post to X, or save notes on a server. The site refuses to display invalid/malformed context fields or unexpected private evidence and credential markers.

Missing, promotional, duplicate or malformed descriptions produce a clear headline-only fallback. The dashboard remains functional even when RSS context is unavailable.

**Next genuine AI milestone:** choose a provider, budget and evidence policy. Only then can an authenticated server-side model gateway be added with a strict daily cost cap, input/output bounds, validated article evidence, and independent safeguards. No model calls or spending are enabled by this phase.

## Phase 2 — Post Studio and Why It Matters (no-cost foundation)

The site now includes two additional tools within each story card:

- **Post Studio:** Four editorial writing starters (News brief, Professional, Analytical and Discussion) generated deterministically from the **attributed headline and source URL**, not from an AI provider. Select **Use this draft** to load it into the existing local editor. The browser asks before overwriting an existing local edit. Copying remains manual and never sends to X.
- **Why it matters:** A clearly labeled research guide showing the original publisher headline, safe original HTTPS link, category-specific verification questions, and notes you can save in **localStorage** on that browser/device. This is **not** an AI summary and does **not** analyze full-text article bodies.

No AI credits or inference calls are consumed by these features. No existing article evidence or private GitHub data is added to the public JSON. Notes are **not synchronized**, so avoid using a shared browser for sensitive research.

### Enabling a real AI-assisted Post Studio later

Do **not** add a paid model key to public static JavaScript or to the public JSON. A separate server-side, authenticated and rate-limited inference gateway is required. Before activation, the gateway must have default-deny behavior, a provider/model allowlist, bounded output/input tokens, per-user and global rate limits, a hard daily budget plus concurrent-request guard, abuse monitoring, and explicit deployment approval for the desired provider and estimated costs. Summaries must cite independently retrieved article evidence or clearly say the article is unavailable. Never describe headline-only output as fact checked, source-verified, or AI-generated.



SignalDesk is a public, read-only collection of news suggestions and AI-written post drafts. Visitors can read source links and copy post text, then manually post on X if they wish. **This site never posts to X, uses X tokens, or verifies the article's claims.**

## Current project

- GitHub: `varadachiru/x-news-automation` (private repo)
- Cloudflare Pages: `signaldesk-news`
- Production Pages hostname: https://signaldesk-news.pages.dev
- Optional custom domain: `news.littlekingchess.com` (must be explicitly attached to Pages)

## What is public

Only schema-versioned fields in `dist/signaldesk/data.json`: headline, original publisher HTTPS URL, category, publisher, short editorial-safe description, suggestion/draft text, review status, timestamp and opaque item ID. Private GitHub Issue content, analyses, publisher evidence snippets, Issue links, access tokens and credentials are not exported.

The Python exporter validates the allowlisted JSON structure and fails closed when private markers or token-looking strings are found. The client uses `textContent`, never dynamic HTML. **Do not add private notes or passwords to an X draft**, because the prepared post text is intentionally public.

## More stories and refresh behavior

The public dashboard export now selects **up to 30 news suggestions** per build (previously nine), retaining topic relevance, source diversity, forecast warnings, and duplicate removal. The original GitHub editorial quota of **nine** is unchanged, as are the Copilot workflow and X publishing controls. The display opens with 12 stories and offers **Show more** in groups of 12.

The static website checks its already-published \`data.json\` snapshot **every 15 minutes while the tab is visible**. The displayed **Last refreshed** time always comes from the server-generated snapshot and includes the local date and time. Checking does **not** trigger an RSS collection job for each visitor or a new Cloudflare deployment.

**Important:** Server-side RSS collection and Cloudflare publishing currently run **daily** (07:12 UTC), plus manual deployments and relevant merges. A site notice makes this distinction clear. For genuine shared 15-minute news collection, we must first decouple RSS ingestion from GitHub Actions/Cloudflare Pages deployments using a scheduled shared cache (e.g. Cloudflare Worker + KV/D1). Avoid scheduling the entire private GitHub Actions build/deploy every 15 minutes: it would mean roughly 2,880 runs per 30-day month, potentially exceeding private GitHub Actions minutes and Cloudflare Pages build/deployment quotas. Cloudflare/GitHub costs must be separately reviewed before activation.

## Daily refresh

The workflow `Build and publish public SignalDesk news dashboard (no X posting)` runs on:
- merges affecting the dashboard or exporter;
- the GitHub scheduled trigger at 07:12 UTC (may be delayed by GitHub);
- a manual `Run workflow` request.

It collects fresh RSS suggestions, reads existing GitHub AI drafts with the GitHub Actions token, exports only approved-to-display fields, validates the public package, and deploys `dist/signaldesk` via the existing Cloudflare Pages token. If a validation or deployment step fails, the previous live version remains in place.

AI-written Copilot drafts are **not** regenerated by this workflow. The existing Copilot draft generator runs only with separate credit approval, while RSS-based suggestions refresh daily at no Copilot usage.

The GitHub Actions token is never embedded in the site. Cloudflare secrets are injected only into the deployment step, not page assets. X publishing remains disabled.

## Add your custom subdomain

1. Open Cloudflare > Workers & Pages > `signaldesk-news` > **Custom domains**.
2. Click **Set up a domain** and enter `news.littlekingchess.com`.
3. Confirm the domain association and follow Cloudflare's DNS CNAME instructions. If the domain is in the same Cloudflare account, Cloudflare often creates the DNS record automatically.
4. Wait for domain and certificate to become active, then verify `https://news.littlekingchess.com`.

Do not add only a DNS CNAME without also associating it with the Pages project.

Official documentation: https://developers.cloudflare.com/pages/configuration/custom-domains/

## Checks

The public build is verified offline in `tests/test_dashboard_export.py`. From GitHub Actions, open the latest **Build and publish public SignalDesk news dashboard** run and check its summary for success. You can also visit `https://signaldesk-news.pages.dev/data.json` to see the *public-only* feed. No tokens or private evidence belong there.

To inspect sources before sharing, always open the original publisher link. News suggestions and AI drafts are not fact-checked or automatically published.

## India News and Copied Articles

**India News:** Separate sidebar view for India-relevant startup, AI, technology, and markets coverage. The shared 15-minute collector reads four additional public Indian publisher RSS feeds, marking stories only when a feed specifically focuses on India's startups or a headline contains clear Indian context (e.g. India, Bengaluru, RBI, Nifty). The dynamic feed now includes up to 15 separately selected India articles, retaining the original up-to-30 global news selection, source diversity caps, and an unchanged public fallback. General Indian-hosted publisher articles about global technology are *not automatically* labelled India news. Publisher RSS content is unverified.

**Copied Articles:** After a successful clipboard write, an article moves out of All Stories, Trending, India News and Saved into a dedicated Copied Articles section. The Undo banner reverses the move to its prior workflow status. The section keeps up to 100 safely bounded story snapshots and personal statuses **in the same browser only**, allowing copied items to remain accessible after news feed refreshes. This does not indicate any post actually appeared on X.

Visitors do not need accounts. Neither feature triggers AI inference, X API calls, or server-side user writes. Cross-device synchronization remains a separate opt-in authentication feature requiring explicit user review.


## Shared collector recovery / current deployment troubleshooting

The dedicated Cloudflare Worker `signaldesk-news-feed` and KV namespace were
created successfully, but GitHub deployment workflow health checks initially
received HTTP 403. A later read-only diagnostic verified `/health` returns
HTTP 200 and found no matching Cloudflare Access application. This makes the
earlier 403 appear transient; it should not be treated as evidence that the
Worker was never uploaded. The `/feed` endpoint may still return HTTP 503
until the first scheduled collection saves at least five eligible articles.

The public Pages builder checks a verified Worker health endpoint and exposes
its URL through an exact-origin Content Security Policy when reachable. Browsers
continue using the daily static news snapshot and manual-copy workflow whenever
the scheduled cache has not been populated or is stale. The public site never
requests upstream RSS per user, invokes paid AI, or posts to X.

Diagnostics: `.github/workflows/diagnose-news-collector.yml` is read-only and
reports HTTP status and sanitized public feed metadata, never secret headers or
article bodies. The configured Cron schedule is `*/15 * * * *` in UTC, but
Cloudflare propagation may delay first collection. If the cache stays empty,
inspect Worker Cron and KV bindings rather than changing account-wide Access.


## Phase 2B — Source-specific RSS context (without paid AI)

The **Why it matters** panel now shows a short (up to 170 characters) sanitized excerpt of the public RSS feed's description **when provided**. It is labelled **"From the RSS preview (unverified)"**. A syndicated RSS description is not proof of publisher authorship, not the full article, and not an AI-generated or independently verified summary.

The research guide highlights relevant forecast language and numbers to verify against the original source. The **Use my notes as draft** action converts only the visitor's own research notes into an editable X-style post with an original source link. It does not call a model, post to X, or save notes on a server. The site refuses to display invalid/malformed context fields or unexpected private evidence and credential markers.

Missing, promotional, duplicate or malformed descriptions produce a clear headline-only fallback. The dashboard remains functional even when RSS context is unavailable.

**Next genuine AI milestone:** choose a provider, budget and evidence policy. Only then can an authenticated server-side model gateway be added with a strict daily cost cap, input/output bounds, validated article evidence, and independent safeguards. No model calls or spending are enabled by this phase.

## Phase 2 — Post Studio and Why It Matters (no-cost foundation)

The site now includes two additional tools within each story card:

- **Post Studio:** Four editorial writing starters (News brief, Professional, Analytical and Discussion) generated deterministically from the **attributed headline and source URL**, not from an AI provider. Select **Use this draft** to load it into the existing local editor. The browser asks before overwriting an existing local edit. Copying remains manual and never sends to X.
- **Why it matters:** A clearly labeled research guide showing the original publisher headline, safe original HTTPS link, category-specific verification questions, and notes you can save in **localStorage** on that browser/device. This is **not** an AI summary and does **not** analyze full-text article bodies.

No AI credits or inference calls are consumed by these features. No existing article evidence or private GitHub data is added to the public JSON. Notes are **not synchronized**, so avoid using a shared browser for sensitive research.

### Enabling a real AI-assisted Post Studio later

Do **not** add a paid model key to public static JavaScript or to the public JSON. A separate server-side, authenticated and rate-limited inference gateway is required. Before activation, the gateway must have default-deny behavior, a provider/model allowlist, bounded output/input tokens, per-user and global rate limits, a hard daily budget plus concurrent-request guard, abuse monitoring, and explicit deployment approval for the desired provider and estimated costs. Summaries must cite independently retrieved article evidence or clearly say the article is unavailable. Never describe headline-only output as fact checked, source-verified, or AI-generated.



SignalDesk is a public, read-only collection of news suggestions and AI-written post drafts. Visitors can read source links and copy post text, then manually post on X if they wish. **This site never posts to X, uses X tokens, or verifies the article's claims.**

## Current project

- GitHub: `varadachiru/x-news-automation` (private repo)
- Cloudflare Pages: `signaldesk-news`
- Production Pages hostname: https://signaldesk-news.pages.dev
- Optional custom domain: `news.littlekingchess.com` (must be explicitly attached to Pages)

## What is public

Only schema-versioned fields in `dist/signaldesk/data.json`: headline, original publisher HTTPS URL, category, publisher, short editorial-safe description, suggestion/draft text, review status, timestamp and opaque item ID. Private GitHub Issue content, analyses, publisher evidence snippets, Issue links, access tokens and credentials are not exported.

The Python exporter validates the allowlisted JSON structure and fails closed when private markers or token-looking strings are found. The client uses `textContent`, never dynamic HTML. **Do not add private notes or passwords to an X draft**, because the prepared post text is intentionally public.

## More stories and refresh behavior

The public dashboard export now selects **up to 30 news suggestions** per build (previously nine), retaining topic relevance, source diversity, forecast warnings, and duplicate removal. The original GitHub editorial quota of **nine** is unchanged, as are the Copilot workflow and X publishing controls. The display opens with 12 stories and offers **Show more** in groups of 12.

The static website checks its already-published \`data.json\` snapshot **every 15 minutes while the tab is visible**. The displayed **Last refreshed** time always comes from the server-generated snapshot and includes the local date and time. Checking does **not** trigger an RSS collection job for each visitor or a new Cloudflare deployment.

**Important:** Server-side RSS collection and Cloudflare publishing currently run **daily** (07:12 UTC), plus manual deployments and relevant merges. A site notice makes this distinction clear. For genuine shared 15-minute news collection, we must first decouple RSS ingestion from GitHub Actions/Cloudflare Pages deployments using a scheduled shared cache (e.g. Cloudflare Worker + KV/D1). Avoid scheduling the entire private GitHub Actions build/deploy every 15 minutes: it would mean roughly 2,880 runs per 30-day month, potentially exceeding private GitHub Actions minutes and Cloudflare Pages build/deployment quotas. Cloudflare/GitHub costs must be separately reviewed before activation.

## Daily refresh

The workflow `Build and publish public SignalDesk news dashboard (no X posting)` runs on:
- merges affecting the dashboard or exporter;
- the GitHub scheduled trigger at 07:12 UTC (may be delayed by GitHub);
- a manual `Run workflow` request.

It collects fresh RSS suggestions, reads existing GitHub AI drafts with the GitHub Actions token, exports only approved-to-display fields, validates the public package, and deploys `dist/signaldesk` via the existing Cloudflare Pages token. If a validation or deployment step fails, the previous live version remains in place.

AI-written Copilot drafts are **not** regenerated by this workflow. The existing Copilot draft generator runs only with separate credit approval, while RSS-based suggestions refresh daily at no Copilot usage.

The GitHub Actions token is never embedded in the site. Cloudflare secrets are injected only into the deployment step, not page assets. X publishing remains disabled.

## Add your custom subdomain

1. Open Cloudflare > Workers & Pages > `signaldesk-news` > **Custom domains**.
2. Click **Set up a domain** and enter `news.littlekingchess.com`.
3. Confirm the domain association and follow Cloudflare's DNS CNAME instructions. If the domain is in the same Cloudflare account, Cloudflare often creates the DNS record automatically.
4. Wait for domain and certificate to become active, then verify `https://news.littlekingchess.com`.

Do not add only a DNS CNAME without also associating it with the Pages project.

Official documentation: https://developers.cloudflare.com/pages/configuration/custom-domains/

## Checks

The public build is verified offline in `tests/test_dashboard_export.py`. From GitHub Actions, open the latest **Build and publish public SignalDesk news dashboard** run and check its summary for success. You can also visit `https://signaldesk-news.pages.dev/data.json` to see the *public-only* feed. No tokens or private evidence belong there.

To inspect sources before sharing, always open the original publisher link. News suggestions and AI drafts are not fact-checked or automatically published.

## Shared collector recovery / current deployment troubleshooting

The dedicated Cloudflare Worker `signaldesk-news-feed` and KV namespace were
created successfully, but GitHub deployment workflow health checks initially
received HTTP 403. A later read-only diagnostic verified `/health` returns
HTTP 200 and found no matching Cloudflare Access application. This makes the
earlier 403 appear transient; it should not be treated as evidence that the
Worker was never uploaded. The `/feed` endpoint may still return HTTP 503
until the first scheduled collection saves at least five eligible articles.

The public Pages builder checks a verified Worker health endpoint and exposes
its URL through an exact-origin Content Security Policy when reachable. Browsers
continue using the daily static news snapshot and manual-copy workflow whenever
the scheduled cache has not been populated or is stale. The public site never
requests upstream RSS per user, invokes paid AI, or posts to X.

Diagnostics: `.github/workflows/diagnose-news-collector.yml` is read-only and
reports HTTP status and sanitized public feed metadata, never secret headers or
article bodies. The configured Cron schedule is `*/15 * * * *` in UTC, but
Cloudflare propagation may delay first collection. If the cache stays empty,
inspect Worker Cron and KV bindings rather than changing account-wide Access.


## Phase 2B — Source-specific RSS context (without paid AI)

The **Why it matters** panel now shows a short (up to 170 characters) sanitized excerpt of the public RSS feed's description **when provided**. It is labelled **"From the RSS preview (unverified)"**. A syndicated RSS description is not proof of publisher authorship, not the full article, and not an AI-generated or independently verified summary.

The research guide highlights relevant forecast language and numbers to verify against the original source. The **Use my notes as draft** action converts only the visitor's own research notes into an editable X-style post with an original source link. It does not call a model, post to X, or save notes on a server. The site refuses to display invalid/malformed context fields or unexpected private evidence and credential markers.

Missing, promotional, duplicate or malformed descriptions produce a clear headline-only fallback. The dashboard remains functional even when RSS context is unavailable.

**Next genuine AI milestone:** choose a provider, budget and evidence policy. Only then can an authenticated server-side model gateway be added with a strict daily cost cap, input/output bounds, validated article evidence, and independent safeguards. No model calls or spending are enabled by this phase.

## Phase 2 — Post Studio and Why It Matters (no-cost foundation)

The site now includes two additional tools within each story card:

- **Post Studio:** Four editorial writing starters (News brief, Professional, Analytical and Discussion) generated deterministically from the **attributed headline and source URL**, not from an AI provider. Select **Use this draft** to load it into the existing local editor. The browser asks before overwriting an existing local edit. Copying remains manual and never sends to X.
- **Why it matters:** A clearly labeled research guide showing the original publisher headline, safe original HTTPS link, category-specific verification questions, and notes you can save in **localStorage** on that browser/device. This is **not** an AI summary and does **not** analyze full-text article bodies.

No AI credits or inference calls are consumed by these features. No existing article evidence or private GitHub data is added to the public JSON. Notes are **not synchronized**, so avoid using a shared browser for sensitive research.

### Enabling a real AI-assisted Post Studio later

Do **not** add a paid model key to public static JavaScript or to the public JSON. A separate server-side, authenticated and rate-limited inference gateway is required. Before activation, the gateway must have default-deny behavior, a provider/model allowlist, bounded output/input tokens, per-user and global rate limits, a hard daily budget plus concurrent-request guard, abuse monitoring, and explicit deployment approval for the desired provider and estimated costs. Summaries must cite independently retrieved article evidence or clearly say the article is unavailable. Never describe headline-only output as fact checked, source-verified, or AI-generated.



SignalDesk is a public, read-only collection of news suggestions and AI-written post drafts. Visitors can read source links and copy post text, then manually post on X if they wish. **This site never posts to X, uses X tokens, or verifies the article's claims.**

## Current project

- GitHub: `varadachiru/x-news-automation` (private repo)
- Cloudflare Pages: `signaldesk-news`
- Production Pages hostname: https://signaldesk-news.pages.dev
- Optional custom domain: `news.littlekingchess.com` (must be explicitly attached to Pages)

## What is public

Only schema-versioned fields in `dist/signaldesk/data.json`: headline, original publisher HTTPS URL, category, publisher, short editorial-safe description, suggestion/draft text, review status, timestamp and opaque item ID. Private GitHub Issue content, analyses, publisher evidence snippets, Issue links, access tokens and credentials are not exported.

The Python exporter validates the allowlisted JSON structure and fails closed when private markers or token-looking strings are found. The client uses `textContent`, never dynamic HTML. **Do not add private notes or passwords to an X draft**, because the prepared post text is intentionally public.

## More stories and refresh behavior

The public dashboard export now selects **up to 30 news suggestions** per build (previously nine), retaining topic relevance, source diversity, forecast warnings, and duplicate removal. The original GitHub editorial quota of **nine** is unchanged, as are the Copilot workflow and X publishing controls. The display opens with 12 stories and offers **Show more** in groups of 12.

The static website checks its already-published \`data.json\` snapshot **every 15 minutes while the tab is visible**. The displayed **Last refreshed** time always comes from the server-generated snapshot and includes the local date and time. Checking does **not** trigger an RSS collection job for each visitor or a new Cloudflare deployment.

**Important:** Server-side RSS collection and Cloudflare publishing currently run **daily** (07:12 UTC), plus manual deployments and relevant merges. A site notice makes this distinction clear. For genuine shared 15-minute news collection, we must first decouple RSS ingestion from GitHub Actions/Cloudflare Pages deployments using a scheduled shared cache (e.g. Cloudflare Worker + KV/D1). Avoid scheduling the entire private GitHub Actions build/deploy every 15 minutes: it would mean roughly 2,880 runs per 30-day month, potentially exceeding private GitHub Actions minutes and Cloudflare Pages build/deployment quotas. Cloudflare/GitHub costs must be separately reviewed before activation.

## Daily refresh

The workflow `Build and publish public SignalDesk news dashboard (no X posting)` runs on:
- merges affecting the dashboard or exporter;
- the GitHub scheduled trigger at 07:12 UTC (may be delayed by GitHub);
- a manual `Run workflow` request.

It collects fresh RSS suggestions, reads existing GitHub AI drafts with the GitHub Actions token, exports only approved-to-display fields, validates the public package, and deploys `dist/signaldesk` via the existing Cloudflare Pages token. If a validation or deployment step fails, the previous live version remains in place.

AI-written Copilot drafts are **not** regenerated by this workflow. The existing Copilot draft generator runs only with separate credit approval, while RSS-based suggestions refresh daily at no Copilot usage.

The GitHub Actions token is never embedded in the site. Cloudflare secrets are injected only into the deployment step, not page assets. X publishing remains disabled.

## Add your custom subdomain

1. Open Cloudflare > Workers & Pages > `signaldesk-news` > **Custom domains**.
2. Click **Set up a domain** and enter `news.littlekingchess.com`.
3. Confirm the domain association and follow Cloudflare's DNS CNAME instructions. If the domain is in the same Cloudflare account, Cloudflare often creates the DNS record automatically.
4. Wait for domain and certificate to become active, then verify `https://news.littlekingchess.com`.

Do not add only a DNS CNAME without also associating it with the Pages project.

Official documentation: https://developers.cloudflare.com/pages/configuration/custom-domains/

## Checks

The public build is verified offline in `tests/test_dashboard_export.py`. From GitHub Actions, open the latest **Build and publish public SignalDesk news dashboard** run and check its summary for success. You can also visit `https://signaldesk-news.pages.dev/data.json` to see the *public-only* feed. No tokens or private evidence belong there.

To inspect sources before sharing, always open the original publisher link. News suggestions and AI drafts are not fact-checked or automatically published.
