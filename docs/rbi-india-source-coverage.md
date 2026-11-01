# RBI official India financial-news feed — staged preview integration

SignalDesk's India list previously had limited financial and banking-policy coverage. This change stages one additional *primary-source* RSS feed:

- Source: Reserve Bank of India — official press releases
- Feed: https://www.rbi.org.in/pressreleases_rss.xml
- Feed discovery: https://systemhealth.rbi.org.in/Scripts/rss.aspx%281%29.html
- Communication policy: https://www.rbi.org.in/Scripts/CommunicationPolicy.aspx
- Category: `markets`; region: `india`; publisher explicitly labelled **official**.
- Photos: disabled to avoid republishing third-party images, seals or logos.
- Only source-attributed RSS headlines and outbound links. No article scraping, images, full-text republication, content rewriting beyond existing user-reviewed draft templates, or paid services.
- Source-usage rights: **review required for commercial syndication beyond headlines and links**. The RBI communication policy says its daily press releases are issued for market participants, wire agencies and media, but this is not an unrestricted commercial licence. Verify if broader reuse is desired.

## Safety checks

A bounded read-only RSS probe verifies that the feed actually responds, contains parseable publication dates and dated headlines inside the 72-hour India window.

**Verified 2026-11-01 (GitHub Actions public preflight):** 10 RSS items parsed, all 10 within 72 hours, **8 eligible India Top 50 selections** after the per-publisher cap; zero were within the narrower 36-hour window. These are publisher announcements, not a guarantee of eight *additional unique* website cards because cross-source duplicates may be removed. The live production Worker was not changed. The one-off preflight was removed from future PR auditing after verification. No fake dates. No additional X permissions, automatic publishing, data storage or individual-article GETs.

The feed is included only in `config/extra-news-sources.json` and exact allowlisted in the **preview-only** reader. `config/sources.json` (original X editorial bot) remains unchanged. Source is also available to future read-only Worker code only if separately and explicitly deployed. Do not deploy the news Worker from this PR.

The existing India Top 50 cap and independent 72-hour window remain unchanged. Extra RBI articles can increase genuine India coverage, but some may be filtered as near duplicates, stale, repeated monetary-policy notices, or above the per-publisher cap of eight. No count guarantee.

## Other publisher candidates

- MEA official India press releases: **not activated**. MEA says copying requires permission: https://www.mea.gov.in/copyright-policy-mea.htm
- PIB: **not activated**. The attempted live RSS variants lacked item-level publication dates. We cannot invent those dates.
- Independent Indian publications: remain subject to their RSS and commercial usage terms.

## Production

Cloudflare Pages preview normally builds on main merges. The shared news Worker deployed to production still uses an older release and requires independent review; this PR changes no production Worker, Cron, CORS, X automation, keys, billing, or user login.
