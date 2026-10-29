"""Offline tests for GitHub-native editorial review. No network or publishing."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from newsbot.github_review import escape, link_url, render, open_or_reuse_issue


SAMPLE = {
    "generated_at": "2026-10-29T06:00:00+00:00",
    "publishing_enabled": False,
    "preview_only": True,
    "articles": [{
        "title": "AI startup announces funding",
        "source": "Test RSS",
        "category": "saas",
        "published_at": "2026-10-29T05:30:00+00:00",
        "link": "https://example.org/news",
        "draft": "Unverified headline, replace before using",
        "publishable": False,
        "relevance": {"score": 7},
    }],
}


class GithubReviewTests(unittest.TestCase):
    def test_issue_worksheet_never_authorizes_posting(self):
        body = render(SAMPLE)
        self.assertIn("News editorial review — 2026-10-29", body)
        self.assertIn("Open article", body)
        self.assertIn("Read original article and verified", body)
        self.assertIn("My reviewed X draft", body)
        self.assertIn("publication_authorized=false", body)
        self.assertIn("NOT publication approval", body)

    def test_escape_feed_metadata_and_unsafe_url(self):
        attack = "<script>alert(1)</script> ](https://evil.example)"
        self.assertNotIn("<script>", escape(attack))
        self.assertNotIn("](https://evil.example)", escape(attack))
        self.assertEqual(link_url("javascript:alert(1)"), None)
        self.assertEqual(link_url("file:///etc/passwd"), None)
        payload = json.loads(json.dumps(SAMPLE))
        payload["articles"][0]["title"] = attack
        self.assertNotIn("<script>", render(payload))

    def test_issue_creation_fails_closed_on_unsafe_flags(self):
        payload = json.loads(json.dumps(SAMPLE))
        payload["publishing_enabled"] = True
        with self.assertRaises(ValueError):
            render(payload)
        payload["publishing_enabled"] = False
        payload["articles"][0]["publishable"] = True
        with self.assertRaises(ValueError):
            render(payload)

    def test_existing_daily_issue_preserves_edits(self):
        url = "https://github.com/sample/private/issues/3"
        result = Mock(stdout=json.dumps([{
            "title": "News editorial review — 2026-10-29", "url": url}]))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GH_TOKEN": "test-only"}):
                with patch("newsbot.github_review.subprocess.run", return_value=result) as mocked:
                    actual = open_or_reuse_issue(SAMPLE, "sample/private", Path(tmp))
            self.assertEqual(actual, url)
            self.assertEqual(mocked.call_count, 1)
            self.assertEqual((Path(tmp) / "github_issue_link.txt").read_text().strip(), url)

    def test_no_candidate_does_not_create_issue(self):
        queue = dict(SAMPLE, articles=[])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("newsbot.github_review.subprocess.run") as mocked:
                self.assertIsNone(open_or_reuse_issue(queue, "sample/private", Path(tmp)))
                mocked.assert_not_called()

    def test_new_issue_is_editorial_not_x(self):
        existing = Mock(stdout="[]")
        created = Mock(stdout="https://github.com/sample/private/issues/7\n")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GH_TOKEN": "test-only"}):
                with patch("newsbot.github_review.subprocess.run",
                           side_effect=[existing, created]) as mocked:
                    url = open_or_reuse_issue(SAMPLE, "sample/private", Path(tmp))
            self.assertEqual(url, "https://github.com/sample/private/issues/7")
            self.assertEqual(mocked.call_count, 2)
            cmd = mocked.call_args_list[1].args[0]
            self.assertEqual(cmd[:3], ["gh", "issue", "create"])
            worksheet = (Path(tmp) / "github_issue_body.md").read_text()
            self.assertIn("publication_authorized=false", worksheet)
            self.assertNotIn("api.x.com", worksheet)


if __name__ == "__main__":
    unittest.main()
