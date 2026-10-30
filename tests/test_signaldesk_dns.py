"""Static safety checks for exact CNAME-only Cloudflare DNS reconciliation."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/'.github/workflows/verify-signaldesk-domain.yml'


class DomainDNSTests(unittest.TestCase):
    def test_workflow_cannot_run_on_unrelated_pushes_or_schedule(self):
        text=WORKFLOW.read_text('utf-8')
        self.assertIn("branches: [main]",text)
        self.assertIn("paths:\n      - '.github/workflows/verify-signaldesk-domain.yml'",text)
        self.assertIn("workflow_dispatch:",text)
        self.assertNotIn("  schedule:",text)
        self.assertNotIn("pull_request:",text)
        self.assertIn("  contents: read",text)
        self.assertNotIn("issues: write",text)

    def test_exact_domain_and_no_overwrite_or_delete(self):
        text=WORKFLOW.read_text('utf-8')
        self.assertIn("ZONE='littlekingchess.com'",text)
        self.assertIn("NAME='news.littlekingchess.com'",text)
        self.assertIn("PROJECT='signaldesk-news'",text)
        self.assertIn("TARGET='signaldesk-news.pages.dev'",text)
        self.assertIn("if records:",text)
        self.assertIn("Existing DNS record conflicts; nothing changed",text)
        self.assertIn("api('POST',records_path",text)
        self.assertNotIn("api('PATCH',records_path",text)
        self.assertNotIn("api('PUT',records_path",text)
        self.assertNotIn("api('DELETE',",text)
        self.assertNotIn("api.x.com",text)
        self.assertNotIn("pages deploy",text)

    def test_requires_ownership_and_unique_zone_before_creation(self):
        text=WORKFLOW.read_text('utf-8')
        self.assertIn("zone.get('account',{}).get('id')!=account",text)
        self.assertIn("len(zone_result)!=1",text)
        self.assertIn("if len(records)>1:",text)
        self.assertIn("current.get('name')!=NAME",text)
        self.assertIn("zone.get('status')!='active'",text)


if __name__=="__main__":
    unittest.main()
