"""RSS context is feed-supplied metadata, never full article evidence."""
import unittest
from newsbot.source_context import preview_from_rss, MAX_PREVIEW
from newsbot.dashboard_export import read_news, validate_public_bundle, build_bundle
import tempfile
from pathlib import Path


def queue(summary):
    return {"publishing_enabled": False, "articles": [{
        "title": "ALPHA10X Raises $5M Pre-Series A",
        "link": "https://www.thesaasnews.com/news/alpha10x-funding",
        "source": "The SaaS News",
        "summary": summary,
        "suggested_post": "An editorial starting point https://www.thesaasnews.com/news/alpha10x-funding",
        "category": "saas",
        "publishable": False,
        "published_at": "2026-10-30T07:00:00Z",
    }], "feed_errors": []}


class RSSContextTests(unittest.TestCase):
    def test_sanitizes_markup_and_keeps_only_short_feed_preview(self):
        raw = ('<p>ALPHA10X, a workflow startup, said it has secured new funding '
               'and is planning a product launch.</p><script>SECRET TRACKER</script>')
        result = preview_from_rss(raw, "ALPHA10X Raises $5M Pre-Series A")
        self.assertIn("workflow startup", result)
        self.assertNotIn("<", result)
        self.assertNotIn("SECRET", result)
        self.assertLessEqual(len(result), MAX_PREVIEW)

    def test_long_rss_context_is_bounded_and_not_full_text(self):
        value = "This short publisher introduction describes its product update. " * 30
        result = preview_from_rss(value, "Different company launches a new AI tool")
        self.assertLessEqual(len(result), 170)
        self.assertTrue(result.endswith("…"))
        self.assertNotIn("<script>", result)

    def test_unhelpful_duplicate_or_promotional_description_is_excluded(self):
        title = "Company raises funding and plans to expand"
        for summary in (title, "Subscribe now for the latest articles and news",
                        "https://example.com/a", "<script>malicious</script>", None):
            with self.subTest(summary=summary):
                self.assertEqual(preview_from_rss(summary, title), "")

    def test_public_export_distinguishes_feed_context_and_no_context(self):
        with_summary = read_news(queue(
            "The team says the funds will support its new product, "
            "according to the RSS description circulated by the publisher."))
        self.assertEqual(with_summary[0]["context_status"], "rss_preview")
        self.assertTrue(with_summary[0]["source_preview"])
        no_summary = read_news(queue(""))
        self.assertEqual(no_summary[0]["context_status"], "headline_only")
        self.assertEqual(no_summary[0]["source_preview"], "")

    def test_public_schema_rejects_inconsistent_or_oversized_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = build_bundle(queue("The RSS preview provides additional publisher context "
                                      "about plans and upcoming services."), [],
                                Path(tmp) / "bundle")
        validate_public_bundle(data)
        data["news"][0]["source_preview"] = "x"*171
        with self.assertRaises(ValueError):
            validate_public_bundle(data)
        data["news"][0]["source_preview"] = ""
        with self.assertRaises(ValueError):
            validate_public_bundle(data)
        data["news"][0]["context_status"] = "full_article_verified"
        with self.assertRaises(ValueError):
            validate_public_bundle(data)

    def test_public_export_redacts_token_like_content(self):
        q = queue("A funding story in the RSS feed contains a dangerous "
                  "github_pat_token_please_never_publish so reject the build.")
        with self.assertRaises(ValueError):
            with tempfile.TemporaryDirectory() as tmp:
                build_bundle(q, [], Path(tmp) / "bundle")


if __name__ == "__main__":
    unittest.main()
