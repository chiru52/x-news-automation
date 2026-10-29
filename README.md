# X News Automation — Stage 1 (safe, draft-only)

A private Python/GitHub Actions project that collects RSS news, removes repeats and creates at most **nine human-review templates per Europe/Stockholm day**.

**Nothing in this version can publish to X or Buffer.** It does not call Grok, OpenAI or any other AI API. Drafts include a visible placeholder: `[Write one verified insight after reading the article.]`.

## Features

- Reads RSS 2.0 and Atom feeds and extracts titles, original links, timestamps and short descriptions.
- Excludes undated, stale, future-dated and invalid-link stories. Removes known URL tracking parameters.
- Removes duplicates by canonicalized URL and normalized headline, including across runs when state is restored.
- Caps review templates at 9 per Stockholm calendar day.
- Produces both `output/review_queue.md` and `output/review_queue.json`, including feed errors.
- Runs automatically via GitHub Actions daily at 06:17 UTC or on demand.
- Runs network-free unit tests on pull requests and pushes.

## How to use

After the setup pull request is merged, visit your repository's **Actions** tab. Select **Collect news (review drafts only)**, click **Run workflow**, choose `main`, and run it. Open the completed run's **Artifacts** section and download the `review-queue-...` artifact. Open `review_queue.md`.

GitHub Actions schedules are best-effort and may run late. The published feed titles are not fact-checked or AI-written: open the original links, verify the details, then write the insight yourself before posting.

## Local usage

Requires Python 3.11+; no additional packages:

```bash
python -m unittest discover -s tests -v
python -m newsbot --demo --state .state/demo.json --output output/demo
python -m newsbot --state .state/seen.json --output output/live
```

`--demo` generates clearly labeled synthetic sample news, without network access.

## Configuration

- `config/sources.json` — list of RSS feed URLs and categories.
- `config/settings.json` — timezone, max drafts, lookback, request timeout.
- `publishing_enabled` must remain `false`, and `ai_provider` must remain `none`.
- Do not put secret API keys in source. Use GitHub Actions secrets later if integrations are approved.

## Limits and safeguards

The state history is cached between GitHub Actions runs, but caches may expire or be evicted. This is suitable for a **non-publishing** review queue only. Before automated posting, add a durable database/ledger, source verification, manual approval controls, strict rate limits, idempotency, and integration tests. Semantic duplicate detection is not yet implemented. Some publishers may block automated RSS requests. Respect their content and licensing terms.

No third-party article text is bundled with the project.

## Three-category news mix (Stage 1B)

The collector now watches three areas: **Technology/AI**, **financial markets/business**, and **SaaS tools, launches and funding**. Edit `config/sources.json` to add or remove permitted RSS/Atom feeds. The `category_order` array in `config/settings.json` controls the categories to balance.

The current default is nine drafts per day, with **3 technology, 3 markets and 3 SaaS** when each has enough eligible stories. For other daily limits, the balancing algorithm splits picks as fairly as it can. It maintains each category's count between runs and falls back to available categories when a feed runs dry. Daily limits, review-only output, and duplicate suppression remain in force.

**Financial headlines are not investment advice.** Prices, earnings and market-sensitive claims must be verified from reliable primary sources before posting. Product Hunt's productivity category may include non-SaaS products; approve relevance before publication. We haven't integrated AI or X publishing. A successful job cannot confirm the underlying reporting is correct.

The first day's existing five drafts consume its draft quota. The new mix begins at the next Stockholm calendar-day quota, unless prior history has expired. A workflow run after merging will validate live source availability; individual feeds can sometimes fail.

## Expanded feeds and daily target (Stage 1C)

The default is now **up to nine editorial review templates per Stockholm day**, not nine guaranteed X posts. Three eligible stories per category is the target; if a category has no fresh items, other categories can fill the available slots. No generated draft is published automatically.

Additional configured RSS candidate sources:
- **Yahoo Finance** stock headline feeds for NVDA, MSFT, GOOGL, AMZN and the S&P 500/Nasdaq indices. These are **company/market-specific news feeds**, not a reliable general Yahoo Finance RSS endpoint.
- **TechCrunch** for startup and app reporting.
- **SaaStr** for SaaS business news and analysis.
- **Hacker News** for noteworthy technology discussions and links.

