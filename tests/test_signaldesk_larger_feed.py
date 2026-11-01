"""Larger public feed without increasing X/AI operations or per-visitor RSS calls."""
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from newsbot.core import Article, select_articles

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)


class LargerDashboardFeedTests(unittest.TestCase):
    def test_thirty_curated_stories_possible_with_source_diversity(self):
        items = []
        for category in ("technology", "saas", "markets"):
            for publisher in range(3):
                for number in range(6):
                    items.append(Article(
                        title=f"{category} company news story {publisher} {number}",
                        link=f"https://example.org/{category}/{publisher}/{number}",
                        source=f"Feed {category} {publisher}",
                        published_at=NOW.isoformat(),
                        category=category))
        state = {"seen": {}, "daily_drafts": {}}
        selected = select_articles(
            items, state, NOW, daily_limit=30, lookback_hours=36,
            max_per_source_per_day=4,
            max_saas_funding_per_day=3, max_us_index_futures_per_day=1)
        self.assertEqual(len(selected), 30)
        self.assertEqual(Counter(a.category for a in selected),
                         {"technology": 10, "saas": 10, "markets": 10})
        self.assertLessEqual(max(Counter(a.source for a in selected).values()), 4)

    def test_dashboard_only_preview_does_not_change_editor_daily_quota(self):
        settings = json.loads((ROOT / "config/settings.json").read_text("utf-8"))
        self.assertEqual(settings["daily_draft_limit"], 9)
        self.assertIs(settings["publishing_enabled"], False)
        self.assertEqual(settings["ai_provider"], "none")
        workflow = (ROOT / ".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn("--preview --dashboard-limit 30", workflow)
        self.assertIn("PUBLISH_ENABLED: 'false'", workflow)
        self.assertNotIn("secrets.X_", workflow)
        self.assertNotIn("copilot -p", workflow)
        self.assertIn("cron: '12 7 * * *'", workflow)

    def test_cli_requires_preview_and_safe_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = [sys.executable, "-m", "newsbot", "--demo", "--output", directory]
            for value in ("8", "51", "10000"):
                completed = subprocess.run(base + ["--preview", "--dashboard-limit", value],
                                           cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(completed.returncode, 0, value)
            not_preview = subprocess.run(base + ["--dashboard-limit", "30"],
                                         cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(not_preview.returncode, 0)
            good = subprocess.run(base + ["--preview", "--dashboard-limit", "50"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(good.returncode, 0, good.stderr)
            queue = json.loads((Path(directory) / "review_queue.json").read_text("utf-8"))
            # One demo source is deliberately capped at four stories per build.
            self.assertEqual(len(queue["articles"]), 4)
            self.assertFalse(queue["publishing_enabled"])

    def test_browser_only_checks_every_fifteen_minutes_and_has_safe_pagination(self):
        page = (ROOT / "dashboard/index.html").read_text("utf-8")
        client = (ROOT / "dashboard/app.js").read_text("utf-8")
        self.assertIn('id="refresh-note"', page)
        self.assertIn("Last refreshed shows when the news was generated", page)
        self.assertIn('id="updated-display"', page)
        self.assertNotIn('id="last-checked-display"', page)
        self.assertIn('id="theme-toggle"', page)
        self.assertIn('id="load-more"', page)
        self.assertIn("let visibleCount = 12;", client)
        self.assertIn("list.slice(0, visibleCount).map(card)", client)
        self.assertIn("visibleCount += 12", client)
        self.assertIn("nextFeedCheckAt(Date.now(), feedCheckJitterMs)", client)
        self.assertIn('document.addEventListener("visibilitychange"', client)
        self.assertIn('shouldCheckAfterReturn(Date.now(), lastFeedCheckAt)', client)
        self.assertIn('lastFeedCheckAt = Date.now()', client)
        self.assertNotIn('setInterval(', client)
        self.assertIn('fetch("./data.json",{cache:"no-store"})', client)
        self.assertIn('fetch("./feed-config.json",{cache:"no-store"})', client)
        self.assertIn('liveFeedUrl=allowCollectorUrl(config.live_feed_url)', client)
        self.assertIn('new Date(data.generated_at).getTime() <= new Date(loadedSnapshot).getTime()', client)
        self.assertIn("if (feedCheckInProgress) return", client)
        self.assertIn('document.visibilityState === "visible"', client)
        self.assertIn('hour:"2-digit", minute:"2-digit"', client)
        self.assertNotIn("method: 'POST'", client)
        self.assertNotIn('method: "POST"', client)


if __name__ == "__main__":
    unittest.main()
