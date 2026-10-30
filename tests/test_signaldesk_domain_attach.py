"""Offline safety tests for one-time SignalDesk Pages domain association."""
import unittest
from pathlib import Path

FLOW = (Path(__file__).resolve().parents[1] /
        ".github/workflows/attach-signaldesk-custom-domain.yml")


class DomainAttachmentWorkflowTests(unittest.TestCase):
    def test_narrow_one_time_event_and_approved_domain(self):
        txt = FLOW.read_text("utf-8")
        self.assertIn("workflow_dispatch:", txt)
        self.assertIn("branches: [main]", txt)
        self.assertIn("paths:\n      - '.github/workflows/attach-signaldesk-custom-domain.yml'", txt)
        self.assertNotIn("  schedule:", txt)
        self.assertNotIn("  pull_request:", txt)
        self.assertIn("DOMAIN = 'news.littlekingchess.com'", txt)
        self.assertIn("PROJECT = 'signaldesk-news'", txt)

    def test_does_not_alter_dns_or_publish_x(self):
        txt = FLOW.read_text("utf-8")
        self.assertIn("  contents: read", txt)
        self.assertNotIn("issues: write", txt)
        self.assertIn("api('POST', endpoint, {'name': DOMAIN})", txt)
        self.assertNotIn("/dns_records", txt)
        self.assertNotIn("pages deploy", txt)
        self.assertNotIn("api.x.com", txt)
        self.assertNotIn("PUBLISH_ENABLED", txt)
        self.assertNotIn("echo '$CLOUDFLARE_API_TOKEN'", txt)


if __name__ == "__main__":
    unittest.main()
