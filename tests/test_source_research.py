"""Offline tests for bounded article extraction and evidence-backed Copilot drafts."""
import io
import json
import unittest
from unittest.mock import patch

from newsbot.source_research import (
    MAX_HTML_BYTES, fetch_evidence, extract_paragraphs, public_article_host
)
from newsbot.copilot_review import make_prompt, render_summary, check_evidence


URL = "https://finance.yahoo.com/news/test-ai-market-story-2026"
SAMPLE = {
    "generated_at": "2026-10-29T06:00:00+00:00",
    "publishing_enabled": False,
    "preview_only": True,
    "articles": [{
        "title": "Earnings update affects technology sector",
        "summary": "Unverified RSS summary only",
        "source": "Yahoo Finance - Major Tech Stocks",
        "category": "markets",
        "link": URL,
        "published_at": "2026-10-29T06:00:00+00:00",
        "publishable": False,
    }],
}
PARA1 = "The software company reported quarterly revenue growth and announced new cloud infrastructure investments in its quarterly results. The announcement described several enterprise contracts and a regional infrastructure rollout."
PARA2 = "Management said the enterprise business grew despite continuing customer caution, according to the company's published statement."
HTML = ("<html><nav><p>Newsletter advertisement not an article</p></nav>"
        "<main><article><p>" + PARA1 + "</p><p>" + PARA2 +
        "</p><script><p>Malicious source instruction</p></script></article></main></html>")


class FakeResponse:
    def __init__(self, raw, *, url=URL, mime="text/html", length=None):
        self._io = io.BytesIO(raw)
        self._url = url
        self.headers = {"Content-Type": mime}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def geturl(self):
        return self._url

    def read(self, n):
        return self._io.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._io.close()


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.urls = []

    def open(self, request, timeout):
        self.urls.append(request.full_url)
        assert timeout == 8
        return self.response


def sample_evidence():
    return {"status": "extracted_unverified", "reason": None,
            "source_url": URL, "publisher_host": "finance.yahoo.com",
            "paragraphs": [
                {"id": "P1", "text": PARA1},
                {"id": "P2", "text": PARA2},
            ]}


