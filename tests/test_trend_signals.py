"""Offline tests for headline editorial signals. Never infer social popularity."""
import unittest
from datetime import datetime, timedelta, timezone

from newsbot.core import Article, render_outputs
from newsbot.trend_signals import match_for_coverage, signals_for_selected
from newsbot.dashboard_export import read_news, validate_public_bundle, build_bundle
import tempfile
from pathlib import Path
import json

NOW = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)


def article(title, source="BBC Technology", *, url="https://example.com/ai-tool",
            category="technology", published=None):
    return Article(title=title, source=source, link=url, category=category,
                   published_at=(published or NOW).isoformat(), summary="Untrusted RSS description")


class TrendingSignalsTests(unittest.TestCase):
    def test_multi_feed_coverage_counts_distinct_feeds_not_reposts(self):
        original = article("OpenAI launches enterprise AI coding assistant for developers today")
        copy = article("OpenAI launches enterprise AI coding assistant for developers",
                       source="The Verge Tech", url="https://another.example/story")
        same_feed = article(original.title, url=original.link + "?utm_source=rss")
        result = signals_for_selected([original], [original, copy, same_feed], NOW)
        data = result[original.identity]
        self.assertEqual(data["coverage_feeds"], 2)
        self.assertIn("matching RSS feeds", data["reason"])
        self.assertTrue(0 <= data["score"] <= 100)

    def test_question_headline_downgraded_not_deleted(self):
        question = article("AI developers: Will a new AI tool launch next year?", url="https://example.com/forecast")
        announcement = article("AI developers launch new enterprise coding tool", url="https://example.com/launch")
        result = signals_for_selected([question, announcement],
                                      [question, announcement], NOW)
        self.assertLess(result[question.identity]["score"],
                        result[announcement.identity]["score"])

    def test_distinct_number_or_company_does_not_count_as_repeat(self):
        first = article("OpenAI raises $15 million for new enterprise developer tools")
        other = article("OpenAI raises $20 million for new enterprise developer tools",
                        source="The Verge Tech", url="https://other.example/20")
        self.assertFalse(match_for_coverage(first, other))
        a = article("OpenAI launches enterprise AI assistant for developer teams")
        b = article("Anthropic launches enterprise AI assistant for developer teams",
                    source="Ars Technica", url="https://other.example/anthropic")
        self.assertFalse(match_for_coverage(a, b))

    def test_outdated_or_future_feed_items_do_not_inflate_score(self):
        current = article("OpenAI launches AI developer software and new enterprise features")
        old = article(current.title, "Ars Technica",
                      published=NOW - timedelta(days=8))
        future = article(current.title, "The Verge Tech",
                         published=NOW + timedelta(hours=2))
        result = signals_for_selected([current], [current, old, future], NOW)
        self.assertEqual(result[current.identity]["coverage_feeds"], 1)

    def test_same_url_in_different_categories_not_multi_feed_confirmation(self):
        a = article("OpenAI launches new productivity app")
        b = article(a.title, "The SaaS News", category="saas")
        self.assertFalse(match_for_coverage(a,b))

    def test_rss_queue_preserves_safe_signal_for_export(self):
        selected = article("OpenAI launches AI developer software for enterprise teams")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            signal = signals_for_selected([selected], [selected], NOW)
            render_outputs([selected], out, NOW, [], trend_signals=signal)
            queue=json.loads((out/"review_queue.json").read_text("utf-8"))
            self.assertEqual(queue["articles"][0]["trend"]["coverage_feeds"], 1)
            exported=read_news(queue)
            self.assertEqual(exported[0]["trend_score"], signal[selected.identity]["score"])
            self.assertIn("trend_reason", exported[0])
            bundle=build_bundle(queue, [], out/"dist", generated_at=NOW.isoformat())
            validate_public_bundle(bundle)
            self.assertNotIn("Untrusted RSS description", json.dumps(bundle))

    def test_unsafe_trend_values_block_export(self):
        a = article("OpenAI launches AI enterprise application")
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            render_outputs([a], out, NOW, [])
            queue=json.loads((out/"review_queue.json").read_text("utf-8"))
            for bad in ({"score": True, "coverage_feeds": 1, "reason": "Headline relevance and recency"},
                        {"score": 300, "coverage_feeds": 1, "reason": "Headline relevance and recency"},
                        {"score": 80, "coverage_feeds": 1, "reason": "Private source analysis"},
                        {"score": 70, "coverage_feeds": 999, "reason": "Headline relevance and recency"}):
                queue["articles"][0]["trend"] = bad
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        read_news(queue)


if __name__ == "__main__":
    unittest.main()
