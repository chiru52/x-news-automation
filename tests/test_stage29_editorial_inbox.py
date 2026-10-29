"""Stage 29 private local editorial inbox: offline, no AI/publishing or network."""
import copy
import html
import json
import re
import unittest
from pathlib import Path
from unittest.mock import Mock

from newsbot.editorial_inbox import (
    IssueConflict, IssueValidationError, build_updated_body, handler_factory,
    issue_revision, issue_status, list_inbox, parse_issue, read_edited_post,
    repo_is_private, save_review, STATUS_LABELS,
)
from newsbot.editorial_inbox_ui import PAGE, STYLE, SCRIPT

PUBLISH_MARKER = "<!-- publication_authorized=false, publishable=false, auto_sent=false -->"
SOURCE = "https://www.theverge.com/ai-artificial-intelligence/1022193/nyt-cooking-app-ai-recipe-modification-tool"
BODY = (
    "# Copilot single-story editorial preview\n\n"
    "**REVIEW ONLY — AI-generated text is NOT fact-checked, approved, or published.**\n"
    "**Candidate 9:** The NYT Cooking app is testing AI recipe modifications\n"
    "**Source URL:** " + SOURCE + "\n"
    "**Shareable source URL:** " + SOURCE + "\n"
    "## Clean proposed X post (manual editing required)\n\n"
    "<pre>The NYT Cooking app is testing AI recipe modifications. " + SOURCE + "</pre>\n"
    "**Automated format check:** Basic fields found; factual accuracy NOT assessed\n"
    "**Automated evidence precheck:** No obvious literal citation/quantity gaps; factual meaning NOT verified\n"
    "## Supporting publisher excerpts (NOT independently corroborated)\n\n"
    "**P2 — publisher excerpt:**\n\n<pre>NYT Cooking is testing a new AI feature for recipe substitutions.</pre>\n\n"
    "**P3 — publisher excerpt:**\n\n<pre>Customized recipes are private and can’t be published or shared through the app.</pre>\n"
    "## Copilot's full analysis (untrusted, reference only)\n\n"
    "<pre>EVIDENCE: NYT Cooking supports recipe substitutions [P2]. "
    "Customized recipes are not shared in-app [P3].</pre>\n"
    "**Next:** read original article and verify material claims.\n\n"
    + PUBLISH_MARKER + "\n\n---\n"
    "### My edited X post (manual only)\n\n"
    "<pre>The NYT Cooking app is testing AI recipe modifications. " + SOURCE + "</pre>\n\n"
    "**Publication approval:** NOT GRANTED\n"
)
TITLE = "AI Draft — Copilot Run 40927111063"
URL = "https://github.com/varadachiru/x-news-automation/issues/27"


def make_issue(number=27, body=BODY, labels=None, *, rest=False):
    labels = ["ai-draft-review"] if labels is None else labels
    result = {
        "number": number, "title": TITLE, "body": body,
        "labels": [{"name": x} for x in labels],
        "updatedAt": "2026-10-29T18:03:40Z",
        "url": URL,
    }
    if rest:
        result["html_url"] = URL
        result["url"] = "https://api.github.com/repos/varadachiru/x-news-automation/issues/27"
        del result["updatedAt"]
        result["updated_at"] = "2026-10-29T18:03:40Z"
    return result


