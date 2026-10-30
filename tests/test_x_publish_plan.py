"""Stage 34: offline X approval-plan safety and replay tests."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsbot.x_preflight import PreflightBlocked
from newsbot.x_publish_plan import make_plan, check_request, render_plan, main

ROOT = Path(__file__).resolve().parents[1]
URL = "https://example.com/tech-news"
REPO = "varadachiru/x-news-automation"


def fixture(text=None, *, reviewed=True, rejected=False):
    labels = [{"name": "ai-draft-review"}]
    if reviewed:
        labels.append({"name": "ai-editor-reviewed"})
    if rejected:
        labels.append({"name": "ai-editor-rejected"})
    return {
        "number": 27,
        "labels": labels,
        "body": (
            "# Private draft\n"
            "**REVIEW ONLY — unverified AI content.**\n"
            f"**Source URL:** {URL}\n"
            "<!-- publication_authorized=false, publishable=false, auto_sent=false -->\n"
            "### My edited X post (manual only)\n\n"
            f"<pre>{text if text is not None else 'Editor verified the claim: ' + URL}</pre>\n\n"
            "**Publication approval:** NOT GRANTED\n"
        )
    }


class ApprovalPlanningTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_binds_handle(self):
        first = make_plan(fixture(), 27, "Example_Handle")
        second = make_plan(fixture(), 27, "example_handle")
        third = make_plan(fixture(), 27, "other_handle")
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertNotEqual(first["sha256"], third["sha256"])
        self.assertEqual(first["destination_handle_unverified"], "example_handle")
        self.assertFalse(first["publication_authorized"])
        self.assertFalse(first["send_enabled"])

    def test_edit_changes_digest_and_invalidates_previous_request(self):
        first = make_plan(fixture(), 27, "example")
        modified = make_plan(fixture("Updated, verified facts: " + URL), 27, "example")
        self.assertNotEqual(first["sha256"], modified["sha256"])
        with self.assertRaises(PreflightBlocked):
            check_request(modified, first["sha256"],
                          f"APPROVE X POST #27 @example {first['sha256']}", [])

    def test_rejected_or_pending_blocks(self):
        for issue in (fixture(reviewed=False), fixture(rejected=True)):
            with self.subTest(labels=issue["labels"]):
                with self.assertRaises(PreflightBlocked):
                    make_plan(issue, 27, "example")

    def test_invalid_account_blocked(self):
        for handle in ("@example", "with spaces", "longhandle_123456789", "", "my-handle"):
            with self.subTest(handle=handle):
                with self.assertRaises(PreflightBlocked):
                    make_plan(fixture(), 27, handle)

    def test_dedup_blocks_prior_attempts_including_unknown(self):
        p = make_plan(fixture(), 27, "example")
        phrase = f"APPROVE X POST #27 @example {p['sha256']}"
        for state in ("reserved", "unknown", "sent", "aborted"):
            with self.subTest(state=state):
                with self.assertRaises(PreflightBlocked):
                    check_request(p, p["sha256"], phrase, [
                        {"state": state, "issue_number": 27,
                         "destination_handle": "example", "sha256": p["sha256"]}
                    ])
        with self.assertRaises(PreflightBlocked):
            check_request(p, p["sha256"], phrase, [
                {"state": "unknown", "issue_number": 27,
                 "destination_handle": "example", "sha256": "0" * 64}
            ])

    def test_missing_history_blocks_and_malformed_history_blocks(self):
        p = make_plan(fixture(), 27, "example")
        phrase = f"APPROVE X POST #27 @example {p['sha256']}"
        for history in (None, {}, [None], [{"state": "mystery"}]):
            with self.subTest(history=history):
                with self.assertRaises(PreflightBlocked):
                    check_request(p, p["sha256"], phrase, history)

    def test_dry_precheck_not_publication_approval(self):
        p = make_plan(fixture(), 27, "example")
        phrase = f"APPROVE X POST #27 @example {p['sha256']}"
        self.assertTrue(check_request(p, p["sha256"], phrase, []))
        # This is a pure prerequisite only: no durable reservation is created
        # and no posting API client exists in this workflow or module.
        self.assertFalse(p["publication_authorized"])
        self.assertFalse(p["send_enabled"])
        for wrong in ("", phrase.lower(), phrase + " ", "APPROVE X POST #27"):
            with self.assertRaises(PreflightBlocked):
                check_request(p, p["sha256"], wrong, [])

    def test_digest_or_flag_tamper_fails(self):
        p = make_plan(fixture(), 27, "example")
        phrase = f"APPROVE X POST #27 @example {p['sha256']}"
        for field, value in (("send_enabled", True), ("publication_authorized", True),
                             ("sha256", "wrong"), ("text", "tampered"),
                             ("destination_handle_unverified", "another_account")):
            corrupted = dict(p)
            corrupted[field] = value
            with self.subTest(field=field):
                with self.assertRaises(PreflightBlocked):
                    check_request(corrupted, p["sha256"], phrase, [])

    def test_summary_clearly_avoids_approval_and_sending(self):
        p = make_plan(fixture(), 27, "example")
        s = render_plan(p)
        self.assertIn("NO POST SENT", s)
        self.assertIn("NOT authenticated", s)
        self.assertIn("atomic", s)
        self.assertIn(p["sha256"], s)
        self.assertIn(URL, s)

    def test_cli_uses_read_only_issue_and_saves_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = str(Path(folder) / "summary.md")
            with patch.dict(os.environ, {
                "GITHUB_REPOSITORY": REPO,
                "GH_TOKEN": "fake",
                "ISSUE_NUMBER": "27",
                "DESTINATION_HANDLE": "example",
                "GITHUB_STEP_SUMMARY": summary}, clear=True):
                with patch("newsbot.x_publish_plan.github_json",
                           side_effect=[{"private": True, "full_name": REPO},
                                        fixture()]) as gh:
                    self.assertEqual(main(), 0)
                    self.assertEqual(gh.call_count, 2)
                    self.assertIn("NO POST SENT", Path(summary).read_text("utf-8"))

    def test_cli_rejects_input_without_network(self):
        with patch.dict(os.environ, {
                "GITHUB_REPOSITORY": REPO, "GH_TOKEN": "fake",
                "ISSUE_NUMBER": "27;true", "DESTINATION_HANDLE": "example"},
                clear=True):
            with patch("newsbot.x_publish_plan.github_json") as gh:
                self.assertEqual(main(), 1)
                gh.assert_not_called()

    def test_workflow_is_manual_read_only_without_secrets(self):
        yml = (ROOT / ".github/workflows/x-publish-plan.yml").read_text("utf-8")
        py = (ROOT / "newsbot/x_publish_plan.py").read_text("utf-8")
        self.assertIn("workflow_dispatch:", yml)
        self.assertNotIn("schedule:", yml)
        self.assertNotIn("pull_request:", yml)
        self.assertNotIn("  issues: write", yml)
        self.assertNotIn("secrets.", yml)
        self.assertIn("PUBLISH_ENABLED: 'false'", yml)
        self.assertNotIn("api.x.com", yml)
        self.assertNotIn("api.x.com", py)
        self.assertNotIn("requests.post(", py)


if __name__ == "__main__":
    unittest.main()
