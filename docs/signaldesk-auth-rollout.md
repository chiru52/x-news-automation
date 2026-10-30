# SignalDesk authentication rollout (Phase 3A)

Authentication code is committed but **disabled** in `dashboard/auth-config.json`. The news workspace remains public and works without signing in.

## Before enabling

1. Create a **separate SignalDesk Supabase project**, not the ReplyPilot or Little King Chess project.
2. Configure email/password Auth with email confirmation, allowed site and redirect URLs pointing at the real SignalDesk domain (`/account.html`). Verify recovery redirects.
3. Configure a verified custom SMTP provider for real production email delivery, review abuse/rate limits and CAPTCHA options.
4. Deploy the public project URL and the **publishable** `sb_publishable_...` key in `auth-config.json` and set `enabled:true` in a separately reviewed PR. Never use a secret/service-role key in public files.
5. Confirm sign-up, email confirmation, sign-in, sign-out, expired session, forgot-password and password update manually in a limited test environment before production activation.
6. Profile badge on the news page remains Guest until a follow-up implements session-aware display. Browser-only bookmarks and drafts are NOT synchronized; guest experience is unchanged.

The frontend uses a pinned Supabase v2 ESM import. Verify that the CDN and domain CSP settings allow it before activation. Use HTTPS. No user tables, elevated roles, or user-write API access are introduced in this phase.
