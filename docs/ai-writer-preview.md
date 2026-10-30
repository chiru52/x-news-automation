# SignalDesk AI Writer — preview-only setup

This feature uses Cloudflare Pages Functions at `/api/ai-writer` and OpenAI's Responses API.

## Required Cloudflare preview project configuration

Configure these in **signaldesk-preview** only. Never commit them in GitHub:
- `OPENAI_API_KEY` — encrypted secret, server-only
- `AI_WRITER_MODEL` — supported model name in your OpenAI project
- `SUPABASE_URL` — SignalDesk Supabase Auth project URL
- `SUPABASE_PUBLISHABLE_KEY` — Supabase public/publishable key
- `AI_WRITER_KV` — Cloudflare KV binding for best-effort hourly quota

Do not enter these on the production project until explicitly approved.

**Deployment blocker:** KV is not an atomic quota system, so simultaneous requests could exceed the five/hour soft cap. This is suitable only for controlled, low-volume preview testing. Before opening to wider users, replace with an atomic durable rate limiter plus billing guardrails. API costs may be incurred when enabled.

## Behavior

- The browser requests a Supabase access token from an existing signed-in session.
- Server authenticates token using Supabase Auth, checks allowed Origin, validates input, and consumes a soft hourly quota before making an OpenAI request.
- The model returns three different styles. Users explicitly select/edit one.
- No AI key is sent to the browser. No automatic X publishing. No AI API calls when unconfigured.
- Supporting source URLs are **not fetched or verified**. Numeric/current claims need independent human verification.
- Production `news.littlekingchess.com` stays untouched.

## Validation

The existing static unit-test workflow must pass. Confirm that Cloudflare Pages Functions are included in Git-based preview deploy (the function is in repository-root `functions/`). Check that unconfigured requests return HTTP 503 and unauthenticated requests fail closed. Then test a signed-in user with a limited API budget. Never use a provider API key in the browser.
