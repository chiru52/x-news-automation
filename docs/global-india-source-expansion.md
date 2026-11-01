# Global + India source expansion — review and staged rollout (2026-11-01)

## Scope
- `config/editorial-sources.json` records **all 8 Global** and **all 11 India** requested source entries. The directory is available inside the dashboard with direct links and truthful statuses. The same publisher may have a Global and India section; these are source entries, not 19 separate legal entities.
- The collector and static export now support **up to 50 Global and 50 India** articles per fresh snapshot. This is a ceiling, *not a guarantee* of 100 qualifying news stories. All Story/Trending continues to deduplicate news from both regions.
- The existing RSS collection occurs exclusively through the same scheduled Worker Cron, not visitor requests. No new scheduled Actions, billing service or extra KV writes. The source-limit is increased to 32 for future **approved** outlets; the original bot source list stays unchanged; actual Worker feed list currently has 19 (18 original + 1 supplemental).
- The only newly activated source is **Alt News**, with `category=factcheck` (not market news), India geography and publisher-asset imagery turned off. Attribution and article-specific third-party licensing must still be respected. Other requested sources are catalogued, not secretly scraped.

## Verification / licensing gate

| Source | Feed path finding | Integration status | Note |
| --- | --- | --- | --- |
| WION | No reliable official RSS verified | Feed not confirmed | Open its website |
| Firstpost World | Section RSS not confidently verified | Feed not confirmed | Do not invent an URL |
| BBC India | Public BBC RSS available | Permission required | BBC identifies RSS business use as requiring a licence |
| Reuters India | No official public Reuters RSS | No official RSS | Do not use third-party Google News as Reuters' own feed |
| Al Jazeera English | RSS available | Permission required | Publisher terms restrict automated reuse |
| The Hindu World | International RSS available | Rights review | A public feed is not a commercial grant |
| Indian Express World | World RSS available | Permission required | Official RSS terms restrict commercial use |
| ORF | Official RSS unconfirmed | Feed not confirmed | Research/analysis is not breaking news |
| The Hindu India | National RSS available | Rights review | Separate source section; check rights |
| Indian Express India | General RSS available | Permission required | Official RSS terms restrict commercial use |
| NDTV India | Listed RSS addresses available | Permission required | Official RSS terms restrict commercial use |
| Scroll.in | Listed FeedBurner feed available | Permission required | Website terms say personal non-commercial use |
| The Wire | Alternate CMS RSS reported | Permission required | Website specifically restricts feed reuse |
| ThePrint | RSS link available | Rights review | Terms still need review |
| Newslaundry | Public news RSS unconfirmed | Feed not confirmed | Private podcast feeds are not public news licences |
| The News Minute | News RSS endpoint unconfirmed | Feed not confirmed | Website /topic/rss is about RSS topic, not an RSS endpoint |
| Alt News | Official site feed available | Attributed CC BY 3.0 candidate activated | Images excluded; third-party exceptions apply |
| Mint | Official Markets RSS available | Permission required | Official RSS page personal noncommercial only |
| Moneycontrol | Source listing exists, direct official RSS not verified | Feed not confirmed | HTML/listing pages are not RSS |

## Evidence and policy (reviewed 2026-11-01)
- BBC: https://www.bbc.co.uk/usingthebbc/terms-of-use — metadata/RSS business permissions
- Al Jazeera: https://www.aljazeera.com/terms-and-conditions/
- Indian Express: https://indianexpress.com/rss/
- NDTV: https://www.ndtv.com/rss
- Mint: https://www.livemint.com/static/rss
- Scroll.in: https://scroll.in/terms
- The Wire: https://science.thewire.in/rss-feeds/
- Alt News: https://www.altnews.in/about/
- The Hindu feeds listed at https://www.thehindu.com/rssfeeds

Feed candidates were discovered from publisher pages and dated RSS directories but **not all were tested from a Cloudflare Worker runtime**. Neither a listed RSS URL nor a public website grants right to copy content or third-party images. The directory exists precisely to make these gates visible.

## Before a broader production release
1. Obtain any required publisher syndication permission or substitute explicitly licensed sources. Record evidence in the catalogue before adding to `config/extra-news-sources.json`.
2. Audit the currently used original 18 feeds and their terms too; this PR doesn't certify existing feeds.
3. Test representative RSS updates in a separate Worker with identical approved bindings and no auto-publishing. Confirm < 50 regional stories when fewer qualify.
4. Confirm 15-minute schedule, CPU usage, archive writes and cached fallback within free-plan quotas.
5. Deploy collector separately from Cloudflare Pages; root Wrangler is for the *editorial inbox*, not the news collector. Do not touch production without approval.
6. Confirm all categories, fact-check labels, dates, sources and page performance in the live preview.

## 2026-11-01 India coverage: 72-hour live parity and PIB
- Live collector code uses the same **72-hour India / 36-hour Global** date windows as the public preview; failed-feed recovery preserves only eligible dated stories. This is not a live Worker deployment; approval is required before deploying the Worker.
- Added a clearly attributed **official primary source**, the Press Information Bureau (PIB) press-release RSS listed at https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1. PIB's copyright policy https://www.pib.gov.in/content/132_2_Copyright-Policy.aspx?lang=1&reg=1 allows reproduction of its material with clear attribution but excludes third-party materials. The dashboard uses headline and link only, **never feed summaries or photos**. These are government statements, not independent reporting.
- Direct RSS retrieval in the Cloudflare Worker runtime has **not** yet been verified. A failed fetch cannot generate invented stories. The India per-source cap is eight and regional max is 50; no guarantee of 50 qualifying stories on a weekend.
- No X publishing, extra Cron invocation, paid API, or extra KV writes were added. Production deployment and verified live counts are separate tasks.
