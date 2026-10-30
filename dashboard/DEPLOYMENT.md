# SignalDesk — Cloudflare news dashboard

A simple copy-and-paste workspace for AI/technology, SaaS and markets news. There is no X API, X authentication, automatic posting, or browser GitHub token.

## How it works

The existing RSS collector makes a news review queue. Existing private GitHub AI Draft Issues are read server-side in GitHub Actions using a temporary read-only token. The exporter saves title, category, publisher/source URL, suggested or editor-edited post text, and editorial status. No full issue bodies, evidence transcripts or secrets are included.

## Step 1 — Build the website package

GitHub > Actions > Build SignalDesk private news dashboard (no deployment) > Run workflow.

The workflow also runs daily at 07:12 UTC, although GitHub may delay scheduled jobs. When it succeeds, download either of two ZIP artifacts:

1. signaldesk-public-starter — a safe empty dashboard with no private news or drafts. Use it to create the Pages project.
2. signaldesk-private-site-(run id) — a private ZIP containing current RSS review suggestions and private AI drafts. Do not deploy it to an unprotected website.

AI-generated drafts only update when the separately authorized Copilot draft workflow produces new ones. The daily dashboard build does not run Copilot or spend AI credits.

## Step 2 — Create Cloudflare Pages with harmless starter content

1. Cloudflare dashboard > Workers & Pages > Create application > Pages > Direct Upload.
2. Name the Pages project signaldesk-news (or similar). Upload the downloaded starter artifact ZIP or extracted directory.
3. The default project.pages.dev address now serves an empty dashboard shell.
4. Use Pages > Custom domains > Add custom domain for your chosen subdomain, such as news.littlekingchess.com. Follow the built-in DNS wizard.
5. Before uploading private drafts, set up Cloudflare Zero Trust > Access > Applications to allow only your own email for the production project.pages.dev hostname, the wildcard preview hostnames, and the new custom domain.
6. Open each hostname in a private/incognito browser window, including data.json. Without Cloudflare Access authentication, every hostname and asset must be inaccessible. STOP if any hostname serves data publicly.

Important: Cloudflare Pages' preview Access toggle does not automatically protect either the production pages.dev address or the custom domain. All three require attention.

Official docs:
- https://developers.cloudflare.com/pages/get-started/direct-upload/
- https://developers.cloudflare.com/pages/configuration/custom-domains/
- https://developers.cloudflare.com/pages/platform/known-issues/
- https://developers.cloudflare.com/pages/configuration/preview-deployments/

## Step 3 — Upload the private website

Only AFTER confirming Access is enforced everywhere, deploy the ZIP named signaldesk-private-site-(run id) through the Pages Direct Upload deployment flow. Log in to your protected subdomain and test: real news and drafts, filters, search, source links, Copy post, browser-local saved items, and mobile layout.

The dashboard is read-only: it cannot edit GitHub Issues or post to X.

## Daily updates

The GitHub schedule builds a fresh private artifact each day, but intentionally does not deploy that artifact to Cloudflare until access protection is verified. In a separate follow-up, an Access-verified deployment job can update the live website automatically. Do not enable deployment without protection.

## Offline development (no GitHub or RSS network calls)

Run the built-in demo collector and export using an empty Issues JSON file:

  python -m newsbot --demo --preview --output output/demo
  python -m newsbot.dashboard_export --queue output/demo/review_queue.json --issues-file empty-issues.json --output dist/signaldesk
  python -m http.server 8000 --directory dist/signaldesk

The empty-issues.json file should contain an empty JSON array: [].

Then visit localhost:8000. All demo stories are explicitly illustrative.

## Safety

- No X API calls and no automatic publishing.
- Browser text is inserted using textContent, never untrusted HTML.
- No GitHub token, user credentials, or complete private Issue text in the browser.
- Private-repo validation and HTTPS source validation fail closed.
- Security response headers include noindex, no-store, and a strict same-origin content security policy. These headers are NOT authentication. Cloudflare Access is required for private content.
