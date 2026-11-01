"""Bounded one-off RSS diagnostics for SignalDesk India coverage.

Only probes the configured named public RSS endpoints; never visits article pages,
loads cover images, stores secrets, writes news, or publishes to X.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from newsbot.core import fetch_feed, parse_feed
from newsbot.regions import explicit_india_sources, is_india_article

ROOT = Path(__file__).resolve().parents[1]
INDIA_NAMES = (
    "Inc42 India Startups",
    "ET Entrepreneur India Startups",
    "ET Tech India",
    "YourStory India",
    "Alt News Fact Checks",
)


def inspect_one(feed, now=None, getter=fetch_feed):
    now = now or datetime.now(timezone.utc)
    result = {"source": feed["name"], "status": "unknown", "parsed": 0,
              "recent": 0, "india": 0, "images": 0}
    try:
        data = getter(feed["url"], timeout=7, max_bytes=800_000)
        items = parse_feed(data, feed["name"], feed.get("category", "technology"))
        result["parsed"] = len(items)
        recent = [a for a in items if now-timedelta(hours=36) <=
                  datetime.fromisoformat(a.published_at) <= now+timedelta(minutes=10)]
        result["recent"] = len(recent)
        region_names = explicit_india_sources([feed])
        result["india"] = sum(is_india_article(a, region_names) for a in recent)
        result["images"] = sum(bool(a.image_url) for a in recent)
        result["status"] = "ok" if recent else "no_recent_items"
    except Exception as exc:
        result["status"] = "error:" + type(exc).__name__
    return result


def run():
    sources = json.loads((ROOT/"config/sources.json").read_text("utf-8"))
    additional = json.loads((ROOT/"config/extra-news-sources.json").read_text("utf-8"))
    wanted = [s for s in sources+additional if s["name"] in INDIA_NAMES]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(inspect_one, wanted))
    print("SignalDesk one-off RSS source check: headline metadata only; no writes/publishing.")
    print("source | status | parsed | recent in 36h | India-qualified | RSS images")
    for item in results:
        print(" | ".join(str(item[x]) for x in
                         ("source", "status", "parsed", "recent", "india", "images")))
    return results


if __name__ == "__main__":
    run()
