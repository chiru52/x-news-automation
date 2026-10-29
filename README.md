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
