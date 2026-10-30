# SignalDesk AI Gateway — OFF and not deployed

This directory prepares owner-only AI explanations. It is NOT included in the
public Pages build or connected to the browser. Merging it causes zero AI calls.

## What the gateway protects

- AI_ENABLED flag: named AI_FEATURE_ENABLED, strictly equals true; no deployment
  config or binding is provided in this PR, so the feature remains off.
- Cryptographically verified Cloudflare Access RS256 JWT with exact issuer, AUD,
  expiration and one editor email. CORS by itself is NOT authentication.
- HTTPS publisher URL and 140–2800 characters of user-supplied article evidence.
  No scraping, paywall bypass, private GitHub evidence or inferred full-article text.
- Pinned Cloudflare Workers AI model: @cf/meta/llama-3.3-70b-instruct-fp8-fast
- Bounded summary, why-it-matters, copyable draft, and exact evidence quotation.
  A matching quote does NOT prove the whole answer is true.
- Atomic one-per-request reservation in dedicated D1 table ai_daily_calls.
  Daily cap is 1–10; a failed model call still consumes its reservation.
- No X account access, API calls, automatic posting, or GitHub writes.

The daily request cap IS NOT a hard USD budget. Costs, provider unit prices
and billing charges still require an explicit approved monetary limit.

## Before future activation — requires separate approval

1. Obtain user approval for AI provider/model, total daily/monthly spending
   budget, approved editor identity, and a tightly limited trial.
2. Create a dedicated D1 database and apply ai-gateway/schema.sql.
3. Create a separate Worker with an AI binding named AI and D1 binding named
   AI_BUDGET_DB. Do not modify the existing Pages production service.
4. Put all Worker hostnames behind Cloudflare Access. Include workers.dev,
   custom domain and any preview routes. Do not allow public access.
5. Configure the following server-only variables and secrets:
   AI_FEATURE_ENABLED=false
   MODEL_ID=@cf/meta/llama-3.3-70b-instruct-fp8-fast
   AI_DAILY_MAX_CALLS=1
   EDITOR_EMAIL=(approved email only)
   ACCESS_AUD=(Cloudflare Access AUD tag)
   ACCESS_TEAM_DOMAIN=(team.cloudflareaccess.com)
   API_ORIGIN=(exact protected Worker HTTPS origin)
   ALLOWED_WEB_ORIGIN=https://news.littlekingchess.com
6. Validate authentication, D1 quota, output checks and model errors offline.
   Then request separate explicit authorization for the first paid AI call.
7. Create an opt-in owner-only UI only after successful canary, independently
   reviewed price limits, actual token usage and billing alerts.

This Worker has NO deployment workflow and is not copied by the news exporter.
The public dashboard cannot reach or activate it in this PR.

## Offline verification

Run with Node 22:
    node --test tests/signaldesk-ai-gateway.test.mjs

The tests use fake AI and D1 bindings and locally signed JWTs. They make no
network requests and incur no provider charges.

Cloudflare reference:
https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/
https://developers.cloudflare.com/workers-ai/platform/pricing/
https://developers.cloudflare.com/pages/functions/get-started/

Evidence remains user-provided and unverified; model output needs human review.