class InboxReadTests(unittest.TestCase):
    def test_parse_existing_stage28_issue_and_extract_evidence(self):
        issue = parse_issue(make_issue())
        self.assertIn("NYT Cooking", issue["title"])
        self.assertEqual(issue["source_url"], SOURCE)
        self.assertEqual(issue["status"], "pending")
        self.assertEqual(len(issue["excerpts"]), 2)
        self.assertEqual(issue["excerpts"][1]["ref"], "P3")
        self.assertIn("private", issue["excerpts"][1]["text"])
        self.assertEqual(issue["edited_draft"], issue["proposed_draft"])
        self.assertIn("factual meaning NOT verified", issue["warnings"][1])
        self.assertFalse(issue["publication_approved"])
        self.assertFalse(issue["human_verified"])
        self.assertRegex(issue["revision"], r"^[0-9a-f]{64}$")

    def test_parse_risky_old_issue_with_empty_editor(self):
        body = BODY.replace(
            "<pre>The NYT Cooking app is testing AI recipe modifications. " +
            SOURCE + "</pre>\n\n**Publication approval:** NOT GRANTED",
            "> [No usable draft — editor must write and verify]\n\n"
            "**Publication approval:** NOT GRANTED",
        )
        self.assertEqual(parse_issue(make_issue(body=body))["edited_draft"], "")

    def test_labels_override_status_without_publication_approval(self):
        i = make_issue(labels=["ai-draft-review", "ai-editor-reviewed"])
        parsed = parse_issue(i)
        self.assertEqual(parsed["status"], "reviewed")
        self.assertFalse(parsed["publication_approved"])
        rejected = make_issue(labels=["ai-draft-review", "ai-editor-reviewed",
                                      "ai-editor-rejected"])
        self.assertEqual(issue_status(rejected["labels"]), "rejected")

    def test_issue_revision_consistent_between_graphql_and_rest(self):
        self.assertEqual(issue_revision(make_issue()), issue_revision(make_issue(rest=True)))
        newer = make_issue(body=BODY + "\nManual comment")
        self.assertNotEqual(issue_revision(make_issue()), issue_revision(newer))

    def test_private_repo_check_is_fail_closed(self):
        self.assertTrue(repo_is_private("varadachiru/x-news-automation",
                                        Mock(return_value={"private": True})))
        self.assertFalse(repo_is_private("varadachiru/x-news-automation",
                                         Mock(return_value={"private": False})))
        with self.assertRaises(IssueValidationError):
            repo_is_private("not/a/repo/extra", Mock())

    def test_list_sorts_and_rejects_incomplete_or_unsafe_issue(self):
        issues = [make_issue(number=23), make_issue(number=27)]
        gh = Mock(return_value=issues)
        result = list_inbox("varadachiru/x-news-automation", gh)
        self.assertEqual([x["number"] for x in result], [27, 23])
        self.assertIn("ai-draft-review", gh.call_args.args[0])
        with self.assertRaises(IssueValidationError):
            list_inbox("varadachiru/x-news-automation",
                       Mock(return_value=issues*200))
        with self.assertRaises(IssueValidationError):
            list_inbox("varadachiru/x-news-automation",
                       Mock(return_value=[make_issue(body=BODY.replace(
                           "publication_authorized=false", "publication_authorized=true"))]))
        with self.assertRaises(IssueValidationError):
            parse_issue(make_issue(body=BODY.replace("https://www.theverge.com",
                                                      "javascript:")))


