# Reference-matched SignalDesk news explorer (preview review)

Design reference: the 6.4-second user-provided screen recording of a minimalist
editorial studio. The design is **not** a stock carousel or marketing gallery:
- calm paper-colored screen, very large faded editorial serif headline
- overlapping portrait cards that progress one at a time from right to left,
  maintaining depth and stacked positions (5400 ms when unpaused)
- selected card summary and original-source link on the right
- a single **Layered / Gallery** toggle retaining the selected story
- Gallery displays a dense, four-column (smaller on mobile) grid of the same
  news records. Hover spotlights, keyboard focus, click opens detailed drawer.
- source cards use code-generated abstract covers instead of unlicensed image
  fetching or full-copy publisher articles.

The normal editorial card with **Save, Copy, Edit, Post Studio, Why it matters,
personal status and Review Desk** is reused inside "Open all editorial tools".
The original workflow, archive and saved/copied views are unchanged.
Search and topic filtering still operate on the same curated story list.

Navigation:
- On news sections, the optional **focus mode** hides the standard sidebar,
  giving the gallery full width. Its "Back to workspace" control restores
  all standard navigation; the bottom bar switches All/Trending/Global/India.
- The display mode and focus preference are cosmetic localStorage settings.
- Press Left/Right in Layered, or swipe left/right on touch. Hovering the
  moving cards or focusing details pauses cycling. Reduced-motion users
  receive static, manual navigation.

This PR changes **only frontend presentation, static asset bundling, tests and
CI trigger efficiency**. No database, backend, feed, auth, paid AI, secrets,
Cloudflare Worker, X posting or production release is authorized here.

Pre-merge checks:
1. CI passes Python bundle export, JavaScript syntax and explorer unit tests.
2. Confirm visually in a real preview browser at desktop and mobile sizes.
3. Try both modes, focus mode, Global/India filters, saved/copied workflow,
   Post Studio and Review Desk, and reduced-motion preference.
4. Confirm this separate original GitHub repository is the intended destination
   before deploying; Cloudflare preview currently tracks the fork instead.
5. Do **not** deploy to production or auto-publish to X.
