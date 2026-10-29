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

## Stage 15: GitHub Copilot one-draft review test (opt-in; no automatic posting)

The **selected AI provider is GitHub Copilot**, using a separate, explicitly triggered workflow: `.github/workflows/copilot-one-draft.yml` (**Copilot - one news draft (manual, consumes AI credits)**). The existing daily RSS collector and its schedule remain unchanged and NEVER invoke Copilot. There is deliberately **no scheduled AI run**.

### Personal-account setup (one-time)

Your repository `varadachiru/x-news-automation` is **personally owned**. Unlike eligible organization-owned repositories, its Copilot usage should be authenticated using a **fine-grained personal access token** linked to your own Copilot entitlement. Create a fine-grained PAT at https://github.com/settings/personal-access-tokens/new owned by your personal account. Restrict its repository access to `x-news-automation`, grant the minimum **Copilot Requests** account permission supported by GitHub, set a short expiration date, and create the secret `COPILOT_PERSONAL_TOKEN` under **Repository → Settings → Secrets and variables → Actions**. Never paste the token into this chat, an Issue, a PR or the repository source. GitHub may require additional account or policy eligibility; the workflow fails closed if authentication is missing.

### First test

1. Keep **additional paid Copilot usage disabled** in GitHub billing settings. The screenshot of included credits does not establish the exact remaining quantity or guarantee that all AI usage is free.
2. After this PR passes CI and is merged, open **Actions → Copilot - one news draft (manual, consumes AI credits)**.
3. Click **Run workflow** on `main`. Select **Article index = 1** and explicitly check **I approve one Copilot AI request using my included credits**. It defaults to **unchecked**.
4. The workflow collects fresh RSS in `--preview` mode only (no quota history change), then submits **one** candidate as an unverified RSS prompt to GitHub Copilot CLI. It displays the result in the Actions **Summary**, and stores an optional `copilot-editorial-preview` artifact.
5. Independently open the linked publisher article, verify claims, and manually edit the final proposed text. The tool cannot mark it verified or approved, and **never posts to X, Buffer or any other network**.

The workflow uses a **30 AI credit soft limit per Copilot CLI session**, the minimum currently supported; this is not a guaranteed hard spending ceiling (an in-flight model response can slightly exceed it). A GitHub Actions job timeout and a single invocation further restrict usage. Using a personal Copilot account's included allowance is expected only if available and eligible; excess usage depends on your actual GitHub billing settings.

### Security

The workflow requires `workflow_dispatch`, checks the explicit credit-use checkbox, and has only `contents: read` repository permission. It does not use the repository built-in token for Copilot requests. Its personal secret is injected **only into the token check and the Copilot invocation**. The runner checks out repository content without persistently storing checkout credentials. Copilot is run from an isolated temporary working directory with shell, write, URL and memory tools denied, built-in MCPs disabled, and custom instructions disabled. This limits what the AI assistant itself can execute, but **the CLI must still connect to GitHub Copilot's model service**; the user approves this network and AI-credit usage by checking the box.

The output is displayed only as HTML-escaped text, marked **NOT VERIFIED** and **NOT APPROVED**, with publisher link, and without any automated posting. The model is **not asked to browse external articles**, because this first test disables web tools for security and predictability. It can only draft from unverified RSS metadata. High-quality independent research and source verification require a later separately reviewed step.

