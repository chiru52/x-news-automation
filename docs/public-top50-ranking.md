# SignalDesk Top 50 editorial ranking — public preview only

This is **a ranking of publisher-supplied, dated, region-eligible RSS articles**, not a fact-check, automated endorsement, popularity measurement, user profiling, or prediction.

## Selection

- Keep Global and India separate: Global uses its existing **36-hour** window, India the disclosed **72-hour** rolling window.
- Score the *complete eligible pool* before selecting up to **50 stories per region**. Do not add filler or silently move stories between regions.
- Give a transparent, deterministic editorial signal from recency, measured headline event words, subject relevance, and presence of publisher RSS context. No sensationalism multipliers or image-preference boosts.
- Apply a modest per-publisher and per-category crowding penalty to keep a single outlet or subject from drowning out other eligible stories.
- Enforce hard per-publisher caps (Global **7**, India **8**) and retain conservative restrictions on promotional pitches, SaaS funding and repetitive index futures.
- Reject stale/future-dated records, repeated links, identical titles, and near-identical syndicated headlines. Prefer not to collapse genuinely separate articles on similar topics.
- Preserve source links, publication timestamps, and unverified status; do not claim that the ranking verifies facts or that it represents a global consensus.
- Ranking is **stable for the same snapshot** regardless of RSS response order.

## UI behavior

The existing static preview's Global and India modes preserve each ranking's order in both Layered and Gallery view. **All Stories stays newest-first**, Trending stays based on the existing editorial signal, and Archive / Saved / Copied / Review remain unchanged. The currently separately deployed live Worker has **not** been given this new rank metadata; when live data becomes accessible its current newest-first behavior remains until separately upgraded.

## Safety and cost

No added RSS requests, API calls, AI models, paid service, image downloads, GitHub schedules, authentication changes, Worker deployment or X post delivery. The existing live Cloudflare Worker and production website are untouched. All changes are preview-only and use simple Python / JavaScript logic that can be unit-tested without network access.

## Limitations

The classifier is a modest headline-based editorial heuristic, not a measure of absolute journalistic importance. It can prioritize a documented policy announcement over a newer routine update but cannot determine whether competing reports are accurate. The current source licensing/availability review remains necessary. Showing 50 requires 50 qualifying licensed, dated, deduplicated stories after publisher caps; if there are only 17, SignalDesk should display 17.
