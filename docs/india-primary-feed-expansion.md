# India preview: official RBI notifications and speeches (2026-11-01)

## Why
India had 25 visible stories while Global reached 50. The two regions are independent and India retains a **72-hour rolling publication-time window**. We will not fill remaining slots with duplicates, guessed publication dates or unrelated Global material.

## Preview-only new sources
| Feed | URL | Editorial type |
|---|---|---|
| RBI notifications | https://www.rbi.org.in/notifications_rss.xml | Official banking and regulatory announcements |
| RBI speeches | https://www.rbi.org.in/speeches_rss.xml | Official primary-source speeches, not independently reported news |

Both RSS feeds are published by the RBI (https://systemhealth.rbi.org.in/Scripts/rss.aspx%281%29.html) and independently catalogued by feed readers. The sources are tagged `india` and `markets`, `headline_only=true`, and `disable_images=true`. We display only dated RSS headlines, attributed publisher names, original outbound links and the existing manual-only draft workflow. **Source use beyond these links/headlines requires a separate commercial-rights review**, including any third-party content (https://www.rbi.org.in/Scripts/CommunicationPolicy.aspx). These are official announcements, not unbiased journalism or verified account statements.

The original RBI press-release feed remains unchanged, as do X editorial draft sources, X quotas, auto-posting disabled, Global windows and the per-publisher India cap. The source array is bounded and exact-URL allowlisted. All sources are fetched only during the scheduled/public-preview build or a separately approved future Worker deployment, never from a website visitor click. This PR does **not** change the production Cloudflare Worker.

## Correct diagnostic time windows
Previously the RSS CLI diagnostic counted everything against the Global 36-hour window even for 72-hour-eligible India news. It now records `recent_global` (36h) and `recent_india` (72h) based on the same country classifier as public preview. The legacy `recent_articles` is the sum for backward compatibility. This corrects reports; it does **not** change article timestamps or relax selection.

## Source rights and future growth
- PIB: official RSS index https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3 and copyright terms https://www.pib.gov.in/ContentPage.aspx?lang=2&menuid=19&reg=48 permit reproduction of PIB's own material with attribution, excluding third-party content. **Not activated:** previously probed PIB RSS endpoints lacked parseable item-level dates; no current date-validation has been demonstrated for this project's parser.
- SEBI: has an official RSS at https://www.sebi.gov.in/sebirss.xml, but its policy requires permission before reproducing website materials (https://www.sebi.gov.in/website-policy.html). **Not activated.**
- MyGov: the official copyright policy supports attributed reuse of its own material (https://www.mygov.in/simple-page/website-policies/), but a reliable, dated, compatible RSS/news feed has **not** been validated. **Not activated.**
- PB-SHABD: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2237648&lang=1&reg=3 says eligible media organizations can register for free platform access until March 2027. This is a **registration-gated option**, not a public RSS syndication permission. **Not integrated.**

## Release checklist
1. Unit-test full RSS parsing, regional limits and preview-only allowlist; the two new endpoints must fail closed if fetch fails or item dates are missing.
2. Optional read-only `python scripts/probe_official_rss.py` in a suitably networked environment: report only metadata (counts, date parseability), never full publisher content.
3. Compare actual static/live India counts, source health and publisher diversity in the next published preview. Counts are **not guaranteed** to reach 50 from these sources.
4. Confirm any separate Pages build is deployed; GitHub workflow-based deployment is still restricted to `varadachiru/x-news-automation` and will not execute just because `chiru52/main` merges.
5. Do not deploy the Cloudflare RSS Worker, change KV/Cron, or turn on X/AI publishing without explicit approval.
