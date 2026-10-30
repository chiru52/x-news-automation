"""No live network: shared collector's Pages fallback, CSP and deployment scope."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from news_collector import configure_live

ROOT = Path(__file__).resolve().parents[1]


class LiveCollectorWiringTests(unittest.TestCase):
    def setup_bundle(self, dest):
        (dest / "_headers").write_text(
            "/*\n  Content-Security-Policy: default-src 'none'; connect-src 'self';\n",
            encoding="utf-8")
        (dest / "feed-config.json").write_text('{"schema_version":1,"live_feed_url":null}',
                                              encoding="utf-8")

    def test_static_fallback_when_cloudflare_access_is_not_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            with patch.object(configure_live, "discover", side_effect=RuntimeError("403")):
                value = configure_live.configure(dest)
            self.assertIsNone(value["live_feed_url"])
            self.assertEqual(json.loads((dest / "feed-config.json").read_text("utf-8")),
                             {"schema_version": 1, "live_feed_url": None})
            self.assertIn("connect-src 'self';", (dest / "_headers").read_text("utf-8"))

    def test_live_url_only_after_verified_worker_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            url = "https://signaldesk-news-feed.example-workers.workers.dev/feed"
            with patch.object(configure_live, "discover", return_value=url):
                value = configure_live.configure(dest)
            self.assertEqual(value["live_feed_url"],url)
            headers = (dest / "_headers").read_text("utf-8")
            self.assertIn("connect-src 'self' https://signaldesk-news-feed.example-workers.workers.dev;",headers)
            self.assertNotIn("CLOUDFLARE_API_TOKEN", headers)

    def test_wrong_worker_hostname_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            self.setup_bundle(dest)
            with patch.object(configure_live,"discover",
                              return_value="https://random.example.org/feed"):
                value=configure_live.configure(dest)
            self.assertIsNone(value["live_feed_url"])

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