These feeds are independently fetched and may return a network error or unsupported response. Feeds have **not been live-tested for this change**; check each run's `feed_errors` in `review_queue.json`. The project's source categories are approximate: a TechCrunch or Product Hunt item may not be about SaaS. Human review is mandatory before we later add any actual posting.

### Buffer Free: clarification

Buffer Free supports up to **10 scheduled posts in the X queue at the same time**, not just 10 per day/month. Queue slots reopen once posts publish. Buffer Free API limits also apply (currently 1,000 requests/30 days for one connected channel, plus rolling shorter windows). The present repository has **no Buffer integration** and therefore consumes zero Buffer API requests. Nine drafts a day is an editorial starting point, not a platform maximum.

If you ran earlier versions today, existing local-day history counts towards nine; the new collector may only produce the unused balance, not nine additional drafts. We prioritize verified, original, useful posts, and stop before publishing anything automatically. X disallows duplicate/spam and certain kinds of automated trend posting. Respect publishers' feed and redistribution terms and cite/link original articles.

## Source diagnostics and editorial classification checks (Stage 1D)

The review artifact now records each feed's **parsed article count, recent article count, and status** in `review_queue.json` and `review_queue.md`. A feed that returns zero fresh items is highlighted separately from a network error; a successful fetch does not mean its topic labels are accurate.

The TechCrunch source used for SaaS/startup coverage is narrowed from the general TechCrunch news RSS to the TechCrunch **Startups** RSS. That feed can still include venture funding or hardware-startup articles; every item's category remains a **source-assigned, unverified label**, and every draft is **not publishable** without editorial review.

Do not conclude from a successful workflow that all fourteen feeds provide recent relevant stories; review the diagnostics and click through to original sources. No source articles are reproduced in full. The AI and publishing integrations remain disabled.

## Explainable headline relevance (Stage 1E)

Before consuming the daily nine-draft budget, **live CLI runs now enable a conservative, offline, keyword-based relevance filter and ranking**. No AI model or billing is involved. Each RSS article must have a category-specific term in its *headline* to qualify; summary matches cannot qualify on their own. Higher-scoring stories are chosen ahead of generic or less impactful ones within each category, and the three-category balancing remains active.

The metadata in `review_queue.json` now includes `relevance.score`, `headline_terms`, `summary_terms`, and `impact_terms`. The Markdown queue shows headline terms and score. Scores are editorial heuristics, not a correctness measure or fact check, and source categories are **not verified**. Headline keyword matching can miss genuinely important stories or include some irrelevant ones; those limitations are intentional until we have a reviewed AI classifier.

For example, a general hardware product rumor in a feed labeled SaaS and an unrelated property lawsuit in a technology feed will not qualify. Relevant earnings, market shifts, startup launches and AI/developer tool releases can qualify. If there aren't nine relevant articles, the system generates fewer. This is better than publishing low-quality filler.

This can be turned off locally for comparison by setting `relevance_filter_enabled` to `false` in `config/settings.json`. **Do not enable publishing:** `publishing_enabled=false` and `ai_provider=none` are still mandatory safety checks.

The 9-draft cap is per Stockholm calendar day; today's existing review history remains intact. GitHub Actions caches can expire and are not a durable posting ledger. Do not use this collector for unattended X publishing until source verification, durable idempotency and manual approval are implemented.

## Step 6: offline editorial review dashboard and quota-free preview

Every collector run now includes `review_dashboard.html` alongside the existing Markdown and JSON files in the GitHub Actions artifact. Download the ZIP, **extract it**, and open the HTML file in a browser. It is a standalone, responsive client-side page: there is **no server, login, third-party JavaScript, network submission, Buffer integration, or X posting**. The only network activity is when you click a publisher's article link.

You can search and filter candidates, open the original news sources, inspect matched terms and heuristic relevance scores, and mark each story **Shortlist**, **Skip**, or **Reset**. Shortlist means only that you want to consider the story for later writing—it is **not approval for publication**. Copy the unfinished template or export decisions to `editorial-decisions.json` for later use. Decisions are held in the browser session and **are lost on reload unless you exported them**. Exports explicitly set `publication_authorized=false`.

