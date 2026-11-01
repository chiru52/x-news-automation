"""Daily static fallback must not let 30 global headlines hide India reporting."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.core import Article, render_outputs
from newsbot.regions import (
    explicit_india_sources, is_india_article, select_india_preview_articles,
)
from newsbot.dashboard_export import build_bundle, validate_public_bundle

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "config/sources.json").read_text())
NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


def article(i, source, title, summary="Enterprise software investment and cloud product update"):
    return Article(title=title, link=f"https://publisher.example/news/{i}",
                   source=source, published_at=(NOW-timedelta(minutes=20)).isoformat(),
                   summary=summary, category="technology")


class IndiaStaticFallbackTests(unittest.TestCase):
    def test_classification_is_evidence_based_not_publisher_nationality(self):
        named = explicit_india_sources(SOURCES)
        self.assertIn("Inc42 India Startups", named)
        self.assertIn("ET Entrepreneur India Startups", named)
        self.assertNotIn("YourStory India", named)
        self.assertTrue(is_india_article(article("a", "Inc42 India Startups",
                        "Startup unveils enterprise cloud software tools"), named))
        self.assertTrue(is_india_article(article("b", "BBC Technology",
                        "RBI announces new technology guidelines for Indian banks"), named))
        self.assertFalse(is_india_article(article("c", "YourStory India",
                         "Global cloud developer software launch and enterprise tools"), named))
        self.assertTrue(is_india_article(article("d", "BBC Business",
                         "Company expands enterprise software platform",
                         "The new Indian startup is based in Bengaluru"), named))

    def test_separate_india_selection_from_more_than_30_global_stories(self):
        global_stories = [
            article(f"global-{i}", "BBC Technology",
                    f"Global AI enterprise software startup launch number {i}")
            for i in range(45)
        ]
        india_stories = [
            article(f"india-{i}", "Inc42 India Startups",
                    f"Enterprise software funding and cloud technology startup update {i}")
            for i in range(7)
        ]
        picked = select_india_preview_articles(global_stories + india_stories,
                    SOURCES, NOW)
        self.assertGreaterEqual(len(picked), 1)
        self.assertLessEqual(len(picked), 8)
        self.assertTrue(all(item.source == "Inc42 India Startups" for item in picked))
        self.assertEqual(select_india_preview_articles(global_stories, SOURCES, NOW), [])

    def test_india_headlines_not_lost_to_technology_only_keyword_filter(self):
        from newsbot.core import Article
        local = Article(
            title="India national policy update affecting small businesses",
            link="https://publisher.example/india-policy-1",
            source="Independent World", published_at=NOW.isoformat(),
            category="policy")
        fact = Article(
            title="Fact check: Viral claim about India found to be misleading",
            link="https://publisher.example/india-fact-check",
            source="Alt News Fact Checks", published_at=NOW.isoformat(),
            category="factcheck", image_url="")
        unrelated = Article(
            title="Major international summit takes place in another region",
            link="https://publisher.example/international-1",
            source="Independent World", published_at=NOW.isoformat(),
            category="world")
        extras = [{"name":"Alt News Fact Checks","region":"india"}]
        chosen = select_india_preview_articles([local, fact, unrelated],
                    SOURCES+extras, NOW)
        self.assertEqual({a.link for a in chosen},
                         {local.link, fact.link})
        self.assertTrue(all(is_india_article(a,
            explicit_india_sources(SOURCES+extras)) for a in chosen))

    def test_only_preview_adds_supplemental_sources_to_static_reader(self):
        from pathlib import Path
        code=(ROOT/"newsbot/__main__.py").read_text()
        self.assertIn("if args.preview:",code)
        self.assertIn('config/extra-news-sources.json',code)
        self.assertIn('source.get("disable_images") is True',code)
        extras=json.loads((ROOT/"config/extra-news-sources.json").read_text())
        self.assertEqual(len(extras),2)
        self.assertEqual(len([x for x in extras if x.get('source_type') == 'official_primary']),1)
        self.assertTrue(extras[0]["disable_images"])
        self.assertEqual(extras[0]["category"],"factcheck")

    def test_supplemental_factcheck_remains_in_india_during_public_export(self):
        from newsbot.dashboard_export import read_news
        queue = {"publishing_enabled": False, "india_articles": [{
            "title": "Fact check: Viral media claim about India",
            "source": "Alt News Fact Checks",
            "link": "https://www.altnews.in/illustrative-example/",
            "category": "factcheck",
            "published_at": NOW.isoformat(),
            "suggested_post": "Review original evidence.",
            "summary": "Publisher has a fact-check of a public claim.",
            "publishable": False,
            "image_url": "",
        }]}
        stories = read_news(queue, "india_articles")
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["region"], "india")
        self.assertEqual(stories[0]["category"], "factcheck")
        self.assertEqual(stories[0]["image_url"], "")

    def test_daily_bundle_carries_india_feed_and_deduplicates_in_browser_by_id(self):
        external = article("global-1", "BBC Technology",
                           "Global enterprise software and AI cloud developer product")
        regional = article("india-1", "Inc42 India Startups",
                           "Startup unveils enterprise cloud and AI developer platform")
        unrelated = article("unrelated", "YourStory India",
                           "International enterprise cloud software developer product")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            render_outputs([external], folder, NOW, [], [], preview_only=True,
                           india_articles=[regional,unrelated])
            queue = json.loads((folder / "review_queue.json").read_text())
            self.assertEqual(len(queue["india_articles"]), 2)
            result = build_bundle(queue, [], folder / "site")
            self.assertEqual(result["news"][0]["region"], "global")
            self.assertEqual(len(result["india_news"]), 1)
            self.assertEqual(result["india_news"][0]["region"], "india")
            self.assertEqual(result["india_news"][0]["publisher"], regional.source)
            self.assertTrue(result["india_news"][0]["source_url"].startswith("https://"))
            validate_public_bundle(result)
            self.assertEqual(len(json.loads((folder / "site/data.json").read_text())["india_news"]), 1)

    def test_public_contract_refuses_global_padding_or_invalid_region(self):
        from newsbot.dashboard_export import read_news
        queue = {"publishing_enabled":False,"articles":[],"india_articles":[{
            "title":"International AI enterprise cloud developer tools launch",
            "source":"YourStory India", "link":"https://publisher.example/global",
            "category":"technology", "published_at":NOW.isoformat(),
            "summary":"International enterprise software update",
            "suggested_post":"Read the original source",
            "publishable":False
        }]}
        self.assertEqual(read_news(queue,"india_articles")[0]["region"],"global")
        with tempfile.TemporaryDirectory() as tmp:
            data=build_bundle(queue,[],Path(tmp)/"site")
            self.assertEqual(data["india_news"],[])
            data["india_news"]=[read_news(queue,"india_articles")[0]]
            with self.assertRaises(ValueError):
                validate_public_bundle(data)

if __name__ == "__main__":
    unittest.main()
