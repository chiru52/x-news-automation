"""No live network: shared collector's Pages fallback, CSP and deployment scope."""
import json
import tempfile
import unittest
from pathlib import Path

from news_collector import configure_live

ROOT = Path(__file__).resolve().parents[1]


class LiveCollectorWiringTests(unittest.TestCase):
    def setup_bundle(self, dest):
        (dest / "_headers").write_text(
            "/*\n  Content-Security-Policy: default-src 'none'; connect-src 'self';\n",
            encoding="utf-8")
        (dest / "feed-config.json").write_text('{"schema_version":1,"live_feed_url":null}',
                                              encoding="utf-8")

    def test_static_fallback_if_no_public_worker_url_is_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            value = configure_live.configure(dest)
            self.assertIsNone(value["live_feed_url"])
            self.assertEqual(json.loads((dest / "feed-config.json").read_text("utf-8")),
                             {"schema_version": 1, "live_feed_url": None})
            self.assertIn("connect-src 'self';", (dest / "_headers").read_text("utf-8"))

    def test_pinned_verified_public_url_and_csp(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            url = configure_live.APPROVED_ENDPOINT
            (dest / "feed-config.json").write_text(
                json.dumps({"schema_version":1,"live_feed_url":url}), encoding="utf-8")
            value = configure_live.configure(dest)
            self.assertEqual(value["live_feed_url"],url)
            headers = (dest / "_headers").read_text("utf-8")
            self.assertIn("connect-src 'self' " + configure_live.APPROVED_ORIGIN + ";",headers)
            self.assertNotIn("CLOUDFLARE_API_TOKEN", headers)

    def test_unapproved_worker_hostname_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            (dest / "feed-config.json").write_text(json.dumps(
                {"schema_version":1,"live_feed_url":"https://attacker.example/feed"}),
                encoding="utf-8")
            value=configure_live.configure(dest)
            self.assertIsNone(value["live_feed_url"])
            self.assertIn("connect-src 'self';", (dest / "_headers").read_text("utf-8"))

    def test_worker_url_is_configured_by_approved_source_only(self):
        source = json.loads((ROOT / "dashboard/feed-config.json").read_text("utf-8"))
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source["live_feed_url"], configure_live.APPROVED_ENDPOINT)
        self.assertNotIn("run_path", (ROOT / "news_collector/configure_live.py").read_text("utf-8"))
        self.assertNotIn("api.cloudflare.com", (ROOT / "news_collector/configure_live.py").read_text("utf-8"))

    def test_worker_deploy_is_separate_and_no_model_or_x(self):
        workflow = (ROOT/".github/workflows/deploy-news-collector.yml").read_text("utf-8")
        self.assertIn("deploy --config wrangler.generated.jsonc",workflow)
        self.assertIn("python news-collector/setup_cloudflare.py provision",workflow)
        self.assertIn("python news-collector/setup_cloudflare.py discover",workflow)
        self.assertIn("actions: write",workflow)
        self.assertIn("build-news-dashboard.yml",workflow)
        self.assertNotIn("secrets.X_",workflow)
        self.assertNotIn("secrets.OPENAI_API_KEY",workflow)
        self.assertNotIn("pages deploy",workflow)
        self.assertIn("PUBLISH_ENABLED: 'false'",workflow)

    def test_worker_health_probe_matches_successful_read_only_diagnostic(self):
        setup=(ROOT / "news-collector/setup_cloudflare.py").read_text("utf-8")
        deploy=(ROOT / ".github/workflows/deploy-news-collector.yml").read_text("utf-8")
        self.assertIn('"User-Agent": "SignalDesk-ReadOnly-HealthDiagnostic/1.0"', setup)
        self.assertIn('"Accept": "application/json"', setup)
        self.assertIn('with urlopen(request, timeout=12)', setup)
        self.assertIn("'news-collector/**'", deploy)
        self.assertNotIn("'news_collector/**'", deploy)
        self.assertNotIn("secrets.X_", deploy)

    def test_public_dashboard_never_triggers_news_collection(self):
        js=(ROOT/"dashboard/app.js").read_text("utf-8")
        self.assertIn('fetch(endpoint,{cache:"no-store",mode:"cors",credentials:"omit"})',js)
        self.assertIn("allowCollectorUrl(config.live_feed_url)",js)
        self.assertIn('fetch("./data.json",{cache:"no-store"})',js)
        self.assertIn('liveFeedUrl=allowCollectorUrl(config.live_feed_url)',js)
        self.assertNotIn('method:"POST"',js)
        self.assertNotIn("wrangler deploy",js)
        self.assertNotIn("api.x.com",js)

    def test_safety_of_public_data_export_and_worker_trigger(self):
        exporter=(ROOT/"newsbot/dashboard_export.py").read_text("utf-8")
        site=(ROOT/".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn('"feed-config.json"',exporter)
        self.assertIn("news_collector.configure_live",site)
        self.assertIn("python -m newsbot --preview --dashboard-limit 30",site)
        self.assertIn("PUBLISH_ENABLED: 'false'",site)
        self.assertIn("issues: read",site)
        self.assertNotIn("issues: write",site)


if __name__ == "__main__":
    unittest.main()
