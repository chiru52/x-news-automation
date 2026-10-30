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
        self.assertNotIn("Read at ", suggestion["text"])
        self.assertIn("I", suggestion["text"].split("\n\n")[1])
        self.assertIn(item.link, suggestion["text"])
        self.assertNotIn("99 new features", suggestion["text"])
        self.assertFalse(suggestion["fact_checked"])
        self.assertFalse(suggestion["publishable"])
        self.assertFalse(suggestion["editor_approved"])
        self.assertFalse(suggestion["source_article_read"])

    def test_funding_headline_becomes_natural_attributed_explanation(self):
        result = suggest_post(story("ALPHA10X Raises $5M Pre-Series A",
                                    category="saas",
                                    link="https://www.thesaasnews.com/news/alpha10x"))
        self.assertIn("ALPHA10X reportedly raised $5M in a Pre-Series A round", result["text"])
        self.assertIn("what the team builds next", result["text"])
        self.assertTrue(result["text"].endswith("https://www.thesaasnews.com/news/alpha10x"))
        self.assertNotIn("Read at ", result["text"])
        self.assertFalse(result["fact_checked"])

    def test_market_question_remains_a_question_not_a_predicted_result(self):
        result = suggest_post(story("Stock Market: Will S&P 500 Open Up or Down Today?",
                                    category="markets"))
        self.assertIn("Will S&P 500 Open Up or Down Today?", result["text"])
        self.assertIn("open question", result["text"])
        self.assertNotIn("will rise", result["text"].lower())
        self.assertNotIn("will fall", result["text"].lower())

    def test_earnings_uses_human_context_without_inventing_figures(self):
        title = "Tech firms take fresh hit as earnings misses fan AI fears"
        result = suggest_post(story(title, category="markets",
                                    summary="Invented losses of 99 billion dollars"))
        self.assertIn(title, result["text"])
        self.assertIn("look at the actual results", result["text"])
        self.assertNotIn("99 billion", result["text"])

    def test_human_voice_is_deterministic_and_varies_across_categories(self):
        title = "New product launches in the enterprise software market"
        a = suggest_post(story(title, category="technology"))
        b = suggest_post(story(title, category="technology"))
        c = suggest_post(story(title, category="saas"))
        self.assertEqual(a["text"], b["text"])
        self.assertNotEqual(a["text"], c["text"])
        self.assertNotIn("Read at ", a["text"])
        self.assertIn("https://example.org/news", a["text"])
        self.assertLessEqual(approximate_x_length(a["text"]), 270)

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
        self.assertIn("https://stocktwits.com/news-articles/markets/example", suggestion["text"])
        self.assertNotIn("Read at ", suggestion["text"])
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
            self.assertNotIn("Read at ", selected["suggested_post"])
            self.assertIn("I", selected["suggested_post"])
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
