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

## Real article imagery (RSS thumbnails)

Card covers now use the article-specific image URL explicitly supplied by the
publisher in media:thumbnail, media:content or image-typed RSS/Atom enclosure.
We **do not** scrape article pages, manufacture headline imagery, request
unsourced stock images, or add new third-party image API calls.

If no valid image is included (or remote loading fails), the cards show
typographic Technology, Business, or Markets covers instead of the previous
five vertical bars. Images are lazy loaded by the visitor's browser, with
no-referrer; visitors may connect directly to the publisher's image CDN.
The publisher's article URL is still the primary source link.

**Release dependency:** Adding the browser display alone cannot magically
create image metadata in previously collected stories. The shared scheduled
Cloudflare RSS Worker must be separately reviewed/deployed with the updated
RSS parser before live thumbnails are delivered. Do not redeploy the Worker
with the Pages build or the repository's editorial-inbox wrangler.toml.
Prior snapshots and cached cards gracefully show the typographic fallback.

RSS distribution alone does not establish image-republication rights.
Verify source terms/licensing before commercial release and disable imagery
from sources where embedding is not permitted. No image files are downloaded
or stored by SignalDesk in this implementation.

## More authentic RSS images — follow-up

Static preview and the shared Worker now also recognize an image embedded in
the *specific RSS item's* HTML description or `content:encoded`, along with
`media:group`. These sources of metadata are used only if the story has no
eligible structured media thumbnail or image enclosure. **No article web pages
are visited**, no image downloads are stored, and no new paid services or
scheduled jobs are added.

Guards reject HTTP or private-network/credential-bearing URLs, encoded control
characters, SVG/GIF, tiny tracking pixels, common logo/avatar placeholders,
and malformed images. A real displayed image must also decode to at least
160×90 pixels, or the browser retains its text-based category cover. The
fallback cover now correctly distinguishes World, Policy and Fact-check stories
from Technology, Markets and Business.

The existing read-only preview diagnostic adds per-publisher **aggregate**
story/image counts, with no headlines, article URLs or full feed content logged.
This reveals where missing images are simply a publisher feed limitation.

**Limitations:** some publishers provide no article image, block external image
display, or restrict reuse; those stories keep their editorial cover. Obtaining
a public RSS URL alone does not grant rights to republish a photo. Verify
licensing for commercial release. The shared Cloudflare RSS Worker still
requires a **separately approved deployment**; this PR alone changes the
static preview after Cloudflare Pages completes its regular build.