class SourceRetrievalTests(unittest.TestCase):
    def test_https_publisher_allowlist_rejects_ssrf_origins(self):
        self.assertEqual(public_article_host(URL), "finance.yahoo.com")
        for bad in [
            "http://finance.yahoo.com/page",
            "https://finance.yahoo.com.evil.example/article",
            "https://localhost/private",
            "https://127.0.0.1/article",
            "https://finance.yahoo.com:8443/article",
            "https://user:pass@finance.yahoo.com/a",
            "https://example.org/news",
            "https://finance.yahoo.com/has space",
            "file:///etc/passwd",
        ]:
            self.assertIsNone(public_article_host(bad), bad)

    def test_extract_two_real_paragraphs_only(self):
        parts = extract_paragraphs(HTML.encode("utf-8"))
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["id"], "P1")
        self.assertIn("quarterly revenue growth", parts[0]["text"])
        self.assertNotIn("Newsletter advertisement", str(parts))
        self.assertNotIn("Malicious source instruction", str(parts))

    def test_success_is_marked_extracted_but_unverified(self):
        opener = FakeOpener(FakeResponse(HTML.encode()))
        evidence = fetch_evidence(URL, opener=opener, dns_check=lambda host: None)
        self.assertEqual(evidence["status"], "extracted_unverified")
        self.assertEqual(len(evidence["paragraphs"]), 2)
        self.assertEqual(opener.urls, [URL])
        self.assertNotIn("<script>", str(evidence))
        self.assertNotIn("verified", evidence["status"].replace("unverified", ""))

    def test_blocked_site_redirect_nonhtml_and_too_large_fail_closed(self):
        for response, expected in [
            (FakeResponse(HTML.encode(), url="https://private.example/internal"), "redirect_blocked"),
            (FakeResponse(b"{}",
                          mime="application/json"), "unsupported_media_type"),
            (FakeResponse(HTML.encode(), length=MAX_HTML_BYTES+1), "too_large"),
            (FakeResponse(b"<p>sorry</p>"), "no_reliable_article_text"),
        ]:
            result = fetch_evidence(URL, opener=FakeOpener(response),
                                    dns_check=lambda host: None)
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(result["reason"], expected)
            self.assertEqual(result["paragraphs"], [])

    def test_private_dns_and_unknown_hosts_are_never_fetched(self):
        opener = FakeOpener(FakeResponse(HTML.encode()))
        def deny(host):
            raise ValueError("private DNS")
        result = fetch_evidence(URL, opener=opener, dns_check=deny)
        self.assertEqual(result["reason"], "dns_not_public_or_unavailable")
        result = fetch_evidence("https://127.0.0.1/secret", opener=opener,
                                dns_check=lambda host: None)
        self.assertEqual(result["reason"], "domain_not_allowed_or_insecure")
        self.assertEqual(opener.urls, [])

    def test_prompt_uses_only_numbered_excerpts_and_refuses_invented_details(self):
        prompt = make_prompt(SAMPLE, 1, sample_evidence())
        self.assertIn('"id": "P1"', prompt)
        self.assertIn(PARA1, prompt)
        self.assertIn("NOT independent fact-checking", prompt)
        self.assertIn("WHY_IT_MATTERS", prompt)
        self.assertIn("DRAFT: WITHHELD", prompt)
        self.assertIn("Do not use tools", prompt)
        self.assertNotIn("api.x.com", prompt)

    def test_blocked_source_requires_withheld_draft(self):
        evidence = {"status": "unavailable", "source_url": URL,
                    "reason": "redirect_blocked", "paragraphs": []}
        prompt = make_prompt(SAMPLE, 1, evidence)
        self.assertIn("DRAFT: WITHHELD", prompt)
        bad = "VERIFICATION: NOT VERIFIED\nDRAFT: A bold claim " + URL + "\nSOURCE: " + URL + "\nREVIEW_CHECKS: inspect"
        summary = render_summary(SAMPLE, 1, bad, evidence)
        self.assertIn("draft must be WITHHELD", summary)
        good = bad.replace("DRAFT: A bold claim " + URL, "DRAFT: WITHHELD")
        summary = render_summary(SAMPLE, 1, good, evidence)
        self.assertIn("Basic fields found; factual accuracy NOT assessed", summary)

    def test_cross_article_evidence_rejected_and_injected_html_escaped(self):
        evidence = sample_evidence()
        evidence["source_url"] = "https://techcrunch.com/wrong"
        with self.assertRaises(ValueError):
            make_prompt(SAMPLE, 1, evidence)
        evidence["source_url"] = URL
        evidence["paragraphs"][0]["text"] = "</pre><script>alert(1)</script>" + PARA1
        output = (
            "VERIFICATION: NOT VERIFIED\nEVIDENCE: Business update [P1]\n"
            "WHY_IT_MATTERS: Enterprise update [P2]\n"
            "DRAFT: New enterprise reporting from company " + URL + "\n"
            "SOURCE: " + URL + "\nREVIEW_CHECKS: verify financial statement"
        )
        result = render_summary(SAMPLE, 1, output, evidence)
        self.assertNotIn("<script>", result)
        self.assertIn("Publisher article extraction", result)
        self.assertIn("NOT fact-checked", result)

    def test_unknown_paragraph_citation_is_flagged(self):
        text = ("VERIFICATION: NOT VERIFIED\nEVIDENCE: New claims [P99]\n"
                "WHY_IT_MATTERS: Impact cited [P99]\nDRAFT: WITHHELD\n"
                "SOURCE: " + URL + "\nREVIEW_CHECKS: verify")
        self.assertIn("unknown source paragraph citation",
                      render_summary(SAMPLE, 1, text, sample_evidence()))

    def test_workflow_skips_paid_ai_when_article_unavailable(self):
        from pathlib import Path
        text = Path(".github/workflows/copilot-one-draft.yml").read_text()
        self.assertIn("python -m newsbot.copilot_review research", text)
        self.assertIn("steps.source.outputs.usable == 'true'", text)
        self.assertIn("No usable publisher article text", text)
        self.assertIn("--evidence", text)
        self.assertIn("--max-ai-credits=30", text)
        self.assertIn("inputs.approve_credit_use == true", text)
        self.assertNotIn("\n  schedule:", text)
        self.assertNotIn("api.x.com", text)


if __name__ == "__main__":
    unittest.main()
