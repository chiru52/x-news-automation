"""Offline safety checks for the read-only GitHub->X editorial preflight."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from newsbot.x_preflight import PreflightBlocked, validate_issue, render, main

ROOT = Path(__file__).resolve().parents[1]
URL = "https://publisher.example/news"


def make_issue(*, reviewed=True, rejected=False, number=27):
    labels = [{"name": "ai-draft-review"}]
    if reviewed:
        labels.append({"name": "ai-editor-reviewed"})
    if rejected:
        labels.append({"name": "ai-editor-rejected"})
    return {
        "number": number, "labels": labels,
        "body": (
            "# Editorial review\n"
            "**REVIEW ONLY — NOT fact checked.**\n"
            f"**Source URL:** {URL}\n"
            "## Clean proposed X post (manual editing required)\n"
            "<pre>Unverified suggestion</pre>\n"
            "<!-- publication_authorized=false, publishable=false, auto_sent=false -->\n"
            "### My edited X post (manual only)\n\n"
            f"<pre>Verified headline and original source: {URL}</pre>\n\n"
            "**Publication approval:** NOT GRANTED\n"
        )
    }


class XPreflightTests(unittest.TestCase):
    def test_reviewed_draft_previews_without_authorization(self):
        result = validate_issue(make_issue(), 27)
        self.assertFalse(result["publication_authorized"])
        self.assertIn(URL, result["draft"])
        self.assertIn("NOT PUBLISHED", render(result))
        self.assertIn("NOT approved", render(result))

    def test_pending_or_rejected_blocked(self):
        for issue in (make_issue(reviewed=False), make_issue(rejected=True)):
            with self.assertRaises(PreflightBlocked):
                validate_issue(issue, 27)

    def test_other_issue_or_pull_request_blocked(self):
        with self.assertRaises(PreflightBlocked):
            validate_issue(make_issue(), 28)
        issue = make_issue()
        issue["pull_request"] = {"url": "https://example.com"}
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_missing_draft_label_blocked(self):
        issue = make_issue()
        issue["labels"] = [{"name": "ai-editor-reviewed"}]
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_non_publication_markers_mandatory(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace("auto_sent=false", "auto_sent=true")
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_publication_denial_mandatory(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace("NOT GRANTED", "GRANTED")
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_empty_editor_block_fails(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace(
            f"<pre>Verified headline and original source: {URL}</pre>",
            "> [No reviewed post]")
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_280_character_conservative_limit(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace(
            f"Verified headline and original source: {URL}",
            "x" * 280 + " " + URL)
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_source_link_is_required(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace(
            f"Verified headline and original source: {URL}",
            "No link included")
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_unsafe_source_link_is_blocked(self):
        issue = make_issue()
        issue["body"] = issue["body"].replace(URL, "https://user:password@host/news")
        with self.assertRaises(PreflightBlocked):
            validate_issue(issue, 27)

    def test_editor_html_unescaping_and_markdown_fence(self):
        issue = make_issue()
        backticks = chr(96) * 3
        issue["body"] = issue["body"].replace(
            f"Verified headline and original source: {URL}",
            f"Verified &amp; sourced {backticks} {URL}")
        result = validate_issue(issue, 27)
        self.assertIn("Verified & sourced", result["draft"])
        self.assertIn(chr(96) * 4 + "text", render(result))

    def test_cli_rejects_bad_input_without_calling_github(self):
        with patch.dict(os.environ, {
                "ISSUE_NUMBER": "1; echo sneaky",
                "GITHUB_REPOSITORY": "varadachiru/x-news-automation",
                "GH_TOKEN": "fake"}, clear=True):
            with patch("newsbot.x_preflight.github_json") as gh:
                self.assertEqual(main(), 1)
                gh.assert_not_called()

    def test_cli_rejects_public_repo_even_if_issue_reviewed(self):
        with patch.dict(os.environ, {
                "ISSUE_NUMBER": "27",
                "GITHUB_REPOSITORY": "varadachiru/x-news-automation",
                "GH_TOKEN": "fake"}, clear=True):
            with patch("newsbot.x_preflight.github_json",
                       return_value={"private": False, "full_name":
                                     "varadachiru/x-news-automation"}) as gh:
                self.assertEqual(main(), 1)
                self.assertEqual(gh.call_count, 1)

    def test_workflow_never_writes_or_publishes(self):
        text = (ROOT / ".github/workflows/x-post-preflight.yml").read_text("utf-8")
        module = (ROOT / "newsbot/x_preflight.py").read_text("utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("pull_request:", text)
        self.assertIn("issues: read", text)
        self.assertNotIn("issues: write", text)
        self.assertNotIn("secrets.", text)
        self.assertIn("PUBLISH_ENABLED: 'false'", text)
        self.assertNotIn("https://api.x.com", module)
        self.assertNotIn("requests.post(", module)


if __name__ == "__main__":
    unittest.main()
