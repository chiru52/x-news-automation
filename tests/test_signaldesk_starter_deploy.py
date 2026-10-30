"""Prevent the retired empty starter workflow from deploying to Cloudflare."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StarterDeploymentSafetyTests(unittest.TestCase):
    def test_starter_is_manual_only_and_cannot_override_production(self):
        text = (ROOT / ".github/workflows/deploy-signaldesk-starter.yml").read_text("utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("branches: [main]", text)
        self.assertNotIn("  push:", text)
        self.assertNotIn("pages deploy", text)
        self.assertNotIn("wrangler-action", text)
        self.assertNotIn("CLOUDFLARE_API_TOKEN", text)
        self.assertNotIn("  schedule:", text)
        self.assertNotIn("  pull_request:", text)
        self.assertIn("  contents: read", text)
        self.assertNotIn("  issues: read", text)
        self.assertNotIn("  issues: write", text)

    def test_starter_never_uploads_private_bundles(self):
        text = (ROOT / ".github/workflows/deploy-signaldesk-starter.yml").read_text("utf-8")
        self.assertIn("data.get('news') == [] and data.get('drafts') == []", text)
        self.assertIn("out=Path('dist/public-starter')", text)
        self.assertIn("assert len(list(out.iterdir())) == 8", text)
        self.assertIn("signaldesk-empty-starter-do-not-deploy", text)
        self.assertNotIn("pages deploy dist/public-starter", text)
        self.assertNotIn("dist/signaldesk", text)
        self.assertNotIn("signaldesk-private-site", text)
        self.assertIn("'studio.mjs'", text)
        self.assertIn("'refresh-clock.mjs'", text)
        self.assertIn("'news-sections.mjs'", text)
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
