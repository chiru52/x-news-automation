import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.core import (Article, canonical_url, clean_text, draft_template, load_state,
                          parse_feed, render_outputs, save_state, select_articles)

NOW = datetime(2026, 10, 29, 9, 30, tzinfo=timezone.utc)


def article(n=1, *, published=None, link=None, title=None):
    return Article(title=title or f"Relevant article {n}",
                   link=link or f"https://example.com/articles/{n}?utm_source=rss",
                   source="Test feed", published_at=(published or NOW).isoformat())


class CoreTests(unittest.TestCase):
    def test_rss_and_tracking(self):
        xml = b'''<rss version="2.0"><channel><item><title>A &amp; B</title>
        <link>https://example.com/story?utm_source=rss&amp;x=1</link>
        <description><![CDATA[<p>A short &amp; useful story</p>]]></description>
        <pubDate>Thu, 29 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>'''
        got = parse_feed(xml, "Example")
        self.assertEqual(got[0].title, "A & B")
        self.assertEqual(got[0].link, "https://example.com/story?x=1")
        self.assertEqual(got[0].summary, "A short & useful story")

    def test_atom(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>Atom story</title><link rel="alternate" href="https://news.example.org/abc"/>
        <updated>2026-10-29T08:00:00Z</updated></entry></feed>'''
        self.assertEqual(parse_feed(xml, "Atom")[0].title, "Atom story")

    def test_bad_urls_or_missing_dates(self):
        xml = b'''<rss><channel><item><title>Bad</title><link>javascript:alert(1)</link>
        <pubDate>Thu, 29 Oct 2026 09:00:00 GMT</pubDate></item>
        <item><title>No date</title><link>https://example.com/a</link></item></channel></rss>'''
        self.assertEqual(parse_feed(xml, "Example"), [])

    def test_daily_cap(self):
        state = {"seen": {}, "daily_drafts": {}}
        items = [article(i) for i in range(1, 9)]
        self.assertEqual(len(select_articles(items, state, NOW)), 5)
        self.assertEqual(select_articles(items, state, NOW + timedelta(minutes=2)), [])

    def test_next_day(self):
        state = {"seen": {}, "daily_drafts": {}}
        select_articles([article(1)], state, NOW)
        tomorrow = NOW + timedelta(days=1)
        self.assertEqual(len(select_articles([article(2, published=tomorrow)], state, tomorrow)), 1)

    def test_same_url_or_title(self):
        state = {"seen": {}, "daily_drafts": {}}
        items = [article(1), article(2, link="https://example.com/articles/1?utm_medium=abc"),
                 article(3, title="Relevant ARTICLE 1!")]
        self.assertEqual(len(select_articles(items, state, NOW)), 1)

    def test_remember_title(self):
        state = {"seen": {}, "daily_drafts": {}}
        select_articles([article(1)], state, NOW)
        self.assertEqual(select_articles([article(100, title="Relevant article 1")], state,
                                         NOW + timedelta(minutes=1)), [])

    def test_reject_stale_future_news(self):
        state = {"seen": {}, "daily_drafts": {}}
        items = [article(1, published=NOW - timedelta(days=3)),
                 article(2, published=NOW + timedelta(hours=1)), article(3)]
        self.assertEqual([a.title for a in select_articles(items, state, NOW)], ["Relevant article 3"])

    def test_bad_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("not JSON", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_state(path)

    def test_review_only_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "output"
            render_outputs([article(1)], out, NOW, [])
            data = json.loads((out / "review_queue.json").read_text(encoding="utf-8"))
            self.assertFalse(data["publishing_enabled"])
            self.assertFalse(data["articles"][0]["publishable"])
            self.assertIn("NEEDS_HUMAN_REVIEW", data["articles"][0]["status"])
            self.assertIn("[Write one verified insight", data["articles"][0]["draft"])

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            initial = {"seen": {"abc": NOW.isoformat()}, "seen_titles": {}, "daily_drafts": {"2026-10-29": 1}}
            save_state(path, initial)
            self.assertEqual(load_state(path), initial)

    def test_draft_length(self):
        self.assertLessEqual(len(draft_template(article(1, title="A very long title " * 40))), 280)


if __name__ == "__main__":
    unittest.main()