The **Run workflow** manual action now includes a `preview` checkbox, enabled by default. Preview collects current RSS data and creates up to nine **additional candidate templates**, but it does **not** change the persisted draft history or consume the day's quota. Previously seen articles remain excluded to reduce repetition. The scheduled collection remains quota-enforcing. There is still no AI text-generation API in this repository and no way to publish from the review page.

### Try it

1. Merge the PR, then open GitHub **Actions → Collect news (review drafts only)**.
2. Click **Run workflow**, select `main`, and leave **preview = true**.
3. Download the new `review-queue-...` artifact. Extract and open `review_dashboard.html`.
4. Review shortlisted stories and export your decisions. Never treat this as published content.

Local test (no API keys needed):

```sh
python -m unittest discover -s tests -v
python -m newsbot --demo --preview --state .state/demo.json --output output/demo-preview
```

The demo uses clearly synthetic articles. The HTML page renders RSS fields safely as text. The relevance score is a keyword heuristic, not verified reporting or a factual guarantee.

## Stage 7: editable post composer and copyable AI prompt (no API needed)

The offline `review_dashboard.html` now includes a **local-only post editor** for each candidate. You can change the RSS template manually, view an advisory **280 raw-character counter**, tick a self-reported **original source checked** checkbox, and copy your edited text. X uses different counting for links, so the counter is not an official validation of publishability.

Use **Copy AI writing prompt** to paste a clearly source-labeled prompt into the AI assistant of your choosing (Grok in the X interface, ChatGPT, etc.). This is a **manual clipboard workflow**: no keys or AI calls are made. The prompt asks the model to avoid inventing facts and seek the full source before unsupported claims. Paste and verify the AI's output before putting it into the editable post.

The **Export decisions JSON** file now includes editor revisions, verification checkbox state and raw character count for changed/shortlisted/skipped candidates, while explicitly setting `publication_authorized=false`, `publishable=false`, and `ai_generated=false` (the system does not know whether you manually pasted AI text). It never authorizes or causes automatic posting.

Like all previous dashboard state, edits and checkbox decisions are held **only in memory** in the current browser tab until exported, and will be lost on reload. Export is not a backup to a server. No X/Buffer integrations or account credentials exist in this version.

## Stage 8: GitHub-native news review (no downloads required)

The repository stays **private**. After each collection, the GitHub Actions **Summary** page shows the selected headlines, original article links, source category, relevance scores, and checklists. Open Actions > Collect news (review drafts only) > latest run > Summary. No ZIP download is required.

Each successful scheduled run with fresh candidates also creates one private GitHub Issue named **News editorial review — YYYY-MM-DD**. Manual runs create/reuse it when the new **Create or reuse private daily review Issue** checkbox is enabled (default true). Find it in the repository's **Issues** tab. Use Edit to rewrite the markdown draft sections, tick source-review boxes, or leave comments. GitHub Issues is an editable Markdown worksheet, not the same fully interactive interface as the optional offline HTML file.

The automation intentionally NEVER overwrites an existing Issue for the same Stockholm calendar day. This protects manual edits and comments. When a second run discovers different stories on the same day, they still appear in that run's GitHub Actions Summary, but the existing Issue is not replaced. A no-candidate run does not create a new Issue.

The workflow requires built-in GitHub Actions GITHUB_TOKEN with issues:write **only to create a private editorial Issue**. This is not an X API permission, and does not connect Buffer, Grok, or OpenAI. All articles remain publishable=false, and publication_authorized=false; even selecting all checkboxes or writing comments can NEVER send a post to X.

To test: merge this PR, open Actions > Collect news, select Run workflow on main, leave Preview and Create or reuse private daily review Issue checked, then open the completed run's Summary or the Issues tab.

GitHub Pages for private repositories typically requires GitHub Pro or another eligible plan, and a GitHub Pages site may be publicly accessible; we deliberately do not use Pages for the private editorial workflow.

