# X News Automation — Stage 1 (safe, draft-only)

A private Python/GitHub Actions project that collects RSS news, removes repeats and creates at most **five human-review templates per Europe/Stockholm day**.

**Nothing in this version can publish to X or Buffer.** It does not call Grok, OpenAI or any other AI API. Drafts include a visible placeholder: `[Write one verified insight after reading the article.]`.

## Features

- Reads RSS 2.0 and Atom feeds and extracts titles, original links, timestamps and short descriptions.
- Excludes undated, stale, future-dated and invalid-link stories. Removes known URL tracking parameters.
- Removes duplicates by canonicalized URL and normalized headline, including across runs when state is restored.
- Caps review templates at 5 per Stockholm calendar day.
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
