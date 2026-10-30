"""UI and deployment contract tests for Phase 1 (no browser or network)."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class SignalDeskPhaseOneUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.script=(ROOT/"dashboard/app.js").read_text("utf-8")
        cls.styles=(ROOT/"dashboard/styles.css").read_text("utf-8")

    def test_trending_is_editorial_not_social_popularity(self):
        self.assertIn('data-view="trending"', self.page)
        self.assertIn('id="nav-trend-count"', self.page)
        self.assertIn('id="count-trending"', self.page)
        self.assertIn('class="trend-pill" hidden', self.page)
        self.assertIn("not X popularity", self.page)
        self.assertIn("function trendingPicks()", self.script)
        self.assertIn('selectedView === "trending"', self.script)
        self.assertIn('const trendIds = new Set', self.script)
        self.assertIn("trend_score", self.script)
        self.assertIn("trend_reason", self.script)
        self.assertIn(".trend-reason{", self.styles)

    def test_workflow_five_stages_and_browser_only_persistence(self):
        self.assertIn('data-view="workflow"', self.page)
        self.assertIn('id="workflow-filters"', self.page)
        self.assertIn('class="workflow-select"', self.page)
        for stage in ("new","reviewing","ready","copied","archived"):
            self.assertIn('value="'+stage+'"',self.page)
            self.assertIn('data-stage="'+stage+'"',self.page)
        self.assertIn('const workflowKey = "signaldesk:workflow:v1"', self.script)
        self.assertIn("localStorage.setItem(workflowKey", self.script)
        self.assertIn('function setWorkflowStage(item, stage)', self.script)
        self.assertIn('selectedView === "workflow"', self.script)
        self.assertIn('workflowStage(item) === "archived"', self.script)
        self.assertIn('stageSelect.addEventListener("change"', self.script)
        self.assertIn('onCopied();', self.script)
        self.assertIn('setWorkflowStage(item, "copied")', self.script)

    def test_status_never_claims_automatic_verification_or_posting(self):
        self.assertIn("not posted to X", self.script)
        self.assertIn("not fact-checked by SignalDesk", self.script)
        self.assertIn("source and claims before publishing manually", self.script)
        self.assertNotIn("api.x.com", self.script)
        self.assertNotIn("method: 'POST'", self.script)
        self.assertNotIn('method: "POST"', self.script)
        self.assertNotIn("innerHTML", self.script)
        self.assertIn("textContent", self.script)
        self.assertIn('Copy post', self.page)

    def test_deploy_job_uses_sanitized_news_only(self):
        workflow=(ROOT/".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn("newsbot/trend_signals.py", workflow)
        self.assertIn("PUBLISH_ENABLED: 'false'", workflow)
        self.assertNotIn("secrets.X_", workflow)
        self.assertNotIn("copilot -p", workflow)


if __name__ == "__main__":
    unittest.main()
