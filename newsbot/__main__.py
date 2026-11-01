"""Run safe RSS-to-review-queue collection from the command line."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path

from .core import (Article, fetch_feed, load_state, make_preview_state, parse_feed,
                   render_outputs, save_state, select_articles)
from .preview_ranking import rank_preview_stories
from .trend_signals import signals_for_selected
from .regions import (select_india_preview_articles, global_preview_candidates,
                      explicit_india_sources, is_india_article, INDIA_PREVIEW_HOURS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect RSS news (review drafts only)")
    parser.add_argument("--sources", default="config/sources.json")
    parser.add_argument("--settings", default="config/settings.json")
    parser.add_argument("--state", default=".state/seen.json")
    parser.add_argument("--output", default="output")
    parser.add_argument("--demo", action="store_true", help="Use illustrative offline articles")
    parser.add_argument("--preview", action="store_true",
                        help="Show more review candidates without consuming today\'s real quota")
    parser.add_argument("--dashboard-limit", type=int, default=None,
                        help="Up to 50 fresh suggestions for public dashboard preview only")
    args = parser.parse_args()
    if args.dashboard_limit is not None and (
            not args.preview or not 9 <= args.dashboard_limit <= 50):
        parser.error("--dashboard-limit must be 9–50 and requires --preview; publishing quota unchanged")
    settings = json.loads(Path(args.settings).read_text(encoding="utf-8"))
    if settings.get("publishing_enabled") is not False or settings.get("ai_provider") != "none":
        parser.error("SAFETY: stage 1 requires publishing_enabled=false and ai_provider=none")
    now = datetime.now(timezone.utc)
    stories: list[Article] = []
    errors: list[str] = []
    diagnostics: list[dict] = []
    sources: list[dict] = []
    if args.demo:
        stories = [Article(title=f"DEMO ONLY: Illustrative technology headline {n}",
                           link=f"https://example.org/demo-story-{n}",
                           source="Demo data (not real news)", published_at=now.isoformat(),
                           summary="Synthetic test item") for n in range(1, 9)]
    else:
        sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
        if args.preview:
            # Only the unprivileged public preview adds supplemental sources.
            # The ordinary editorial bot, its publishing quotas and config
            # remain unchanged. Never accept arbitrary visitor-supplied URLs.
            extras = json.loads(Path("config/extra-news-sources.json").read_text(encoding="utf-8"))
            approved_primary_feeds = {
                "https://www.federalreserve.gov/feeds/press_all.xml":
                    ("global", "markets", "US Federal Reserve (official releases)"),
                "https://www.rbi.org.in/pressreleases_rss.xml":
                    ("india", "markets", "Reserve Bank of India (official press releases)"),
                "https://www.rbi.org.in/notifications_rss.xml":
                    ("india", "markets", "Reserve Bank of India (official notifications)"),
                "https://www.rbi.org.in/speeches_rss.xml":
                    ("india", "markets", "Reserve Bank of India (official speeches)"),
            }
            def allowed_preview_source(entry):
                if not isinstance(entry, dict) or entry.get("disable_images") is not True:
                    return False
                if entry.get("source_type") == "official_primary":
                    return (entry.get("region"), entry.get("category"), entry.get("name")) == (
                        approved_primary_feeds.get(entry.get("url")))
                return (entry.get("name") == "Alt News Fact Checks" and
                        entry.get("url") == "https://www.altnews.in/feed/" and
                        entry.get("region") == "india" and entry.get("category") == "factcheck")
            if (not isinstance(extras, list) or len(extras) > 6 or
                    len({entry.get("url") for entry in extras if isinstance(entry, dict)}) != len(extras) or
                    any(not allowed_preview_source(entry) for entry in extras)):
                parser.error("Invalid preview-only supplemental source configuration")
            sources = sources + extras
        earliest = now - timedelta(hours=int(settings["lookback_hours"]))
        # India preview allows valid articles from the preceding 72h.
        india_cutoff = now - timedelta(hours=INDIA_PREVIEW_HOURS)
        india_sources = explicit_india_sources(sources) if args.preview else set()
        for source in sources:
            stat = {"source": source["name"], "category": source.get("category", "technology"),
                    "parsed_articles": 0, "recent_articles": 0,
                    "recent_global": 0, "recent_india": 0, "status": "error"}
            try:
                data = fetch_feed(source["url"], timeout=int(settings["request_timeout_seconds"]),
                                  max_bytes=int(settings["maximum_feed_bytes"]))
                items = parse_feed(data, source["name"], source.get("category", "technology"))
                if source.get("disable_images") is True:
                    # Attribution rights for third-party fact-check images
                    # may be different from the publisher's original prose.
                    items = [replace(item, image_url="") for item in items]
                if source.get("headline_only") is True:
                    # Minimal reuse: official headline and outbound source link,
                    # never reprint the article text or feed summary.
                    items = [replace(item, summary="") for item in items]
                stat["parsed_articles"] = len(items)
                recent_global = sum(
                    earliest <= datetime.fromisoformat(item.published_at) <= now + timedelta(minutes=10)
                    and (not args.preview or not is_india_article(item, india_sources))
                    for item in items)
                recent_india = sum(
                    india_cutoff <= datetime.fromisoformat(item.published_at) <= now + timedelta(minutes=10)
                    and is_india_article(item, india_sources)
                    for item in items) if args.preview else 0
                stat["recent_global"] = recent_global
                stat["recent_india"] = recent_india
                stat["recent_articles"] = recent_global + recent_india
                stat["status"] = ("ok" if stat["recent_articles"] else
                                  "no_recent_items" if items else "empty_or_unparseable")
                stories.extend(items)
            except Exception as exc:
                errors.append(f"{source.get('name','unknown source')}: {type(exc).__name__}: {exc}")
            diagnostics.append(stat)
    state = load_state(Path(args.state))
    selection_state = make_preview_state(state, now, settings["timezone"]) if args.preview else state
    public_limit = args.dashboard_limit if args.dashboard_limit is not None else int(settings["daily_draft_limit"])
    # The public site has TWO independent regional capacities. Never allow
    # India candidates to consume Global slots and then drop them on export.
    # Keep the existing all-source editorial/X draft behavior unchanged.
    global_pool = global_preview_candidates(stories, sources) if args.preview else stories
    selected = select_articles(global_pool, selection_state, now, daily_limit=public_limit,
                               lookback_hours=int(settings["lookback_hours"]),
                               timezone_name=settings["timezone"],
                              category_order=tuple(settings.get("category_order", ("technology", "markets", "saas"))),
                              rank_by_relevance=settings.get("relevance_filter_enabled") is True,
                              max_per_source_per_day=(7 if args.dashboard_limit else
                                                         int(settings.get("max_drafts_per_source_per_day", 2))),
                              max_saas_funding_per_day=(3 if args.dashboard_limit else
                                                         int(settings.get("max_saas_funding_drafts_per_day", 1))),
                              exclude_promotional_headlines=settings.get("exclude_promotional_headlines") is True,
                              max_us_index_futures_per_day=int(settings.get("max_us_index_futures_drafts_per_day", 1)))
    if args.preview and args.dashboard_limit is not None and not args.demo:
        # Preview-only editorial Top 50 ranks the COMPLETE eligible RSS pool.
        # The original X draft selector above and non-preview history remain
        # unchanged; this override neither writes state nor sends anything.
        selected = rank_preview_stories(
            global_pool, now, lookback_hours=int(settings["lookback_hours"]),
            limit=public_limit, max_per_source=7, max_saas_funding=3,
            max_us_futures=int(settings.get("max_us_index_futures_drafts_per_day",1)),
            exclude_promotional=settings.get("exclude_promotional_headlines") is True)
    india_selected = select_india_preview_articles(
        stories, sources, now, lookback_hours=INDIA_PREVIEW_HOURS,
        exclude_promotional=settings.get("exclude_promotional_headlines") is True,
    ) if not args.demo and args.preview else []
    trend_signals = signals_for_selected(selected, stories, now,
                                         lookback_hours=int(settings['lookback_hours']))
    render_outputs(selected, Path(args.output), now, errors, diagnostics,
                   preview_only=args.preview, trend_signals=trend_signals,
                   india_articles=india_selected)
    if not args.preview:
        save_state(Path(args.state), state)
    print(f"Collected {len(stories)} articles, drafted {len(selected)}, feed errors {len(errors)}")
    for item in diagnostics:
        print(f"FEED {item['source']}: {item['parsed_articles']} parsed, "
              f"{item['recent_articles']} recent (Global 36h: {item['recent_global']}, "
              f"India 72h: {item['recent_india']}), status={item['status']}")
    print("SAFETY: no AI or publishing API called; no X posts sent.")
    if args.preview:
        print("PREVIEW: daily draft quota and persisted history were not changed.")
    return 0 if stories or args.demo else 2


if __name__ == "__main__":
    raise SystemExit(main())