**Do not confuse Stage 14 (manual ChatGPT PR #13, not merged) with this alternative:** this PR implements a separate GitHub Copilot path and does not depend on that PR.

## Copilot authentication update: no personal token required

The initial manually triggered Copilot preview failed with **missing token**, then **Copilot CLI authentication failed** for the fine-grained user token. GitHub's latest documentation now supports using the **built-in GitHub Actions `GITHUB_TOKEN`** for Copilot CLI in personally owned repositories, with usage billed to the repository owner's Copilot seat: https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/copilot-cli-in-github-actions .

This workflow now grants `copilot-requests: write` alongside `contents: read`, and injects only the short-lived `GITHUB_TOKEN: ${{ github.token }}` into the Copilot CLI step. There is no PAT, secret check, organization, repository transfer, or additional AI API needed. **The previously configured `COPILOT_PERSONAL_TOKEN` is no longer read**; the user may revoke the old personal PAT and remove the unused GitHub Actions secret after confirming this workflow is active.

The task remains `workflow_dispatch` ONLY, with `approve_credit_use` unchecked by default, `--preview` quota protection, ONE model invocation maximum, `--max-ai-credits=30` session soft limit, restricted Copilot tool use, no X/Buffer publishing, and an editorial-only Actions Summary. **Merging this PR does not call Copilot or spend AI credits.** The user must check billing/spending settings and opt in for each manual test; model requests may still be billed to the user's allowance.

If the user later chooses an organization-owned repository, `GITHUB_TOKEN` usage is instead billed directly to that organization, provided its **Allow use of Copilot CLI billed to the organization** policy is enabled. Do not transfer this repository just to solve the old PAT issue.

## Stage 16 — Source-grounded Copilot editorial writing (one story, opt-in)

The previously successful [Copilot preview run #40912673131](https://github.com/varadachiru/x-news-automation/actions/runs/40912673131) proves that GitHub's **built-in `GITHUB_TOKEN`** can authenticate Copilot CLI without creating an organization or personal PAT. However, that draft only paraphrased an unverified RSS headline.

This upgrade adds a **single bounded publisher article retrieval** *before* Copilot is invoked:

1. The separate manually dispatched Copilot workflow collects normal RSS candidates in `--preview` mode; it never consumes the persisted daily quota.
2. `newsbot.source_research` tries to retrieve **exactly one public HTTPS article** for the chosen index. Domains are restricted to a reviewed list of news publishers; redirects, private/local hosts, unusual ports, non-HTML content and oversized pages are rejected. DNS is screened for non-public addresses. The fetch has an 8-second timeout and 400 KB response cap.
3. A standard-library HTML parser extracts at most **8 visible article paragraphs and 3,200 source characters**. Raw HTML and full articles are not uploaded as artifacts. These paragraphs are publisher statements, **not independent verification or corroboration**.
4. If no useful article evidence is available (paywall, redirect, JavaScript-heavy site, unsupported domain, insufficient paragraphs), the workflow writes an explanatory Actions Summary and **skips the paid AI request**. You can select another candidate on a later explicitly approved run.
5. When article text is usable, Copilot is given numbered paragraphs `[P1]`, `[P2]`, etc. and instructed to distinguish publisher claims from fact, cite which paragraphs support proposed insights, avoid copying source passages, and **WITHHOLD** the draft unless the article evidence supports a meaningful original post. The GitHub Actions Summary displays the source extraction status, AI draft, excerpt citation format checks and a manual-review warning.
6. The response is **not fact-checked** by a second publisher. There is no reliable automated verification of every claim, article quality or true X length. A human editor must still read the source and corroborate meaningful statements.

**Safety invariants remain unchanged:** the Copilot workflow is `workflow_dispatch` ONLY; it requires a default-unchecked explicit credit-use approval; only one selected article and one model invocation maximum; GitHub `GITHUB_TOKEN` permissions remain limited to `contents: read` and `copilot-requests: write`; the 30-AI-credit session soft limit and five-minute model timeout remain; no X/Buffer integration, scheduling, sending, or GitHub Issue changes. The original scheduled RSS collector is unchanged. **Opening/merging the PR consumes no model credits.**

This is **article-grounded drafting**, not independent fact-checking. Sites can block retrieval, and retrieval uses a public-site allowlist and no redirects. The user must not expect every chosen article to generate a draft. Ineligible sources deliberately yield `WITHHELD` and no billable model call.

## Stage 17 follow-up: source access diagnostics and safe fallback

The [Stage 17 workflow run #40914861402](https://github.com/varadachiru/x-news-automation/actions/runs/40914861402) **completed successfully but skipped AI**: all 9 RSS candidates were selected, yet the *first preferred article* could not be extracted. No Copilot credits were consumed by that run, and no X post was sent. The previous version did not display the precise extraction reason in the Actions Summary.

A manually authorized Copilot run now attempts the **preferred article first**, then tries remaining shortlisted articles (at most 9 total, bounded by the existing per-article HTTPS allowlist, size and timeout safeguards). Once an article yields usable publisher paragraphs, it **stops searching** and passes **only that one article** to the unchanged **single Copilot CLI invocation**. The selected index is shown in the GitHub Actions Summary, alongside a compact table of failed candidate indices and sanitized reason codes. This lets the user distinguish `redirect_blocked`, `no_reliable_article_text`, `domain_not_allowed_or_insecure`, and other extraction issues rather than guessing.

If **none** of the nine candidate article pages yield usable text, the workflow exits successfully but **skips Copilot entirely**. It never falls back to headline-only AI drafting. It never performs independent corroboration and never authorizes posting. The GitHub credit-use checkbox is still **unchecked by default**, there is no AI schedule or X/Buffer publishing path, and the existing `--max-ai-credits=30` soft session limit applies only when the single Copilot request is actually made. The free publisher HTTP reads can take longer than one-source checks; no browser logins, cookies, paywalls or redirects are bypassed.

To test after merge, the user must independently choose to invoke the manual workflow and approve the one Copilot request. PR CI itself performs offline tests only and consumes no AI credits.

## Stage 19 — Better article extraction and private AI Drafts

The [Step 18 run](https://github.com/varadachiru/x-news-automation/actions/runs/40916291735) shortlisted nine stories but extracted no usable publisher article prose, so Copilot was deliberately skipped.

**Improved source handling:** Article retrieval now supports HTML paragraphs plus structured NewsArticle/Article/BlogPosting articleBody JSON-LD (commonly present on JavaScript-heavy news sites). The bounded HTML download cap increases from 400 KB to 1.2 MB, but material provided to Copilot stays at **8 snippets / 3,200 characters**. Up to two same-host HTTPS canonical redirects are supported, with public DNS checking. Redirects to other domains, HTTP, private hosts or paywalls remain blocked. This is **publisher evidence, not independent corroboration**. The existing table of extraction failure reasons remains available in Actions Summary.

**Dedicated private AI Drafts area:** After an explicitly approved, successful Copilot run, a separate least-privilege GitHub Actions job creates one editable private Issue per run with the label **ai-draft-review**. Find all successful drafts at [AI Drafts — GitHub Issues](https://github.com/varadachiru/x-news-automation/issues?q=is%3Aissue%20label%3Aai-draft-review). Human edits are never overwritten by reruns; a duplicate run reuses the existing Issue. If the repository is ever made public, the Issue-saving job refuses to save any AI draft. The original Actions Summary and seven-day artifact remain available.

**Safety:** Copilot job permissions remain read-only contents plus Copilot Requests write; a *separate* job can create private GitHub Issues with contents read and issues write but has no Copilot permission. No AI schedule, no X or Buffer API, and no automatic publishing. A new Copilot request still requires the manually checked, default-off approval checkbox; the 30-credit session limit is a soft limit and not a guaranteed spending cap.

### Finding and editing a generated draft

1. Following merge, manually run [Copilot — one news draft](https://github.com/varadachiru/x-news-automation/actions/workflows/copilot-one-draft.yml) **only when you choose to spend credits**.
2. If a draft was generated, visit [AI Drafts](https://github.com/varadachiru/x-news-automation/issues?q=is%3Aissue%20label%3Aai-draft-review) and open the new run's Issue.
3. Read the original source, corroborate claims, and edit the proposed text before manually posting anything. **Issue creation is not publishing approval.**
4. If there is no new Issue, check the workflow's Source access diagnostics table to learn why the model may have been skipped.


## Stage 21 — Cleaner Copilot draft reviews and visible source evidence

A verified successful example is [private AI Draft #19](https://github.com/varadachiru/x-news-automation/issues/19) from [Copilot run #40918543275](https://github.com/varadachiru/x-news-automation/actions/runs/40918543275). Its proposed X post included model-internal citations like `[P3][P4]`, but the private Issue did not show the supporting source snippets. Those citations should be for editorial reasoning, not public X copy.

New reviews now include, in this order:

1. **Clean proposed X post (manual editing required):** Copilot's single-line draft with internal `[P#]` markers removed automatically, the original URL preserved as-is, and the estimated X length displayed. Any overlength or missing-source issues are flagged; the system never invents facts, figures, links or corrections. `WITHHELD` drafts remain withheld.
2. **Automated format check:** checks source URL equality, required fields, explicit NOT VERIFIED status, cited paragraph identifiers, evidence references and approximate X length. An otherwise complete format check still states that factual accuracy has **not** been assessed.
3. **Supporting publisher excerpts:** up to four SHORT excerpts of cited publisher paragraphs, identified by `P1`, `P2`, etc. The complete article is NOT republished and no independent verification is implied. Editorial readers should compare context to the original source.
4. **Full Copilot response:** preserved as safely escaped untrusted text, for inspecting reasoning and warnings.
5. **Editable private Issue:** after a successful manually approved AI run, the separate Issue-saving job pre-fills the *My edited X post (manual only)* field with the clean, citation-free proposed text. Editors can change it via GitHub's Edit control. **Publication approval remains NOT GRANTED**.

The enhanced format and source checks do **not** guarantee factual validity. A human must verify claims and independently corroborate important claims before manually using the draft. These improvements only affect **new future runs**; existing Issue #19 and other human-edited Issues are not overwritten or backfilled.

All existing protections remain: the Copilot workflow is manually dispatched with a default-unchecked credit approval, capped at one Copilot request per run (30-credit soft session limit, not a billing hard cap); the separate Issue-saving job only has Issues permission; no automatic X or Buffer publishing, no X credentials, no scheduled AI jobs. The PR's tests run offline and consume no Copilot credits.

## Stage 23 — Unique and fresh news before any Copilot credit use

In [AI Draft #19](https://github.com/varadachiru/x-news-automation/issues/19) and [AI Draft #21](https://github.com/varadachiru/x-news-automation/issues/21), two separate credit-using runs wrote about **the same Hyperbolic funding news**. GitHub's RSS `--preview` intentionally doesn't update the daily review queue's persisted history, so without a second **AI-specific** history, repeated runs can draft the same article.

The manually dispatched Copilot workflow now performs an additional **read-only private GitHub Issues lookup before article research or Copilot**. It reads Issues labeled `ai-draft-review`, including the existing #19 and #21, and extracts their original source URL and news headline (never the full body into the Copilot prompt). It then:

1. **Skips previously drafted URLs**, including tracking query variations and fragments.
2. **Skips highly similar news headlines** even when syndicated to another URL; conservative high-word-overlap matching avoids suppressing unrelated news on the same broad topic. This is heuristic, not semantic AI verification.
3. **Filters stale items**, requiring the feed publication timestamp to be no more than 36 hours old, consistent with current RSS source collection settings.
4. **Honors the user's preferred article index** when it is unused and fresh. Otherwise prioritizes eligible alternatives by existing relevance score, then publication recency; source extraction still requires genuine publisher paragraphs and follows the earlier safety restrictions.
5. **Skips Copilot with no AI credit use** if all candidates were drafted, stale or blocked. The Actions Summary lists each skipped candidate and its reason (`already_reviewed`, `stale_or_ineligible`) alongside publisher extraction diagnostics.

The built-in temporary GitHub token gains **`issues: read` permission in the Copilot preflight job**, while the separate private draft-saving job retains `issues: write`. If private Issues cannot be read or the history is malformed, the workflow fails **before** any model call; it does not silently ignore history and spend credits. The history lookup is limited to 999 existing AI Draft Issues; at the limit, it fails closed instead of assuming the oldest Issue has been seen. Previous Issues are **never overwritten** and the scheduled non-AI RSS collector remains unchanged.

**No automatic X publishing, scheduling, or posting is added.** GitHub Copilot still runs at most once per manually triggered workflow after a separately checked explicit credit-approval checkbox (30-credit *soft* session limit, not a guaranteed spend cap). Tests run entirely offline and do not request Copilot credits.

**Next after merge:** Only if you want to use another potentially billable Copilot request, run the manual workflow on `main` and inspect the source-access table. It should skip Hyperbolic if it reappears in the shortlist and select a different supported article when available. The resulting new review will be saved under [private AI Draft Issues](https://github.com/varadachiru/x-news-automation/issues?q=is%3Aissue%20label%3Aai-draft-review). No new Issue is created if all candidates are excluded.


## Stage 25 — Better tech-news priority and cleaner X source links

Stage 24 succeeded at avoiding the repeated Hyperbolic story, but [AI Draft #23](https://github.com/varadachiru/x-news-automation/issues/23) picked a relatively routine Pinnacle earnings update, used an ambiguous company name and retained a Yahoo Finance RSS tracking parameter.

**Editorial selection:** The manually initiated Copilot workflow now offers two modes:
- **quality_first (default):** prioritizes eligible AI, technology, developer tools, security, cloud and SaaS launch articles over routine market-price/earnings stories. The ranking uses the RSS category, unverified headline, existing relevance score and recency, not an AI call or independent verification.
- **preferred_first:** retains the previous behavior, where the manually chosen article index is tried first if unused and fresh.

Both modes still skip previously drafted stories, articles older than 36 hours and sources that fail safe publisher-text extraction. If none remain, Copilot is skipped without spending model credits. The Actions Summary identifies the strategy and selection result.

**Writing improvements:** The prompt asks Copilot to name the company or product unambiguously (full company name when supported by publisher text) and to offer a source-supported reason the development matters to an AI/technology/SaaS reader. It should withhold an X draft if relevant details or company identity cannot be substantiated. Prompts are guidance, not proof of truth or a guarantee of quality; every post still requires human fact-checking.

**Clean sharing links:** The raw original Source URL remains intact in the private GitHub Issue for audit and deduplication. A separate Shareable source URL strips a conservative set of tracking parameters (including .tsrc, utm_*, fbclid) and the URL fragment without changing the domain or removing meaningful query fields. Copilot is instructed to use this share link. If it reproduces the exact tracking URL, clean proposed X copy automatically substitutes the cleaned link without inventing or following a new URL. Editors should still verify that the link opens.

**Safety:** No additional model calls, automatic X posts, schedules or paid providers. Manual Copilot workflow_dispatch requires its existing default-off credit-use checkbox; maximum one Copilot CLI call per approved run with a 30-credit soft session limit (not a guaranteed billing cap). AI Drafts remain private and editable, without publication approval. All PR tests operate offline with zero Copilot credits.

The new editorial ranking and cleaned URLs have passed offline regression tests. Actual article selection and model writing quality still require a future manually approved, potentially billable live run if desired.


## Stage 27 — Claim-to-paragraph prechecks (no automatic fact-check claims)

[Step 26's Microsoft AI Draft #25](https://github.com/varadachiru/x-news-automation/issues/25) exposed a review gap: a model can cite an existing paragraph ID even when the specific number it claims (for example, **60,000 eligible employees**) does not actually appear in that limited paragraph excerpt. Earlier checks only verified the ID existed. A cropped first-190-character preview could also miss relevant text farther into that paragraph.

For **new, manually approved** drafts, the editorial review now:

1. **Checks numeric details against cited paragraphs sentence by sentence** in Copilot's EVIDENCE and WHY_IT_MATTERS fields. It compares literal figures in model claims and the particular referenced publisher excerpt(s), with basic equivalence such as 60K = 60,000 and $30 million = 30M. It also checks whether the public DRAFT's numeric details occur in any publisher paragraph cited by the analysis. Missing citations, unavailable IDs, and numeric gaps are flagged as potential editorial problems.
2. **Shows the most claim-relevant part of each cited publisher paragraph**, selected by overlapping numbers and words, rather than always cutting off the paragraph's opening 190 characters. Excerpts remain short, HTML-escaped and bounded, with no full-page or new URL retrieval.
3. **Adds an "Automated claim-to-evidence precheck" section** to the private AI Draft. If a problem is detected, the issue still displays the draft and supporting text for review, but its separate "My edited X post" section is **NOT prefilled**. Instead it asks a human editor to investigate and write approved copy. This is also true for pre-existing format warnings.
4. **Strengthens the one-shot Copilot prompt**: require paragraph references at the end of each factual sentence; do not copy numerical details unless the referenced publisher excerpt actually contains them; do not conflate employees *eligible for buyouts* with actual layoffs.

**Important limitations:** These checks compare only **short, automatically extracted, unverified publisher snippets** (at most eight paragraphs, each truncated to 550 characters). A number omitted by truncation may cause a *false warning*. A matching number does **not** prove accurate attribution, the denominator or scope, semantic meaning, truth, or independent corroboration. An unflagged post is **NOT fact-checked or approved** and still requires a human to read the original and independently verify material claims. Other unsupported nonnumeric assertions may not be detected. There is no extra AI model call or spend for these checks.

Offline tests cover both matching and mismatched numeric citations, short excerpt focus, escaped HTML, partial source limitations, withheld output and no-prefill behavior; tests never use AI credits. Existing private Issues (#19, #21, #23, #25) remain unchanged. The Copilot workflow is still manual-only with explicit default-off credit approval, at most one model call per approved run (30-credit soft limit, not a billing hard cap) and **no automatic X publishing**.
