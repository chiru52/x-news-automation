import datetime as dt
import unittest

from scripts.check_live_news_worker import (
    PREVIEW, PRODUCTION, UNTRUSTED, cors_verdict, freshness_verdict, run, preview_deployment_report, read_preview_file
)


class LiveNewsWorkerDiagnosticsTests(unittest.TestCase):
    def test_exact_origin_checks_fail_closed(self):
        self.assertEqual(cors_verdict(
            {"Access-Control-Allow-Origin": PREVIEW}, PREVIEW, True), "PASS")
        self.assertEqual(cors_verdict(
            {"Access-Control-Allow-Origin": PRODUCTION}, PREVIEW, True), "FAIL")
        self.assertEqual(cors_verdict({}, PREVIEW, True), "FAIL")
        self.assertEqual(cors_verdict({}, UNTRUSTED, False), "PASS")
        self.assertEqual(cors_verdict(
            {"Access-Control-Allow-Origin": "*"}, UNTRUSTED, False), "FAIL")

    def test_freshness_does_not_accept_stale_or_invalid_news(self):
        now = dt.datetime(2026, 10, 31, 10, 0, tzinfo=dt.timezone.utc)
        good = {"schema_version": 1, "news": [{}] * 5,
                "generated_at": "2026-10-31T09:45:00Z"}
        self.assertEqual(freshness_verdict(good, now)[0], "PASS")
        self.assertEqual(freshness_verdict(
            {**good, "generated_at": "2026-10-31T02:00:00Z"}, now)[0], "FAIL")
        self.assertEqual(freshness_verdict(
            {**good, "generated_at": "2026-11-01T09:45:00Z"}, now)[0], "FAIL")
        self.assertEqual(freshness_verdict(
            {**good, "news": []}, now)[0], "FAIL")
        self.assertEqual(freshness_verdict(
            {**good, "generated_at": "not a date"}, now)[0], "FAIL")

    def test_public_preview_inspection_uses_only_fixed_static_assets(self):
        import json
        self.assertRaises(ValueError,read_preview_file,"/admin")
        seen=[]
        def fake_get(path):
            seen.append(path)
            body=(
                json.dumps({"generated_at":"2026-10-31T23:55:00Z",
                            "news":[{"image_url":""}]*30,"india_news":[]})
                if path=="/data.json" else
                json.dumps([{"name":"A"}]*19) if path=="/editorial-sources.json" else
                "const picture=safeNewsImage(item.image_url);"
            )
            return {"http_status":200,"body":body}
        metrics=preview_deployment_report(fake_get)
        self.assertEqual(seen,["/data.json","/editorial-sources.json","/news-explorer.mjs"])
        self.assertEqual(metrics["static_global_stories"],30)
        self.assertEqual(metrics["static_india_stories"],0)
        self.assertEqual(metrics["catalogue_entries"],19)
        self.assertTrue(metrics["news_explorer_has_real_image_support"])

    def test_audit_is_get_only_and_never_fetches_unapproved_urls(self):
        seen = []
        now = dt.datetime(2026, 10, 31, 10, 0, tzinfo=dt.timezone.utc)

        def fake_get(path, origin):
            seen.append((path, origin))
            body = {"status": "read_only", "x_posting_enabled": False}
            if path == "/feed":
                body = {"schema_version": 1, "news": [{}] * 6,
                        "generated_at": "2026-10-31T09:50:00Z"}
            return {"status": 200, "headers": {
                "Access-Control-Allow-Origin": origin
            } if origin != UNTRUSTED else {}, "data": body}

        results = run(fake_get, now=now)
        self.assertEqual(len(results), 5)
        self.assertEqual([path for path, _ in seen], [
            "/health", "/health", "/health", "/feed", "/archive?days=7"
        ])
        self.assertTrue(all(x["cors"] == "PASS" for x in results))


if __name__ == "__main__":
    unittest.main()
