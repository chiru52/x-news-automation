"""Offline Stage 23: avoid paying Copilot to repeatedly rewrite old news."""
from datetime import datetime, timedelta, timezone
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

from newsbot.story_history import (
    history_from_issues, read_history, normalize_url, title_terms,
    story_duplicate, choose_story_order,
)
from newsbot.copilot_review import select_research_evidence


NOW = datetime(2026, 10, 29, 17, 20, tzinfo=timezone.utc)
HYPER = "https://www.thesaasnews.com/news/hyperbolic-raises-30m-series-a-1"
ISSUE_19 = {
    "title": "AI Draft — Copilot Run 40918543275",
    "body": (
        "# Copilot single-story editorial preview\n"
        "**Candidate 2:** Hyperbolic Raises $30M Series A-1\n"
        "**Source URL:** " + HYPER + "\n"
        "VERIFICATION: NOT VERIFIED\n"
        "<!-- publication_authorized=false -->"
    ),
}
ISSUE_21 = {
    "title": "AI Draft — Copilot Run 40920271580",
    "body": (
        "**Candidate 2:** Hyperbolic Raises $30M Series A-1\n"
        "**Source URL:** " + HYPER + "?utm_source=rss\n"
        "DRAFT: another unverified draft"
    ),
}


def story(link, title, score=10, age_hours=2, category="saas"):
    return {
        "link": link,
        "title": title,
        "relevance": {"score": score},
        "published_at": (NOW - timedelta(hours=age_hours)).isoformat(),
        "category": category,
        "source": "RSS source",
        "publishable": False,
    }


def queue(*articles):
    return {
        "generated_at": NOW.isoformat(),
        "preview_only": True,
        "publishing_enabled": False,
        "articles": list(articles),
    }


def available(url):
    return {
        "source_url": url, "status": "extracted_unverified",
        "reason": None, "paragraphs": [
            {"id": "P1", "text": "One publisher paragraph about the company's new report."},
            {"id": "P2", "text": "Another publisher paragraph about the same report."},
        ],
    }


def old_history():
    return history_from_issues([ISSUE_19, ISSUE_21])


