"""Offline tests for unattributed-claim prevention and source-based drafts."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from newsbot.core import Article, render_outputs
from newsbot.github_review import render
from newsbot.writing import suggest_post, approximate_x_length


NOW = datetime(2026, 10, 29, 9, 0, tzinfo=timezone.utc)


def story(title="OpenAI launches an AI developer tool", *, category="technology",
          link="https://example.org/news", source="BBC Technology", summary=""):
    return Article(title=title, link=link, source=source, published_at=NOW.isoformat(),
                   category=category, summary=summary)


class DraftSuggestionTests(unittest.TestCase):
    def test_attributed_draft_does_not_invent_summary_claims(self):
        item = story(summary="ARTICLE SUMMARY: The model invented 99 new features.")
        suggestion = suggest_post(item)
        self.assertIn(item.title, suggestion["text"])
        self.assertIn("Read at example.org:", suggestion["text"])
        self.assertIn(item.link, suggestion["text"])
        self.assertNotIn("99 new features", suggestion["text"])
        self.assertFalse(suggestion["fact_checked"])
        self.assertFalse(suggestion["publishable"])
        self.assertFalse(suggestion["editor_approved"])
        self.assertFalse(suggestion["source_article_read"])

    def test_numbers_and_market_sensitive_claims_are_flagged(self):
        result = suggest_post(story("Nvidia shares rise 12% on $4B forecast",
                                    category="markets"))
        self.assertTrue(any("figure" in s or "number" in s for s in result["verification_warnings"]))
        self.assertTrue(any("Market-sensitive" in s for s in result["verification_warnings"]))
        self.assertTrue(any("rumor or forecast" in s for s in result["verification_warnings"]))

    def test_saas_relevance_remains_unverified(self):
        result = suggest_post(story("Startup raises $20M Series A",
                                    category="saas"))
        self.assertTrue(any("really belong" in s for s in result["verification_warnings"]))

    def test_long_link_is_counted_as_tco_but_unverified(self):
        url = "https://example.org/" + "some-very-long-article/" * 24
        result = suggest_post(story("Cloud software company launches developer tool",
                                    link=url, source="A sufficiently long source"))
        self.assertLessEqual(result["approx_x_length"], 270)
        self.assertEqual(result["approx_x_length"], approximate_x_length(result["text"]))
        self.assertIn(url, result["text"])
        self.assertTrue(result["limit_approximate"])

    def test_long_headline_truncates_and_flags_omissions(self):
        text = "SaaS startup announces funding of a new automation platform with details " * 7
        result = suggest_post(story(text, category="saas"))
        self.assertTrue(result["headline_shortened"])
        self.assertTrue(result["text"].splitlines()[0].endswith("…"))
        self.assertTrue(any("shortened" in note for note in result["verification_warnings"]))
        self.assertLessEqual(result["approx_x_length"], 270)

    def test_syndicated_headline_links_real_article_site(self):
        item = story("Nasdaq futures mixed after Fed policy statement",
                     category="markets",
                     link="https://stocktwits.com/news-articles/markets/example",
                     source="Yahoo Finance - Market Indices")
        suggestion = suggest_post(item)
        self.assertIn("Read at stocktwits.com:", suggestion["text"])
        self.assertNotIn("Via Yahoo Finance", suggestion["text"])
        self.assertEqual(suggestion["rss_feed_name"], "Yahoo Finance - Market Indices")
        self.assertEqual(suggestion["linked_article_site"], "stocktwits.com")
        self.assertTrue(any("Linked site differs" in x for x in suggestion["verification_warnings"]))
        self.assertIs(suggestion["feed_domain_mismatch"], True)

    def test_known_home_site_has_no_false_syndication_warning(self):
        a = story("Google launches new cybersecurity technology",
                  source="The Verge Tech",
                  link="https://www.theverge.com/tech/123")
        result = suggest_post(a)
        self.assertIs(result["feed_domain_mismatch"], False)
        self.assertFalse(any("Linked site differs" in x
                             for x in result["verification_warnings"]))

    def test_unknown_feed_domain_does_not_claim_mismatch(self):
        a = story("Company launches AI productivity platform",
                  source="Unlisted feed",
                  link="https://example.org/post")
        result = suggest_post(a)
        self.assertIsNone(result["feed_domain_mismatch"])
        self.assertFalse(any("Linked site differs" in x
                             for x in result["verification_warnings"]))

    def test_fails_closed_for_missing_source(self):
        with self.assertRaises(ValueError):
            suggest_post(story(link="javascript:alert(1)"))
        with self.assertRaises(ValueError):
            suggest_post(story(title=" "))

    def test_rendered_queue_includes_safe_draft_and_legacy_template(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            render_outputs([story()], out, NOW, [], preview_only=True)
            data = json.loads((out / "review_queue.json").read_text(encoding="utf-8"))
            selected = data["articles"][0]
            self.assertIn("Read at example.org:", selected["suggested_post"])
            self.assertIn("[Write one verified insight", selected["draft"])
            self.assertFalse(selected["writing"]["fact_checked"])
            self.assertFalse(selected["publishable"])
            self.assertIn("Source-attributed", render(data))
            self.assertIn("Publication approval:** NOT GRANTED", render(data))
            dashboard = (out / "review_dashboard.html").read_text(encoding="utf-8")
            self.assertIn("item.suggested_post || item.draft", dashboard)
            self.assertIn("Approx. X length", dashboard)


if __name__ == "__main__":
    unittest.main()
