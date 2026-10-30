"""Run safe RSS-to-review-queue collection from the command line."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import (Article, fetch_feed, load_state, make_preview_state, parse_feed,
                   render_outputs, save_state, select_articles)
from .trend_signals import signals_for_selected
from .regions import select_india_preview_articles


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
                        help="Up to 40 fresh suggestions for public dashboard preview only")
    args = parser.parse_args()
    if args.dashboard_limit is not None and (
            not args.preview or not 9 <= args.dashboard_limit <= 40):
        parser.error("--dashboard-limit must be 9–40 and requires --preview; publishing quota unchanged")
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
        earliest = now - timedelta(hours=int(settings["lookback_hours"]))
        for source in sources:
            stat = {"source": source["name"], "category": source.get("category", "technology"),
                    "parsed_articles": 0, "recent_articles": 0, "status": "error"}
            try:
                data = fetch_feed(source["url"], timeout=int(settings["request_timeout_seconds"]),
                                  max_bytes=int(settings["maximum_feed_bytes"]))
                items = parse_feed(data, source["name"], source.get("category", "technology"))
                stat["parsed_articles"] = len(items)
                stat["recent_articles"] = sum(
                    earliest <= datetime.fromisoformat(item.published_at) <= now + timedelta(minutes=10)
                    for item in items)
                stat["status"] = ("ok" if stat["recent_articles"] else
                                  "no_recent_items" if items else "empty_or_unparseable")
                stories.extend(items)
            except Exception as exc:
                errors.append(f"{source.get('name','unknown source')}: {type(exc).__name__}: {exc}")
            diagnostics.append(stat)
    state = load_state(Path(args.state))
    selection_state = make_preview_state(state, now, settings["timezone"]) if args.preview else state
    public_limit = args.dashboard_limit if args.dashboard_limit is not None else int(settings["daily_draft_limit"])
    selected = select_articles(stories, selection_state, now, daily_limit=public_limit,
                               lookback_hours=int(settings["lookback_hours"]),
                               timezone_name=settings["timezone"],
                              category_order=tuple(settings.get("category_order", ("technology", "markets", "saas"))),
                              rank_by_relevance=settings.get("relevance_filter_enabled") is True,
                              max_per_source_per_day=(4 if args.dashboard_limit else
                                                         int(settings.get("max_drafts_per_source_per_day", 2))),
                              max_saas_funding_per_day=(3 if args.dashboard_limit else
                                                         int(settings.get("max_saas_funding_drafts_per_day", 1))),
                              exclude_promotional_headlines=settings.get("exclude_promotional_headlines") is True,
                              max_us_index_futures_per_day=int(settings.get("max_us_index_futures_drafts_per_day", 1)))
    india_selected = select_india_preview_articles(
        stories, sources, now, lookback_hours=int(settings["lookback_hours"]),
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
              f"{item['recent_articles']} recent, status={item['status']}")
    print("SAFETY: no AI or publishing API called; no X posts sent.")
    if args.preview:
        print("PREVIEW: daily draft quota and persisted history were not changed.")
    return 0 if stories or args.demo else 2


if __name__ == "__main__":
    raise SystemExit(main())