## Stage 9: automatic source-attributed draft suggestions (no paid AI API)

Every eligible story gets a **concise suggested post** created deterministically from the RSS headline and a link back to the original source, with an explicit **Via [feed]** attribution. It uses no AI service or paid API and makes **no additional claims** from an RSS summary (e.g., it does not invent analysis of market moves or AI capabilities).

The new queue fields are `suggested_post` and `writing` (method, approximate X length, source-check flags, headline-shortening flag, and specific verification warnings). The original `draft` fill-in template remains available for compatibility. The GitHub Actions Summary, any **new** GitHub daily editorial Issue, and the offline HTML editor now prioritize the suggested post and flag items that contain financial figures, rumors, unverified funding claims, or shortened headlines.

**These are NOT independently fact-checked posts.** The source headline can itself be wrong, imprecise, or incomplete. Users must open the article, verify all claims and dates, check X's official length handling, and rewrite the final post before use. The calculated character count approximates X's 23-character URL weighting, not the platform's official unicode/link calculation. No post is marked publishable or editor approved.

Existing daily GitHub Issues are not overwritten, specifically to preserve manual edits. To preview these new suggestions on the same day, use the latest **GitHub Actions run Summary**. A new editable Issue is created on the next Stockholm day with eligible stories. The workflow does not call X, Buffer, Grok, or OpenAI.

## Stage 10: diversified news selection and correct link attribution

The first live run of automatic post suggestions succeeded, but the queue concentrated **all three SaaS picks on funding rounds**, **all three technology picks on The Verge**, and **three market picks on Yahoo Finance** (with some Yahoo RSS links leading to Stocktwits stories). The automated text is still a source-attributed **unverified headline**, not engaging original commentary.

To improve editorial variety without guessing at reporting:
- The daily review queue now selects **at most 2 drafts from the same RSS feed** when configured as `max_drafts_per_source_per_day=2`. If other relevant feeds are dry, it returns fewer drafts instead of bypassing the cap.
- The daily queue includes **at most 1 SaaS fundraising headline**, with `max_saas_funding_drafts_per_day=1`. Other SaaS products/launches can fill remaining eligible slots. This detects common “Series A/B” and “raises $...” forms; heuristics are not a full SaaS classifier.
- Source attribution in suggested text names the **linked article domain**, e.g. `Read at stocktwits.com`, rather than implying that the RSS feed is the writer. The feed name and linked domain are separately recorded in `writing.rss_feed_name` and `writing.linked_article_site`.
- Both new limits are respected across multiple non-preview runs within a Stockholm day and are reset only in the in-memory preview state. Prior day's history is unaffected.

All suggestions remain `publishable=false`, `fact_checked=false`, and `editor_approved=false`. Even a valid linked site does not prove the underlying facts. Old GitHub Issues are never overwritten. No AI API, Buffer, X posting, or billing has been added.

## Stage 11: promotion and futures noise reduction (no X or paid API)

After the live Stage 10 review preview, the rules correctly selected 9 stories across 7 RSS feeds and reduced SaaS funding headlines from 3 to 1. But a TechCrunch conference ticket discount appeared as SaaS news, while two updates described the same US stock-index futures theme. Every source also received an unnecessary syndication warning because comparing a hostname with a descriptive feed name was incorrect.

**Improvements:** when `exclude_promotional_headlines=true`, drop obvious ticket, registration, early-bird or discount promotion headlines; do not broadly block conference reporting. When `max_us_index_futures_drafts_per_day=1`, accept no more than one NASDAQ/Dow/S&P 500 **futures snapshot** across all market feeds in a day, to leave room for other market topics. This tracks usage across daily runs; a preview resets only its temporary counts. No filler stories are invented if relevant sources are exhausted.

**Attribution:** use a small explicit list of known feed domains; warn about cross-site links only when a known feed links outside its expected domain (e.g. a Yahoo Finance RSS result linking to Stocktwits). The linked domain is still not a guarantee about authorship or accuracy; human verification remains necessary. Unknown feeds don't trigger spurious mismatch claims.

No change to the nine-draft maximum, per-source and SaaS funding limits, review-only permissions, or publication safeguards.
