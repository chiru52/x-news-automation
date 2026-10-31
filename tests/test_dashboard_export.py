"""Offline dashboard export tests; no Cloudflare, X, Copilot, or network."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from newsbot.dashboard_export import (
    build_bundle, categorize, clean, read_drafts, read_news, source_url,
    fetch_private_issues, validate_public_bundle, REPO,
)

SOURCE = "https://publisher.example/story"
BODY = (
    "# Copilot private editorial preview\n"
    "**REVIEW ONLY — AI-generated, unverified.**\n"
    "**Candidate 3:** A new AI service is being tested\n"
    "**Source URL:** " + SOURCE + "\n"
    "## Clean proposed X post (manual editing required)\n\n"
    "<pre>Unverified first look. " + SOURCE + "</pre>\n"
    "<!-- publication_authorized=false, publishable=false, auto_sent=false -->\n"
    "### My edited X post (manual only)\n\n"
    "<pre>Human edited &amp; sourced: " + SOURCE + "</pre>\n\n"
    "**Publication approval:** NOT GRANTED\n"
)


def issue(number=27, body=BODY, labels=None):
    return {
        "number": number, "title": "AI Draft — test",
        "body": body, "labels": [{"name": name} for name in (labels or ["ai-draft-review"])],
        "updated_at": "2026-10-30T05:00:00Z",
        "html_url": "https://github.com/varadachiru/x-news-automation/issues/27",
    }


def queue():
    return {
        "generated_at": "2026-10-30T05:00:00Z", "publishing_enabled": False,
        "articles": [
            {"title": "SaaS company announces a new feature",
             "link": SOURCE, "source": "Publisher",
             "summary": "<script>Untrusted text</script> (rendered as plain text)",
             "suggested_post": "New features reviewed: " + SOURCE,
             "category": "saas", "publishable": False,
             "published_at": "2026-10-30T04:30:00Z"},
        ], "feed_errors": [],
    }


class DashboardExportTests(unittest.TestCase):
    def test_queue_export_and_categorization(self):
        result = read_news(queue())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "saas")
        self.assertEqual(result[0]["status"], "unverified")
        self.assertTrue(result[0]["id"])
        self.assertFalse(any("GH_TOKEN" in str(v) for v in result[0].values()))

    def test_news_export_removes_syndicated_repeats(self):
        q = queue()
        first = dict(q["articles"][0])
        another = dict(first)
        another["link"] = first["link"] + "?utm_source=another_feed"
        another["source"] = "Syndicated copy"
        third = dict(first)
        third["title"] = "Different story from the same newspaper"
        third["link"] = "https://publisher.example/other-story"
        q["articles"] = [first, another, third]
        export = read_news(q)
        self.assertEqual(len(export), 2)
        self.assertEqual(export[0]["publisher"], "Publisher")

    def test_export_repeated_ai_draft_prefers_newest_issue(self):
        high = issue(number=30)
        low = issue(number=12)
        drafts = read_drafts([low, high])
        self.assertEqual([d["id"] for d in drafts], ["30"])
        self.assertEqual(drafts[0]["status"], "pending")

    def test_private_issue_uses_only_safe_edited_text(self):
        result = read_drafts([issue()])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "27")
        self.assertIn("Human edited & sourced", result[0]["post"])
        self.assertNotIn("publication_authorized", json.dumps(result))
        self.assertNotIn("REVIEW ONLY", json.dumps(result))
        self.assertNotIn("<pre>", json.dumps(result))
        self.assertEqual(result[0]["status"], "pending")

    def test_rejected_ignored_reviewed_kept(self):
        rejected = issue(number=25, labels=["ai-draft-review", "ai-editor-rejected"])
        reviewed = issue(number=27, labels=["ai-draft-review", "ai-editor-reviewed"])
        result = read_drafts([rejected, reviewed])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "reviewed")

    def test_bad_issue_marker_fails_closed(self):
        bad = issue(body=BODY.replace("auto_sent=false", "auto_sent=true"))
        with self.assertRaises(ValueError):
            read_drafts([bad])

    def test_unknown_and_external_issues_ignored(self):
        generic = issue(labels=["unrelated"])
        pr = issue()
        pr["pull_request"] = {}
        self.assertEqual(read_drafts([generic, pr]), [])

    def test_unsafe_feed_and_bad_articles_fail_closed(self):
        q = queue()
        q["publishing_enabled"] = True
        with self.assertRaises(ValueError):
            read_news(q)
        q["publishing_enabled"] = False
        q["articles"][0]["publishable"] = True
        with self.assertRaises(ValueError):
            read_news(q)

    def test_validate_urls_and_text(self):
        for uri in ("javascript:alert(1)", "https://alice:secret@host/story",
                    "http://publisher.example/story", "https://bad host/story"):
            self.assertFalse(source_url(uri), uri)
        self.assertEqual(source_url(SOURCE), SOURCE)
        self.assertEqual(clean("one\x00two"), "one two")
        self.assertEqual(categorize("Startup lands seed round"), "saas")
        self.assertEqual(categorize("Stock market rally"), "markets")

    def test_bundle_contains_only_static_files_and_nonapproved_data(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "dist"
            result = build_bundle(queue(), [issue()], dest, generated_at="2026-10-30T06:00:00Z")
            self.assertEqual(result["schema_version"], 1)
            self.assertEqual(len(result["news"]), 1)
            self.assertEqual(len(result["drafts"]), 1)
            self.assertEqual(sorted(p.name for p in dest.iterdir()),
                             ["_headers", "account-visual.css", "account.html", "account.mjs", "app.js", "archive-client.mjs", "auth-config.json", "cloud-sync.mjs", "data.json", "feed-config.json", "index.html", "news-sections.mjs", "perspective.mjs", "refresh-clock.mjs", "review-desk.mjs", "studio.mjs", "styles.css", "workspace-transfer.mjs"])
            data = json.loads((dest / "data.json").read_text("utf-8"))
            self.assertNotIn("GH_TOKEN", json.dumps(data))
            self.assertNotIn("X_API", json.dumps(data))
            self.assertNotIn("publication_authorized=true", json.dumps(data))
            html = (dest / "index.html").read_text("utf-8")
            js = (dest / "app.js").read_text("utf-8")
            css = (dest / "styles.css").read_text("utf-8")
            self.assertIn("Copy post", html)
            self.assertIn("textContent", js)
            self.assertNotIn("innerHTML", js)
            self.assertNotIn("fonts.googleapis.com", css)
            self.assertNotIn("api.x.com", js)

    def test_public_feed_does_not_export_publisher_rss_excerpts(self):
        q = queue()
        q["articles"][0]["summary"] = "PRIVATE EVIDENCE DO NOT DISPLAY"
        exported = read_news(q)
        self.assertNotIn("PRIVATE EVIDENCE", json.dumps(exported))
        self.assertIn("Verify all claims", exported[0]["description"])

    def test_public_schema_blocks_private_issue_evidence_and_token_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            data = build_bundle(queue(), [issue()], Path(folder) / "public")
        data["drafts"][0]["evidence"] = "Raw publisher quotation"
        with self.assertRaises(ValueError):
            validate_public_bundle(data)
        data["drafts"][0].pop("evidence")
        for marker in ("github_pat_123456", "-----BEGIN PRIVATE KEY-----",
                       "## Supporting publisher excerpts", "<pre>raw original</pre>"):
            modified = json.loads(json.dumps(data))
            modified["drafts"][0]["post"] = marker
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    validate_public_bundle(modified)

    def test_public_schema_rejects_unsafe_status_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            data = build_bundle(queue(), [issue()], Path(folder) / "public")
        data["drafts"][0]["status"] = "rejected"
        with self.assertRaises(ValueError):
            validate_public_bundle(data)
        data["drafts"][0]["status"] = "pending"
        data["drafts"][0]["source_url"] = "http://example.com/"
        with self.assertRaises(ValueError):
            validate_public_bundle(data)

    def test_reject_export_into_asset_source(self):
        from newsbot.dashboard_export import ASSETS
        with self.assertRaises(ValueError):
            build_bundle(queue(), [], ASSETS)

    def test_no_github_read_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                fetch_private_issues()

    def test_workflow_publishes_only_sanitized_public_feed_not_to_x(self):
        text = (Path(__file__).resolve().parents[1] /
                ".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertIn("issues: read", text)
        self.assertNotIn("issues: write", text)
        self.assertIn("PUBLISH_ENABLED: 'false'", text)
        self.assertIn("validate_public_bundle(data)", text)
        self.assertIn("pages deploy dist/signaldesk", text)
        self.assertIn("--project-name=signaldesk-news", text)
        self.assertIn("secrets.CLOUDFLARE_API_TOKEN", text)
        self.assertIn("secrets.CLOUDFLARE_ACCOUNT_ID", text)
        self.assertNotIn("secrets.X_", text)
        self.assertNotIn("api.x.com", text)
        self.assertNotIn("copilot -p", text)


if __name__ == "__main__":
    unittest.main()