class HistoryTests(unittest.TestCase):
    def test_reads_existing_private_issue_19_and_21_formats(self):
        h = old_history()
        self.assertEqual(h["count"], 2)
        self.assertTrue(h["review_only"])
        self.assertEqual(h["stories"][0]["link"], HYPER)
        self.assertEqual(h["stories"][1]["link"], HYPER)

    def test_no_duplicate_for_another_news_story(self):
        one = story(
            "https://www.thesaasnews.com/news/example-ai-product",
            "A software startup releases a new tool for independent retailers")
        self.assertFalse(story_duplicate(one, old_history()["stories"]))

    def test_tracking_query_and_fragment_are_ignored(self):
        one = story(HYPER + "?utm_medium=social#main",
                    "A completely different headline should still be duplicate")
        self.assertTrue(story_duplicate(one, old_history()["stories"]))
        self.assertEqual(normalize_url(one["link"]), HYPER)

    def test_similar_syndicated_titles_are_duplicate_without_same_url(self):
        one = story(
            "https://www.reuters.com/example/hyperbolic-fundraising",
            "Hyperbolic raises $30M Series A-1")
        self.assertTrue(story_duplicate(one, old_history()["stories"]))

    def test_generic_topic_overlap_does_not_hide_distinct_articles(self):
        old = [{"title": "Tech stocks drop amid uncertain markets",
                "link": "https://example.com/markets/1"}]
        new = story("https://example.com/markets/2",
                    "Stocks rebound as software earnings improve")
        self.assertFalse(story_duplicate(new, old))

    def test_readonly_gh_issues_access_and_errors_fail_closed(self):
        client = Mock(return_value=Mock(stdout=json.dumps([ISSUE_19, ISSUE_21])))
        h = read_history("varadachiru/x-news-automation", runner=client)
        self.assertEqual(h["count"], 2)
        argv = client.call_args.args[0]
        self.assertEqual(argv[:3], ["gh", "issue", "list"])
        self.assertIn("--label", argv)
        self.assertIn("ai-draft-review", argv)
        self.assertNotIn("create", argv)
        with self.assertRaises(subprocess.CalledProcessError):
            read_history("varadachiru/x-news-automation", runner=Mock(
                side_effect=subprocess.CalledProcessError(1, "gh")))

    def test_unparseable_history_issue_fails_closed(self):
        with self.assertRaises(ValueError):
            history_from_issues([{"title": "AI Draft", "body": "no source"}])
        with self.assertRaises(ValueError):
            history_from_issues([{"title": "AI Draft", "body": None}])
        with self.assertRaises(ValueError):
            history_from_issues([{"title": "AI Draft", "body": "bad"}] * 1000)

    def test_preferred_used_story_skipped_choose_best_unused_next(self):
        items = [
            story("https://example.com/a", "Unrelated article older", score=3, age_hours=7),
            story(HYPER, "Hyperbolic Raises $30M Series A-1", score=50, age_hours=1),
            story("https://example.com/b", "New SaaS firm launches analytics", score=24, age_hours=6),
            story("https://example.com/c", "New market research on cloud AI", score=24, age_hours=1),
        ]
        order = choose_story_order(queue(*items), 2, old_history())
        self.assertEqual(order, [4, 3, 1])

    def test_preferred_unused_story_remains_first(self):
        items = [
            story("https://example.com/a", "Story A", score=1),
            story(HYPER, "Hyperbolic Raises $30M Series A-1", score=95),
            story("https://example.com/b", "Story B", score=50),
        ]
        self.assertEqual(choose_story_order(queue(*items), 1, old_history()), [1, 3])

    def test_source_research_skips_reviewed_without_fetch_or_ai(self):
        q = queue(story(HYPER, "Hyperbolic Raises $30M Series A-1"),
                  story("https://www.thesaasnews.com/news/new-products", "New software tools", 5))
        fetched = []
        def get(url):
            fetched.append(url)
            return available(url)
        result = select_research_evidence(q, 1, fetcher=get, history=old_history())
        self.assertEqual(fetched, [q["articles"][1]["link"]])
        self.assertEqual(result["selected_index"], 2)
        self.assertEqual(result["status"], "extracted_unverified")
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["history_count"], 2)
        self.assertIn("already_reviewed", [a["reason"] for a in result["attempts"]])

    def test_all_history_duplicates_produce_no_model_preparation(self):
        q = queue(story(HYPER, "Hyperbolic Raises $30M Series A-1"))
        fetched = Mock(side_effect=AssertionError("must not fetch duplicate"))
        result = select_research_evidence(q, 1, fetcher=fetched, history=old_history())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "no_unused_fresh_candidates")
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["attempts"][0]["status"], "skipped")
        fetched.assert_not_called()

    def test_old_story_outside_36_hours_is_skipped(self):
        q = queue(story("https://example.com/old", "Old headline", age_hours=50))
        result = select_research_evidence(q, 1, fetcher=lambda _: available("x"),
                                          history={"review_only": True, "stories": [], "count": 0})
        self.assertEqual(result["reason"], "no_unused_fresh_candidates")
        self.assertEqual(result["attempts"][0]["reason"], "stale_or_ineligible")

    def test_bad_history_not_silently_ignored(self):
        q = queue(story("https://example.com/new", "New article"))
        for bad in ({}, {"review_only": False, "stories": []}):
            with self.assertRaises(ValueError):
                select_research_evidence(q, 1, history=bad)

    def test_workflow_never_auto_ai_and_checks_history_before_model(self):
        workflow = Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("inputs.approve_credit_use == true", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("  issues: read", workflow)
        self.assertIn("python -m newsbot.story_history", workflow)
        self.assertIn("--history", workflow)
        self.assertLess(workflow.index("python -m newsbot.story_history"),
                        workflow.index("copilot -p "))
        self.assertEqual(workflow.count("copilot -p "), 1)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertIn("      issues: write", workflow)  # only the separate Issue-saving job
        self.assertNotIn("https://api.twitter.com", workflow)


if __name__ == "__main__":
    unittest.main()
