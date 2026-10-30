# SignalDesk source audit — 30 October 2026

This is a **configuration and public documentation review**, not proof that every endpoint returns valid recent RSS from the Cloudflare Worker. Production fetch results vary by upstream availability and must be monitored separately. No live private credentials or news article bodies are used here.

## Current feed configuration

- 18 configured RSS/Atom endpoints: technology, markets, and SaaS.
- 2 explicitly India-focused sources (`region: india`): **Inc42 India Startups** and **ET Entrepreneur India Startups**. Their channel descriptions are treated as India-focused.
- 2 more India-named publishers (ET Tech India, YourStory India) are **not** automatically classified as India news. International coverage from an Indian publisher must still be Global; classify by India-specific title and strong feed-preview context.
- General Global sources can also produce India news when the headline or strong description contains India-specific evidence (RBI, Nifty, Bengaluru, UPI, etc.).
- Multiple feeds belonging to one publication group (e.g. CNBC Markets + CNBC Investing; BBC Technology + BBC Business) count as **one publisher group** for trending coverage.
- These are RSS headline-monitoring sources, not independently verified reporting or proof of X/social-media trends.

## Source additions and permissions

Do not add unverified RSS endpoints just to raise the India counter. The official Economic Times RSS terms restrict aggregation, retention and redistribution; Mint labels its feed for individual non-commercial reading. Their RSS availability alone does not grant permission to republish. Check each publisher's terms and obtain appropriate permission **before adding new sources** or changing commercial use. The current release adds no new third-party feeds and does not change source licensing.

Reference pages reviewed:
- https://economictimes.indiatimes.com/rss.cms
- https://www.livemint.com/Object/6dFbaxSRSDKWk4Rit9Gk3M/rssHome.html
- https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1 (official Indian government RSS directory; not yet added)

## Ranking and deduplication contract

- Public Worker uses a 36-hour window of available RSS items; it does **not** query X or measure engagement.
- Conservative grouping requires equal numeric tokens, matching lead terms, and strong headline overlap, or an identical cleaned URL.
- Freshness, concrete development keywords, question/speculation language, and distinct publisher groups determine bounded scores (0–100).
- Trending means **editorial discovery priority**, not social popularity, factual verification or investment advice.
- Archives remain 30-day, public RSS only. The user-facing source-health panel stays removed.
- The site remains guest-first. No automatic X publishing.
