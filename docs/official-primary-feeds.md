# Official primary-source coverage (preview only)

## Why these two feeds
The original publisher shortlist remains unchanged: 8 requested Global entries, 11 India entries. This extension adds **two clearly labelled primary sources** to the separate supplemental news-feed registry, never to the original X publishing-bot sources:

- **Government of India — Press Information Bureau (PIB)**: official government press releases. Its [RSS directory](https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1) advertises the English press-releases feed. Its [copyright policy](https://www.pib.gov.in/content/132_2_Copyright-Policy.aspx?lang=1&reg=1) permits reuse without prior approval when source credit is prominent, content is accurate and not misleading, and **does not extend this right to third-party material**.
- **U.S. Federal Reserve Board**: official bank policy/regulatory releases. Its [RSS directory](https://www.federalreserve.gov/feeds/feeds.htm) advertises the all-press-releases feed. The [Board disclaimer](https://www.federalreserve.gov/disclaimer.htm) says Board website information is generally public domain unless indicated; any third-party content may have separate rights, and the Board should be cited.

These are **official viewpoints**, not independent journalistic verification. Do not present press releases as unbiased or independently fact-checked reporting. Both entries set `disable_images=true`, so SignalDesk does not redistribute potentially third-party press photos or use official seals as promotional art.

## Limits and safeguards
- These entries are added only to `config/extra-news-sources.json`; `config/sources.json` and publishing quota are unchanged. The preview reader only accepts three explicit feed identities and URLs, with images disabled.
- The static preview already has distinct maximum 50 Global / 50 India articles. Adding two official RSS feeds may improve coverage, but is **not a guarantee of hitting 50**.
- The read-only Worker import also uses this supplementary config, but is **not deployed by GitHub merge**. Live Worker rollout requires independent permission.
- This change does not create additional GitHub schedules, third-party data APIs, X posts, secret access or extra services. If a particular source feed returns invalid/empty data, don't invent stories or bypass date and duplicate limits.
- The preflight script sends one GET per fixed, documented official feed, with bounded response/time and no article fetch, image download or data writes. Check its output before claiming the source is operational.
- For published policy stories, source attribution should be obvious in the publisher label; verify facts against more than one source when appropriate. Official announcements are not a replacement for your requested independent Indian and world publishers.
