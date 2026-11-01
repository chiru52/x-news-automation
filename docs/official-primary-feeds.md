# Official Global financial-policy source (preview only)

The user-requested publisher catalogue still contains the original **eight Global and eleven India source entries**. We added one supplementary, clearly identified primary source:

- **U.S. Federal Reserve Board** (official news, not independent journalism). Its [RSS listing](https://www.federalreserve.gov/feeds/feeds.htm) provides `press_all.xml`. Its [published disclaimer](https://www.federalreserve.gov/disclaimer.htm) says Board information is generally in the public domain unless otherwise indicated, and should be credited. Third-party photos are excluded (`disable_images=true`).

**Verification:** A bounded, read-only GitHub Actions preflight fetched its RSS successfully on 2026-11-01. The feed contained **20 parsed entries** but **zero published in the past 36 hours**. It is a reliable *occasional* policy source, not a daily volume source.

## Indian primary-source candidate deliberately not activated

India's [Press Information Bureau RSS](https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1) is listed as public, and [PIB's reuse policy](https://www.pib.gov.in/content/132_2_Copyright-Policy.aspx?lang=1&reg=1) permits accurately attributed material with third-party exceptions. However, the feed variants were inspected in the same bounded preflight: the main variant contained zero entries; alternate regional variants contained 20 entries **without individual publication dates**. The news pipeline must not assume that the feed collection time is the story publication time or invent freshness. **PIB therefore remains inactive** until we can verify a dated official feed.

### Scope and safety

- Only the supplemental, read-only RSS list is changed. The original editorial-bot source file, daily X quota and disabled publishing flags remain unchanged.
- Both active supplemental feeds (Alt News and the Federal Reserve) set `disable_images=true`: third-party rights to photographs are not presumed.
- Supplementary feed URLs are explicitly pinned in the preview reader, not user-controlled.
- No extra GitHub schedules, APIs, AI charges or Cloudflare deployments. The live Worker needs a separate deployment and remains untouched.
- Global maximum remains 50 **qualified recent** stories; India maximum remains 50. This change does **not** guarantee an increase in either count on a given day.
- Do not mix official press releases with independent newsroom reporting without visibly distinguishing the publisher.
