import datetime as dt
import unittest


def story(index, region="global", published="2026-10-31T09:45:00Z"):
    return {"id": f"{index:024x}", "title": f"Software company announces verified update {index}",
            "publisher": "Source Publisher", "source_url": f"https://publisher.example/story/{index}",
            "published_at": published, "category": "technology", "region": region,
            "status": "unverified", "image_url": ""}


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
        good = {"schema_version": 1, "news": [story(i) for i in range(5)], "india_news": [],
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

    def test_live_snapshot_supports_two_independent_50_story_regions(self):
        now = dt.datetime(2026, 10, 31, 10, tzinfo=dt.timezone.utc)
        good = {"schema_version": 1, "news": [story(i) for i in range(50)],
                "india_news": [story(i+50, "india") for i in range(50)],
                "generated_at": "2026-10-31T09:45:00Z"}
        verdict, details = freshness_verdict(good, now)
        self.assertEqual(verdict, "PASS")
        self.assertIn("50 Global / 50 India", details)
        self.assertEqual(freshness_verdict({**good, "news":[story(i) for i in range(51)]}, now)[0], "FAIL")
        self.assertEqual(freshness_verdict({**good, "india_news":None}, now)[0], "FAIL")
        self.assertEqual(freshness_verdict({
            **good, "india_news":[{"region":"global"}]}, now)[0], "FAIL")

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

    def test_image_health_counts_are_aggregated_without_articles_or_private_data(self):
        import json
        def fake_get(path):
            if path=="/data.json":
                return {"http_status":200,"body":json.dumps({
                    "news":[
                        {"publisher":"Publisher A","image_url":"https://img.example/a.jpg","title":"Private not logged"},
                        {"publisher":"Publisher A","image_url":""},
                        {"publisher":"Publisher B","image_url":""},
                    ],"india_news":[{"publisher":"Publisher B","image_url":"https://img.example/b.jpg"}]
                })}
            if path=="/editorial-sources.json":
                return {"http_status":200,"body":"[]"}
            return {"http_status":200,"body":""}
        coverage=preview_deployment_report(fake_get)["publisher_photo_coverage"]
        self.assertEqual(coverage,[
            {"publisher":"Publisher A","stories":2,"with_images":1},
            {"publisher":"Publisher B","stories":2,"with_images":1}
        ])
        self.assertNotIn("title",str(coverage))
        self.assertNotIn("img.example",str(coverage))

    def test_audit_is_get_only_and_never_fetches_unapproved_urls(self):
        seen = []
        now = dt.datetime(2026, 10, 31, 10, 0, tzinfo=dt.timezone.utc)

        def fake_get(path, origin):
            seen.append((path, origin))
            body = {"status": "read_only", "x_posting_enabled": False,
                    "ai_generation_enabled": False,
                    "collector_contract": "rss-v2-india72-exact-origin"}
            if path == "/feed":
                body = {"schema_version": 1, "news": [story(i) for i in range(6)], "india_news": [],
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
