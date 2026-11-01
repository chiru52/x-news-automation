"""Offline RBI primary-source RSS fixtures: no network, no publishing."""
import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.core import parse_feed
from newsbot.regions import select_india_preview_articles, explicit_india_sources

ROOT=Path(__file__).resolve().parents[1]
EXTRAS=json.loads((ROOT/"config/extra-news-sources.json").read_text("utf-8"))
NOW=datetime(2026,11,1,12,tzinfo=timezone.utc)
RBI=[s for s in EXTRAS if s["url"].startswith("https://www.rbi.org.in/")]


def fixture(title, date, link):
    date_xml=f"<pubDate>{date}</pubDate>" if date else ""
    return ("<?xml version='1.0'?><rss><channel><item>"
            f"<title>{title}</title><link>{link}</link>{date_xml}"
            "<description>Official issuer's announcement.</description>"
            "</item></channel></rss>").encode("utf-8")


class IndiaOfficialFeedExpansionTests(unittest.TestCase):
    def test_exact_rbi_feeds_are_primary_source_headline_only(self):
        self.assertEqual(len(RBI),3)
        self.assertEqual(len({s["url"] for s in RBI}),3)
        for feed in RBI:
            self.assertEqual(feed["region"],"india")
            self.assertEqual(feed["category"],"markets")
            self.assertEqual(feed["source_type"],"official_primary")
            self.assertTrue(feed["headline_only"])
            self.assertTrue(feed["disable_images"])
        self.assertEqual({s["url"].split("/")[-1] for s in RBI},
                         {"pressreleases_rss.xml","notifications_rss.xml","speeches_rss.xml"})

    def test_dated_60_hour_notification_is_valid_india_but_not_global(self):
        source=next(s for s in RBI if "notifications" in s["url"])
        pub=(NOW-timedelta(hours=60)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        feed=fixture("RBI issues banking risk management notification",pub,
                     "https://www.rbi.org.in/example-notification")
        entries=[replace(x,summary="") for x in parse_feed(feed,source["name"],source["category"])]
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0].summary,"")
        self.assertIn(source["name"],explicit_india_sources(EXTRAS))
        self.assertEqual(len(select_india_preview_articles(entries,EXTRAS,NOW)),1)

    def test_missing_item_date_is_not_promoted_to_current_news(self):
        source=next(s for s in RBI if "speeches" in s["url"])
        feed=fixture("RBI governor discusses emerging financial risks",None,
                     "https://www.rbi.org.in/example-speech")
        self.assertEqual(parse_feed(feed,source["name"],source["category"]),[])

    def test_more_than_72_hours_old_is_not_selected(self):
        source=next(s for s in RBI if "speeches" in s["url"])
        pub=(NOW-timedelta(hours=73)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        feed=fixture("RBI governor discusses emerging financial risks",pub,
                     "https://www.rbi.org.in/older-speech")
        entries=parse_feed(feed,source["name"],source["category"])
        self.assertEqual(len(entries),1)
        self.assertEqual(select_india_preview_articles(entries,EXTRAS,NOW),[])

if __name__=="__main__":
    unittest.main()
