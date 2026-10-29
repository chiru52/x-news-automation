"""Offline tests for structured publisher extraction and private AI Draft Issues."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from newsbot.source_research import (
    extract_paragraphs, fetch_evidence, MAX_HTML_BYTES, MAX_EXCERPT_CHARS,
)
from newsbot.ai_drafts import save_private_review, LABEL


URL = "https://finance.yahoo.com/news/ai-example"
BODY = (
    "The publisher describes a new research report on technology company software revenues, "
    "including conditions behind the quarterly change. "
    "The report lists enterprise demand as a driver for higher spending in selected categories. "
    "It says investment is focused on services and infrastructure rather than consumer advertising. "
    "Analysts quoted in the report describe uncertainty about future growth as conditions evolve. "
    "Executives expect customers to evaluate costs before making new long-term software purchases. "
    "The research highlights how subscription spending is shifting across different enterprise teams. "
)
JSONLD = json.dumps({
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebPage", "name": "Research update"},
        {"@type": "NewsArticle", "headline": "New research report",
         "articleBody": BODY},
    ],
})
PAGE = ("<html><head><script type='application/ld+json'>" + JSONLD +
        "</script></head><body><main><p>Short intro.</p></main></body></html>").encode()


class FakePage:
    def __init__(self, content=PAGE, url=URL, content_type="text/html"):
        self.data = io.BytesIO(content)
        self.url = url
        self.headers = {"Content-Type": content_type}
    def read(self, amount):
        return self.data.read(amount)
    def geturl(self):
        return self.url
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.data.close()


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []
    def open(self, req, timeout):
        self.seen.append(req.full_url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class StructuredExtractionTests(unittest.TestCase):
    def test_newsarticle_jsonld_paragraphs_extracted(self):
        snippets = extract_paragraphs(PAGE)
        self.assertGreaterEqual(len(snippets), 2)
        self.assertEqual(snippets[0]["id"], "P1")
        self.assertIn("publisher describes", snippets[0]["text"])
        self.assertLessEqual(sum(len(x["text"]) for x in snippets), MAX_EXCERPT_CHARS)

    def test_jsonld_inert_does_not_execute_or_accept_generic_json(self):
        snippets = extract_paragraphs(
            b'<script type="application/ld+json">' +
            b'{"@type": "WebPage", "articleBody": "not a publisher story"}' +
            b'</script><script>throw new Error("inert")</script>'
        )
        self.assertEqual(snippets, [])

    def test_same_host_https_canonical_redirect_can_succeed(self):
        redirect = HTTPError(URL, 301, "Moved", {"Location": "/news/canonical"}, None)
        canonical = "https://finance.yahoo.com/news/canonical"
        client = FakeOpener([redirect, FakePage(url=canonical)])
        r = fetch_evidence(URL, opener=client, dns_check=lambda host: None)
        self.assertEqual(r["status"], "extracted_unverified")
        self.assertEqual(r["source_url"], URL)
        self.assertEqual(client.seen, [URL, canonical])

    def test_cross_host_redirect_never_follows(self):
        redirect = HTTPError(URL, 301, "Moved",
                             {"Location": "https://private.example/secret"}, None)
        client = FakeOpener([redirect])
        r = fetch_evidence(URL, opener=client, dns_check=lambda host: None)
        self.assertEqual(r["reason"], "redirect_blocked")
        self.assertEqual(client.seen, [URL])

    def test_oversize_html_rejected(self):
        client = FakeOpener([FakePage(content=PAGE + b" "*(MAX_HTML_BYTES+10))])
        r = fetch_evidence(URL, opener=client, dns_check=lambda host: None)
        self.assertEqual(r["reason"], "too_large")

    def test_invalid_jsonld_falls_back_without_ai(self):
        r = fetch_evidence(URL, opener=FakeOpener([FakePage(
            content=b'<script type="application/ld+json">{bad}</script>'
        )]), dns_check=lambda host: None)
        self.assertEqual(r["reason"], "no_reliable_article_text")


DRAFT = ("# Copilot single-story editorial preview\n\n"
         "**REVIEW ONLY — AI-generated text is NOT fact-checked, approved, or published.**\n\n"
         "<pre>VERIFICATION: NOT VERIFIED\nDRAFT: Example (unverified)</pre>\n\n"
         "<!-- publication_authorized=false, publishable=false, auto_sent=false -->\n")


class PrivateAiDraftsTests(unittest.TestCase):
    def make_file(self, content=DRAFT):
        tmp = tempfile.TemporaryDirectory()
        file = Path(tmp.name) / "copilot-review.md"
        file.write_text(content, encoding="utf-8")
        return tmp, file

    @patch("newsbot.ai_drafts.run_gh")
    def test_private_draft_creates_labeled_issue(self, gh):
        gh.side_effect = ["true", "[]", "", "https://github.com/varadachiru/x-news-automation/issues/42"]
        tmp, file = self.make_file()
        try:
            with patch.dict(os.environ, {"GH_TOKEN": "DUMMY"}):
                url = save_private_review("varadachiru/x-news-automation", "12345", file)
            self.assertEqual(url, "https://github.com/varadachiru/x-news-automation/issues/42")
            args = [x.args[0] for x in gh.call_args_list]
            self.assertTrue(any(x[:2] == ["label", "create"] for x in args))
            self.assertTrue(any(x[:2] == ["issue", "create"] and LABEL in x for x in args))
            self.assertIn("Publication approval:** NOT GRANTED", file.read_text())
        finally:
            tmp.cleanup()

    @patch("newsbot.ai_drafts.run_gh")
    def test_existing_issue_is_reused_without_editing(self, gh):
        gh.side_effect = ["true", json.dumps([{
            "title": "AI Draft — Copilot Run 10",
            "url": "https://github.com/varadachiru/x-news-automation/issues/5"}])]
        tmp, file = self.make_file()
        try:
            original = file.read_bytes()
            with patch.dict(os.environ, {"GH_TOKEN": "DUMMY"}):
                url = save_private_review("varadachiru/x-news-automation", "10", file)
            self.assertTrue(url.endswith("/issues/5"))
            self.assertEqual(file.read_bytes(), original)
            self.assertEqual(gh.call_count, 2)
        finally:
            tmp.cleanup()

    @patch("newsbot.ai_drafts.run_gh")
    def test_public_repo_refused_and_no_issue_created(self, gh):
        gh.return_value = "false"
        tmp, file = self.make_file()
        try:
            with patch.dict(os.environ, {"GH_TOKEN": "DUMMY"}):
                with self.assertRaises(ValueError):
                    save_private_review("varadachiru/x-news-automation", "123", file)
            self.assertEqual(gh.call_count, 1)
        finally:
            tmp.cleanup()

    @patch("newsbot.ai_drafts.run_gh")
    def test_unsafe_draft_and_repo_rejected(self, gh):
        tmp, file = self.make_file("draft without safety marker")
        try:
            with patch.dict(os.environ, {"GH_TOKEN": "DUMMY"}):
                with self.assertRaises(ValueError):
                    save_private_review("varadachiru/x-news-automation", "1", file)
                with self.assertRaises(ValueError):
                    save_private_review("unknown/../../repo", "1", file)
            gh.assert_not_called()
        finally:
            tmp.cleanup()

    def test_workflow_credit_gate_and_private_issue_permission(self):
        text = Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("inputs.approve_credit_use == true", text)
        self.assertIn("needs.one-draft.outputs.draft_ready == 'true'", text)
        self.assertIn("      issues: write", text)
        self.assertIn("  copilot-requests: write", text)
        self.assertEqual(text.count("copilot -p "), 1)
        self.assertNotIn("\n  schedule:", text)


if __name__ == "__main__":
    unittest.main()
