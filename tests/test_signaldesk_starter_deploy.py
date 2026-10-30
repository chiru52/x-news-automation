"""Prevent the Cloudflare starter bootstrap from leaking private drafts."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StarterDeploymentSafetyTests(unittest.TestCase):
    def test_bootstrap_has_a_narrow_once_only_trigger(self):
        text = (ROOT / ".github/workflows/deploy-signaldesk-starter.yml").read_text("utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("branches: [main]", text)
        self.assertIn("paths:\n      - '.github/workflows/deploy-signaldesk-starter.yml'", text)
        self.assertNotIn("  schedule:", text)
        self.assertNotIn("  pull_request:", text)
        self.assertIn("  contents: read", text)
        self.assertNotIn("  issues: read", text)
        self.assertNotIn("  issues: write", text)

    def test_starter_never_uploads_private_bundles(self):
        text = (ROOT / ".github/workflows/deploy-signaldesk-starter.yml").read_text("utf-8")
        self.assertIn("d['news'] == [] and d['drafts'] == []", text)
        self.assertIn("out=Path('dist/public-starter')", text)
        self.assertIn("assert len(list(out.iterdir())) == 6", text)
        self.assertIn("pages deploy dist/public-starter", text)
        self.assertNotIn("dist/signaldesk", text)
        self.assertNotIn("signaldesk-private-site", text)
        self.assertIn("'studio.mjs'", text)
        self.assertNotIn("gh issue", text)
        self.assertNotIn("newsbot.dashboard_export", text)
        self.assertNotIn("api.x.com", text)

    def test_public_starter_is_empty(self):
        import json
        d = json.loads((ROOT / "dashboard/data.json").read_text("utf-8"))
        self.assertEqual(d["news"], [])
        self.assertEqual(d["drafts"], [])


if __name__ == "__main__":
    unittest.main()
