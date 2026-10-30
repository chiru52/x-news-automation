# SignalDesk — public Cloudflare news dashboard

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
