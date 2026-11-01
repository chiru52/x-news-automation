"""Offline proof that a fresh timestamp cannot mask stale or forged headlines."""
import datetime as dt
import unittest

from scripts.check_live_news_worker import (
    EXPECTED_COLLECTOR_CONTRACT, freshness_verdict, run, PREVIEW, UNTRUSTED
)
from scripts.signaldesk_feed_integrity import inspect_feed_stories, source_url_ok

NOW = dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)
STAMP = "2026-11-01T11:50:00Z"


def article(index, region="global", age_hours=3):
    return {"id": f"{index:024x}", "title": f"Verified technology product update {index}",
            "publisher": "Publisher Name",
            "source_url": f"https://news.example.org/story/{index}",
            "category": "technology", "region": region,
            "published_at": (NOW-dt.timedelta(hours=age_hours)).isoformat(),
            "status": "unverified", "image_url": ""}


def feed(global_news=None, india_news=None):
    return {"schema_version": 1, "generated_at": STAMP,
            "news": global_news if global_news is not None else [article(i) for i in range(5)],
            "india_news": india_news if india_news is not None else [],
            "drafts": []}


class SignalDeskIntegrityTests(unittest.TestCase):
    def test_two_regions_really_support_50_verified_items(self):
        data = feed([article(i) for i in range(50)],
                    [article(i+50, "india", 70) for i in range(50)])
        self.assertEqual(freshness_verdict(data, NOW)[0], "PASS")
        self.assertIn("50 Global / 50 India verified", freshness_verdict(data,NOW)[1])

    def test_global_36_and_india_72_hour_windows_are_independent(self):
        self.assertIn("36-hour", freshness_verdict(feed([article(i,age_hours=40) for i in range(5)]),NOW)[1])
        data = feed(india_news=[article(50, "india", 70)])
        self.assertEqual(freshness_verdict(data,NOW)[0],"PASS")
        data["india_news"]=[article(50,"india",73)]
        self.assertIn("72-hour", freshness_verdict(data,NOW)[1])
        data["india_news"]=[article(50,"india",-1)]
        self.assertIn("72-hour", freshness_verdict(data,NOW)[1])

    def test_timestamp_only_or_empty_fake_stories_cannot_pass(self):
        data=feed([{} for _ in range(5)])
        self.assertEqual(freshness_verdict(data,NOW)[0],"FAIL")
        data=feed()
        data["news"][2]["published_at"]="2025-11-01T11:50:00Z"
        self.assertEqual(freshness_verdict(data,NOW)[0],"FAIL")
        data=feed()
        data["news"][2]["published_at"]="not-a-date"
        self.assertEqual(freshness_verdict(data,NOW)[0],"FAIL")

    def test_duplicate_ids_and_urls_are_rejected_across_regions(self):
        data=feed(india_news=[{**article(9,"india"),"source_url":"https://news.example.org/story/0"}])
        self.assertIn("duplicate publisher link",freshness_verdict(data,NOW)[1])
        data=feed(india_news=[article(0,"india")])
        self.assertIn("duplicate article ID",freshness_verdict(data,NOW)[1])

    def test_attribution_region_category_and_unverified_state_are_required(self):
        for key,value in (("publisher",""),("title",""),("region","india"),
                          ("category","malicious"),("status","published")):
            with self.subTest(field=key):
                data=feed()
                data["news"][0][key]=value
                self.assertEqual(freshness_verdict(data,NOW)[0],"FAIL")

    def test_bad_article_link_or_image_is_rejected(self):
        for link in ("http://news.example.org/1", "https://localhost/a",
                     "https://127.0.0.1/a", "https://example.com:8080/a",
                     "javascript:alert(1)","https://user:pass@example.org/a"):
            self.assertFalse(source_url_ok(link),link)
        for key in ("source_url","image_url"):
            data=feed()
            data["news"][0][key]="https://127.0.0.1/article"
            self.assertEqual(freshness_verdict(data,NOW)[0],"FAIL")

    def test_old_live_worker_fails_readiness_even_if_health_http_is_200(self):
        def fake_fetch(path,origin):
            body={"status":"read_only","x_posting_enabled":False,
                  "ai_generation_enabled":False}
            if path=="/feed":body=feed()
            return {"status":200,"data":body,"headers":
                    {} if origin==UNTRUSTED else {"Access-Control-Allow-Origin":origin}}
        rows=run(fake_fetch,now=NOW)
        self.assertEqual(rows[0]["details"],
                         "Health flags or deployed collector contract do not match current tested code")
        self.assertEqual(rows[3]["details"].split(":")[0],"Feed PASS")
        self.assertEqual(EXPECTED_COLLECTOR_CONTRACT,"rss-v2-india72-exact-origin")


if __name__ == "__main__":
    unittest.main()
