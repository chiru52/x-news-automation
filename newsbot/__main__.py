"""Run safe RSS-to-review-queue collection from the command line."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import (Article, fetch_feed, load_state, parse_feed, render_outputs,
                   save_state, select_articles)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect RSS news (review drafts only)")
    parser.add_argument("--sources", default="config/sources.json")
    parser.add_argument("--settings", default="config/settings.json")
    parser.add_argument("--state", default=".state/seen.json")
    parser.add_argument("--output", default="output")
    parser.add_argument("--demo", action="store_true", help="Use illustrative offline articles")
    args = parser.parse_args()
    settings = json.loads(Path(args.settings).read_text(encoding="utf-8"))
    if settings.get("publishing_enabled") is not False or settings.get("ai_provider") != "none":
        parser.error("SAFETY: stage 1 requires publishing_enabled=false and ai_provider=none")
    now = datetime.now(timezone.utc)
    stories: list[Article] = []
    errors: list[str] = []
    diagnostics: list[dict] = []
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
    selected = select_articles(stories, state, now, daily_limit=int(settings["daily_draft_limit"]),
                               lookback_hours=int(settings["lookback_hours"]),
                               timezone_name=settings["timezone"],
                              category_order=tuple(settings.get("category_order", ("technology", "markets", "saas"))),
                              rank_by_relevance=settings.get("relevance_filter_enabled") is True)
    render_outputs(selected, Path(args.output), now, errors, diagnostics)
    save_state(Path(args.state), state)
    print(f"Collected {len(stories)} articles, drafted {len(selected)}, feed errors {len(errors)}")
    for item in diagnostics:
        print(f"FEED {item['source']}: {item['parsed_articles']} parsed, "
              f"{item['recent_articles']} recent, status={item['status']}")
    print("SAFETY: no AI or publishing API called; no X posts sent.")
    return 0 if stories or args.demo else 2


if __name__ == "__main__":
    raise SystemExit(main())