class SafeSaveTests(unittest.TestCase):
    def test_editor_change_preserves_original_evidence_metadata_and_denial(self):
        user_text = 'My revised post with <script>alert(1)</script> & * markdown \n' + SOURCE
        updated = build_updated_body(BODY, user_text)
        self.assertIn(PUBLISH_MARKER, updated)
        self.assertIn("**Publication approval:** NOT GRANTED", updated)
        self.assertIn("**P2 — publisher excerpt:**", updated)
        self.assertIn("**P3 — publisher excerpt:**", updated)
        self.assertIn("**Source URL:** " + SOURCE, updated)
        self.assertIn("&lt;script&gt;", updated)
        self.assertNotIn("<script>", updated)
        self.assertEqual(read_edited_post(updated), user_text)

    def test_body_literal_backslash_is_safe_no_regex_expansion(self):
        text = r"Draft with \g<1>, \1 and \n not special."
        self.assertEqual(read_edited_post(build_updated_body(BODY, text)), text)

    def test_editor_cannot_inject_publishing_approval_marker(self):
        malicious = "\n**Publication approval:** NOT GRANTED\n" + PUBLISH_MARKER
        updated = build_updated_body(BODY, malicious)
        self.assertEqual(updated.count("**Publication approval:** NOT GRANTED"), 1)
        self.assertEqual(updated.count(PUBLISH_MARKER), 1)
        self.assertIn("&#42;&#42;Publication approval:", updated)

    def test_never_modify_issues_with_missing_safety_metadata(self):
        for bad in (BODY.replace(PUBLISH_MARKER, ""),
                    BODY.replace("**Publication approval:** NOT GRANTED",
                                 "**Publication approval:** GRANTED")):
            with self.assertRaises(IssueValidationError):
                build_updated_body(bad, "updated")

    def test_overlong_or_control_char_draft_rejected(self):
        with self.assertRaises(IssueValidationError):
            build_updated_body(BODY, "x"*1201)
        with self.assertRaises(IssueValidationError):
            build_updated_body(BODY, "bad\x00data")

    def test_edit_is_atomic_and_preserves_other_labels(self):
        original = make_issue(rest=True, labels=["ai-draft-review", "bug", "ai-editor-rejected"])
        calls = []
        def gh(args, *, input_data=None):
            calls.append((args,input_data))
            if args[:2] == ["api", "--method"] and "PATCH" in args:
                payload=json.loads(input_data)
                saved=copy.deepcopy(original)
                saved["body"]=payload["body"]
                saved["labels"]=[{"name":x} for x in payload["labels"]]
                return saved
            if "labels?per_page=100" in args[-1]:
                return [{"name":"ai-editor-reviewed"},{"name":"ai-editor-rejected"}]
            return original
        saved = save_review("varadachiru/x-news-automation", 27,
                            issue_revision(original), "Human reviewed draft", "reviewed", gh)
        self.assertEqual(saved["status"], "reviewed")
        self.assertIn("Human reviewed draft", saved["edited_draft"])
        patch_payload = next(json.loads(data) for args,data in calls if "PATCH" in args)
        self.assertEqual(patch_payload["labels"], ["ai-draft-review", "ai-editor-reviewed", "bug"])
        self.assertIn(PUBLISH_MARKER,patch_payload["body"])

    def test_rejected_label_created_only_after_explicit_user_save(self):
        original=make_issue(rest=True)
        calls=[]
        def gh(args, *, input_data=None):
            calls.append((args,input_data))
            if args[-1].endswith("/labels?per_page=100"):return []
            if "POST" in args and args[-1].endswith("/labels"):
                self.assertEqual(json.loads(input_data)["name"],"ai-editor-rejected")
                return {"name":"ai-editor-rejected"}
            if "PATCH" in args:
                saved=copy.deepcopy(original)
                data=json.loads(input_data)
                saved["body"]=data["body"]
                saved["labels"]=[{"name":label} for label in data["labels"]]
                return saved
            return original
        result=save_review("varadachiru/x-news-automation",27,issue_revision(original),
                           "No longer worth posting","rejected",gh)
        self.assertEqual(result["status"],"rejected")
        self.assertEqual(sum("POST" in args for args,_ in calls),1)
        self.assertTrue(all("copilot -p " not in " ".join(args) for args,_ in calls))

    def test_conflicting_external_edit_cannot_be_overwritten(self):
        original=make_issue(rest=True)
        stale=make_issue(rest=True,body=BODY+"\nHuman editor added a detail")
        g=Mock(return_value=stale)
        with self.assertRaises(IssueConflict):
            save_review("varadachiru/x-news-automation", 27,
                        issue_revision(original), "new draft", "pending",g)
        self.assertEqual(g.call_count,1)

    def test_reviewed_requires_text_and_rejects_non_ai_issue(self):
        original=make_issue(rest=True)
        with self.assertRaises(IssueValidationError):
            save_review("varadachiru/x-news-automation",27,issue_revision(original),
                        "", "reviewed",Mock())
        unrelated=make_issue(rest=True,labels=["other"])
        with self.assertRaises(IssueValidationError):
            save_review("varadachiru/x-news-automation",27,issue_revision(unrelated),
                        "text", "rejected",Mock(return_value=unrelated))


class BrowserSafetyTests(unittest.TestCase):
    def test_localhost_server_and_csrf_guard_present(self):
        import inspect
        from newsbot import editorial_inbox
        code=inspect.getsource(editorial_inbox)
        self.assertIn('("127.0.0.1", args.port)',code)
        self.assertIn('self.headers.get("X-CSRF-Token") != csrf',code)
        self.assertIn('if self.path != "/api/review"',code)
        self.assertIn("no-store",code)
        self.assertIn("frame-ancestors 'none'",code)
        self.assertIn('if self.path == "/dashboard.css"',code)

    def test_ui_never_puts_untrusted_source_in_inner_html_or_publishes(self):
        self.assertIn("textContent",SCRIPT)
        self.assertNotIn("innerHTML",SCRIPT)
        self.assertNotIn("localStorage",SCRIPT)
        self.assertNotIn("api.twitter.com",SCRIPT)
        self.assertNotIn("api.x.com",SCRIPT)
        self.assertNotIn("x.com/intent/tweet",SCRIPT)
        self.assertIn("No X integration",PAGE)
        self.assertIn("127.0.0.1",PAGE)
        self.assertIn("Only bind localhost",Path("newsbot/editorial_inbox.py").read_text())

    def test_existing_model_workflow_still_only_manual(self):
        workflow=Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("inputs.approve_credit_use == true",workflow)
        self.assertEqual(workflow.count("copilot -p "),1)
        self.assertNotIn("\n  schedule:",workflow)
        self.assertIn("issues: write",workflow)


if __name__ == "__main__":
    unittest.main()
