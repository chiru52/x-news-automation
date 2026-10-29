"""Offline checks for Stage 21 private Copilot X-draft editorial quality."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsbot.copilot_review import evaluate_review, render_summary, make_prompt
from newsbot.ai_drafts import suggested_clean_draft, save_private_review


URL = "https://www.thesaasnews.com/news/hyperbolic-raises-30m-series-a-1"
QUEUE = {
    "preview_only": True,
    "publishing_enabled": False,
    "articles": [{
        "title": "Hyperbolic Raises $30M Series A-1",
        "summary": "Unverified RSS summary only.",
        "link": URL,
        "source": "The SaaS News",
        "category": "saas",
        "published_at": "2026-10-29T17:05:00+00:00",
        "publishable": False,
    }],
}
EVIDENCE = {
    "status": "extracted_unverified",
    "reason": None,
    "source_url": URL,
    "paragraphs": [
        {"id": "P1", "text": "Publisher paragraph about a funding announcement, "
                             "reported as a Series A-1 financing round."},
        {"id": "P2", "text": "A separate article paragraph about the publisher's "
                             "company background, not cited by the proposed insight."},
        {"id": "P3", "text": "The article discusses a possible network for reselling "
                             "unused computing capacity to new customers."},
        {"id": "P4", "text": "The publisher says the platform could extend beyond "
                             "GPU management to broader shared infrastructure."},
    ],
}
MODEL = (
    "VERIFICATION: NOT VERIFIED (one publisher source)\n"
    "EVIDENCE: Funding reported [P1]. Proposed resale [P3].\n"
    "WHY_IT_MATTERS: Marketplace extension [P3][P4].\n"
    "DRAFT: Hyperbolic reportedly plans a marketplace to resell unused compute "
    "[P3][P4] " + URL + "\n"
    "SOURCE: " + URL + "\n"
    "REVIEW_CHECKS: Confirm reported plans with company statement."
)


class DraftQualityTests(unittest.TestCase):
    def test_cited_excerpts_visible_and_uncited_paragraph_omitted(self):
        rendered = render_summary(QUEUE, 1, MODEL, EVIDENCE)
        self.assertIn("## Supporting publisher excerpts", rendered)
        for ref in ("**P1 — publisher excerpt:**", "**P3 — publisher excerpt:**",
                    "**P4 — publisher excerpt:**"):
            self.assertIn(ref, rendered)
        self.assertNotIn("**P2 — publisher excerpt:**", rendered)
        self.assertIn("Publisher paragraph about a funding announcement", rendered)
        self.assertIn("NOT independently corroborated", rendered)

    def test_citation_markers_removed_from_clean_post_only(self):
        rendered = render_summary(QUEUE, 1, MODEL, EVIDENCE)
        clean_section = rendered.split("## Clean proposed X post", 1)[1].split(
            "\n## ", 1)[0]
        self.assertIn(URL, clean_section)
        self.assertNotIn("[P3]", clean_section)
        self.assertNotIn("[P4]", clean_section)
        self.assertIn("**Approximate X length:**", clean_section)
        self.assertIn("[P3][P4]", rendered)  # raw Copilot analysis preserved
        self.assertIn("HUMAN FACT-CHECK REQUIRED", rendered)
        self.assertIn("publication_authorized=false", rendered)
        self.assertNotIn("Needs corrections:", rendered)
        self.assertEqual(suggested_clean_draft(rendered),
                         "Hyperbolic reportedly plans a marketplace to resell unused compute " + URL)

    def test_missing_source_and_citation_are_flagged(self):
        modified = MODEL.replace("[P1]", "").replace("[P3]", "").replace("[P4]", "")
        modified = modified.replace("SOURCE: " + URL, "SOURCE: https://example.com/wrong")
        output = render_summary(QUEUE, 1, modified, EVIDENCE)
        self.assertIn("evidence claims lack publisher paragraph references", output)
        self.assertIn("SOURCE field does not match", output)
        self.assertIn("Needs corrections:", output)
        self.assertIn("HUMAN FACT-CHECK REQUIRED", output)

    def test_unknown_paragraph_id_is_flagged_even_if_stripped_from_copy(self):
        altered = MODEL.replace("[P3][P4] " + URL, "[P99] " + URL)
        output = render_summary(QUEUE, 1, altered, EVIDENCE)
        self.assertIn("unknown source paragraph citation", output)
        self.assertNotIn("[P99]", output.split("## Clean proposed X post", 1)[1].split(
            "\n## ", 1)[0])
        self.assertIn("[P99]", output)  # raw analysis displays warning evidence

    def test_unsafe_html_is_inert_in_editable_copy_and_excerpts(self):
        evidence = {**EVIDENCE, "paragraphs": [dict(p) for p in EVIDENCE["paragraphs"]]}
        evidence["paragraphs"][2]["text"] = "</pre><script>alert('pwn')</script>" + evidence["paragraphs"][2]["text"]
        output = MODEL.replace("Hyperbolic reportedly", "<script>alert('x')</script> Hyperbolic reportedly")
        rendered = render_summary(QUEUE, 1, output, evidence)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;/pre&gt;", rendered)

    def test_model_can_withhold_and_no_clean_draft_is_claimed(self):
        withheld = MODEL.split("DRAFT:", 1)[0] + "DRAFT: WITHHELD\nSOURCE: " + URL + "\nREVIEW_CHECKS: verify"
        rendered = render_summary(QUEUE, 1, withheld, EVIDENCE)
        self.assertIn("WITHHELD — no supported draft available", rendered)
        self.assertEqual(suggested_clean_draft(rendered), "")

    def test_x_overlength_detected_without_fake_fact_check(self):
        long = MODEL.replace("Hyperbolic reportedly plans a marketplace to resell unused compute", "Many words " * 40)
        checked = evaluate_review(QUEUE["articles"][0], long, EVIDENCE)
        self.assertIn("X length exceeds approximate limit", checked["issues"])
        self.assertGreater(checked["approximate_x_length"], 280)

    def test_prompt_requests_no_research_markers_in_draft(self):
        prompt = make_prompt(QUEUE, 1, EVIDENCE)
        self.assertIn("never place [P#] markers in DRAFT", prompt)
        self.assertIn("Do not submit, schedule, send, or post anything", prompt)

    @patch("newsbot.ai_drafts.run_gh")
    def test_issue_prefills_clean_copy_but_denies_posting(self, gh):
        gh.side_effect = [
            "true", "[]", "",
            "https://github.com/varadachiru/x-news-automation/issues/88",
        ]
        with tempfile.TemporaryDirectory() as d:
            body = Path(d) / "review.md"
            body.write_text(render_summary(QUEUE, 1, MODEL, EVIDENCE), encoding="utf-8")
            with patch.dict(os.environ, {"GH_TOKEN": "FAKE"}, clear=False):
                created = save_private_review("varadachiru/x-news-automation", "88", body)
            self.assertTrue(created.endswith("/issues/88"))
            stored = body.read_text()
            edited = stored.split("### My edited X post (manual only)", 1)[1]
            self.assertIn("Hyperbolic reportedly plans a marketplace", edited)
            self.assertNotIn("[P3]", edited)
            self.assertIn("Publication approval:** NOT GRANTED", edited)
            self.assertIn("Read article and corroborate material claims", stored)

    def test_workflow_still_requires_credit_approval_and_never_publishes(self):
        workflow = Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("inputs.approve_credit_use == true", workflow)
        self.assertIn("default: false", workflow)
        self.assertEqual(workflow.count("copilot -p "), 1)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertIn("needs.one-draft.outputs.draft_ready == 'true'", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("https://api.twitter.com", workflow)


if __name__ == "__main__":
    unittest.main()
