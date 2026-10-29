"""Stage 27: editorial evidence prechecks are useful but NOT fact-checking."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from newsbot.evidence_audit import (audit_model_evidence, claim_units,
                                    focused_excerpt, quantities)
from newsbot.copilot_review import evaluate_review, make_prompt, render_summary
from newsbot.ai_drafts import save_private_review, suggested_clean_draft


URL = "https://www.theverge.com/tech/1022023/microsoft-exit-offer-layoffs-notepad"
QUEUE = {
    "publishing_enabled": False, "preview_only": True,
    "articles": [{
        "link": URL, "title": "Microsoft's AI future has fewer jobs",
        "publishable": False, "source": "The Verge",
        "summary": "Single RSS source. Not independently verified.",
        "published_at": "2026-10-29T17:48:00+00:00",
        "category": "technology",
    }],
}
LONG = ("Microsoft's CEO discussed AI infrastructure investments and possible "
        "workforce changes in public remarks. " * 3)
PARAGRAPHS = [
    {"id": "P1", "text": "Microsoft discussed the offer of voluntary buyouts to "
                              "around 60,000 eligible workers in several regions."},
    {"id": "P2", "text": "Microsoft CEO Satya Nadella argued that AI will change "
                              "the technology workforce over the next few years. " + LONG},
    {"id": "P3", "text": "The program is intended to reduce operating costs while "
                              "the firm maintains AI infrastructure spending."},
]
EVIDENCE = {
    "status": "extracted_unverified", "reason": None,
    "source_url": URL, "paragraphs": PARAGRAPHS,
}
MODEL_GOOD = (
    "VERIFICATION: NOT VERIFIED (one publisher source)\n"
    "EVIDENCE: Microsoft reportedly offered voluntary buyouts to 60,000 "
    "eligible employees [P1]. The company plans continued AI investment [P3].\n"
    "WHY_IT_MATTERS: AI infrastructure investment may coincide with cost cuts [P3].\n"
    "DRAFT: Microsoft reportedly offered voluntary buyouts to 60,000 eligible workers "
    "while maintaining AI infrastructure investment. " + URL + "\n"
    "SOURCE: " + URL + "\n"
    "REVIEW_CHECKS: Confirm employees eligible, geographic reach and management rationale."
)
MODEL_WRONG = MODEL_GOOD.replace("employees [P1]", "employees [P2]")


class NumericEvidenceTests(unittest.TestCase):
    def test_normalize_numbers_with_thousands_and_percent(self):
        self.assertEqual(quantities("around 60,000 people, 60K more"), {"60000"})
        self.assertEqual(quantities("$30 million; 30M; 11.7%"), {"30000000", "11.7%"})
        self.assertEqual(quantities("Q3 earnings https://example.com/1022023 [P2]"), set())
        self.assertNotEqual(quantities("11.7%"), quantities("11.7"))

    def test_numeric_claim_referenced_to_wrong_paragraph_is_flagged(self):
        fields = {
            "EVIDENCE": "Microsoft offered buyouts to around 60,000 workers [P2].",
            "WHY_IT_MATTERS": "Some context [P3].",
            "DRAFT": "Microsoft offered buyouts to 60,000 workers. " + URL,
        }
        report = audit_model_evidence(fields, PARAGRAPHS)
        self.assertEqual(report["status"], "needs_attention")
        self.assertFalse(report["verified"])
        self.assertTrue(any("EVIDENCE quantity 60000" in issue and "P2" in issue
                            for issue in report["flags"]))
        self.assertTrue(any("DRAFT quantity 60000" in issue
                            for issue in report["flags"]))

    def test_numeric_in_correct_cited_paragraph_passes_limited_check(self):
        fields = {
            "EVIDENCE": "Reported around 60K workers eligible [P1].",
            "WHY_IT_MATTERS": "Ongoing AI infrastructure spending [P3].",
            "DRAFT": "Microsoft reportedly offers buyouts to 60,000 eligible workers. " + URL,
        }
        report = audit_model_evidence(fields, PARAGRAPHS)
        self.assertEqual(report["flags"], [])
        self.assertEqual(report["status"], "limited_precheck_only")
        self.assertFalse(report["verified"])

    def test_claim_without_any_citation_is_flagged(self):
        fields = {
            "EVIDENCE": "Microsoft said 60,000 workers are eligible. AI spending continues [P3].",
            "WHY_IT_MATTERS": "WITHHELD",
            "DRAFT": "WITHHELD",
        }
        report = audit_model_evidence(fields, PARAGRAPHS)
        self.assertTrue(any("uncited claim" in issue for issue in report["flags"]))

    def test_empty_and_withheld_sections_have_no_unfounded_success(self):
        report = audit_model_evidence(
            {"EVIDENCE": "NONE", "WHY_IT_MATTERS": "WITHHELD", "DRAFT": "WITHHELD"},
            PARAGRAPHS,
        )
        self.assertEqual(report["flags"], [])
        self.assertFalse(report["verified"])

    def test_quantity_flag_is_independent_of_model_citation_id_validity(self):
        fields = {
            "EVIDENCE": "Around 60,000 people [P9].",
            "WHY_IT_MATTERS": "NONE",
            "DRAFT": "WITHHELD",
        }
        report = audit_model_evidence(fields, PARAGRAPHS)
        self.assertTrue(any("no available" in f for f in report["flags"]))

    def test_multiple_cited_paragraphs_may_support_claim_quantities(self):
        fields = {
            "EVIDENCE": "60,000 eligible employees and infrastructure spending [P1][P3].",
            "WHY_IT_MATTERS": "NONE", "DRAFT": "60K employees. " + URL,
        }
        self.assertEqual(audit_model_evidence(fields, PARAGRAPHS)["flags"], [])

    def test_citation_claim_units_are_local_per_sentence(self):
        fields = {"EVIDENCE": "Workers eligible [P1]. Separately, expenses rose 3.3% [P3].",
                  "WHY_IT_MATTERS": "NONE"}
        claims = claim_units(fields)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["refs"], ["P1"])
        self.assertEqual(claims[1]["refs"], ["P3"])


class FocusedExcerptTests(unittest.TestCase):
    def test_relevant_number_near_end_beats_generic_paragraph_start(self):
        text = ("The CEO discussed shifting investment priorities across AI tooling "
                "and cloud services, without saying what the final headcount will be. " * 2 +
                "The offer is available to about 60,000 employees across divisions. " +
                "Other editorial commentary followed.")
        excerpt = focused_excerpt(text, ["Microsoft offered to 60,000 employees [P1]"])
        self.assertIn("60,000", excerpt)
        self.assertLessEqual(len(excerpt), 192)
        self.assertTrue(excerpt.startswith("…"))
        self.assertTrue(excerpt.endswith("…"))

    def test_focused_snippet_escapes_untrusted_html_when_rendered(self):
        evidence = {
            **EVIDENCE, "paragraphs": [dict(row) for row in PARAGRAPHS],
        }
        evidence["paragraphs"][0]["text"] += " " + "</pre><script>alert('bad')</script>"
        rendered = render_summary(QUEUE, 1, MODEL_GOOD, evidence)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("**P1 — publisher excerpt:**", rendered)

    def test_source_excerpt_window_bounded_when_no_relevant_terms(self):
        excerpt = focused_excerpt("Miscellaneous prose about markets. " * 24, ["completely unrelated"])
        self.assertLessEqual(len(excerpt), 192)


class ReviewAndIssueTests(unittest.TestCase):
    def test_correct_review_is_still_unverified_not_approved(self):
        rendered = render_summary(QUEUE, 1, MODEL_GOOD, EVIDENCE)
        self.assertIn("Automated evidence precheck:", rendered)
        self.assertIn("factual meaning NOT verified", rendered)
        self.assertNotIn("Needs manual attention:", rendered)
        self.assertIn("HUMAN FACT-CHECK REQUIRED", rendered)
        self.assertIn("publication_authorized=false", rendered)
        self.assertIn("60,000", suggested_clean_draft(rendered))

    def test_wrong_reference_surfaces_warning_without_fact_check_claim(self):
        rendered = render_summary(QUEUE, 1, MODEL_WRONG, EVIDENCE)
        self.assertIn("**Automated evidence precheck:** Needs manual attention:", rendered)
        self.assertIn("quantity 60000", rendered)
        self.assertIn("P2", rendered)
        self.assertIn("potentially truncated", rendered)
        self.assertIn("NOT fact-checking", rendered)
        self.assertEqual(evaluate_review(QUEUE["articles"][0], MODEL_WRONG,
                                         EVIDENCE)["evidence_audit"]["status"],
                         "needs_attention")

    @patch("newsbot.ai_drafts.run_gh")
    def test_flagged_review_does_not_autoprefill_editable_post(self, gh):
        gh.side_effect = [
            "true", "[]", "",
            "https://github.com/varadachiru/x-news-automation/issues/200",
        ]
        with tempfile.TemporaryDirectory() as d:
            body = Path(d)/"review.md"
            body.write_text(render_summary(QUEUE, 1, MODEL_WRONG, EVIDENCE),
                            encoding="utf-8")
            with patch.dict(os.environ, {"GH_TOKEN": "FAKE"}):
                save_private_review("varadachiru/x-news-automation", "200", body)
            editor = body.read_text(encoding="utf-8").split(
                "### My edited X post (manual only)", 1)[1]
            self.assertIn("Resolve the flagged evidence/format gaps", editor)
            self.assertNotIn("60,000 eligible workers", editor)
            self.assertIn("Publication approval:** NOT GRANTED", editor)

    @patch("newsbot.ai_drafts.run_gh")
    def test_unflagged_issue_still_prefills_unverified_draft(self, gh):
        gh.side_effect = [
            "true", "[]", "",
            "https://github.com/varadachiru/x-news-automation/issues/201",
        ]
        with tempfile.TemporaryDirectory() as d:
            body = Path(d)/"review.md"
            body.write_text(render_summary(QUEUE, 1, MODEL_GOOD, EVIDENCE),
                            encoding="utf-8")
            with patch.dict(os.environ, {"GH_TOKEN": "FAKE"}):
                save_private_review("varadachiru/x-news-automation", "201", body)
            editor = body.read_text(encoding="utf-8").split(
                "### My edited X post (manual only)", 1)[1]
            self.assertIn("60,000 eligible workers", editor)
            self.assertIn("Publication approval:** NOT GRANTED", editor)

    def test_prompt_requires_exact_evidence_and_differentiates_eligibility(self):
        prompt = make_prompt(QUEUE, 1, EVIDENCE)
        self.assertIn("For EACH factual sentence", prompt)
        self.assertIn("60,000 layoffs", prompt)
        self.assertIn("must appear in its cited", prompt)
        self.assertIn("Do not submit, schedule, send, or post anything.", prompt)

    def test_workflow_still_manual_credit_only_no_model_in_tests(self):
        text = Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("inputs.approve_credit_use == true", text)
        self.assertIn("default: false", text)
        self.assertEqual(text.count("copilot -p "), 1)
        self.assertNotIn("\n  schedule:", text)
        self.assertNotIn("api.x.com", text)
        self.assertNotIn("api.twitter.com", text)


if __name__ == "__main__":
    unittest.main()
