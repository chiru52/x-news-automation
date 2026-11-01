"""Global and India may each show up to fifty *qualified* headlines.

This is public preview selection only. The editorial posting quota stays at 9
and no database, network, Cloudflare deployment or publishing is involved.
"""
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.core import Article, select_articles
from newsbot.regions import global_preview_candidates, select_india_preview_articles

NOW=datetime(2026,11,1,11,0,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]


class IndependentRegionalPreviewTests(unittest.TestCase):
    def article(self, num, region, source):
        return Article(
            title=("India policy and business update" if region=="india" else
                   "Global financial market earnings update") + " " + str(num),
            link=f"https://example.com/{region}/{num}", source=source,
            category="markets", published_at=(NOW-timedelta(minutes=num*4)).isoformat(),
            summary="Public report, verification required")

    def test_global_india_50_are_independent_without_padding_or_overlaps(self):
        global_items=[self.article(i,"global","Global Feed "+str(i%13))
                      for i in range(90)]
        india_items=[self.article(i,"india","India Feed "+str(i%13))
                     for i in range(90)]
        sources=[{"name":"India Feed "+str(i),"region":"india"} for i in range(13)]
        mixed=[v for pair in zip(global_items,india_items) for v in pair]
        global_candidates=global_preview_candidates(mixed,sources)
        self.assertEqual(len(global_candidates),90)
        state={"seen":{},"seen_titles":{},"daily_drafts":{}}
        selected=select_articles(global_candidates,state,NOW,daily_limit=50,
                                 lookback_hours=36,rank_by_relevance=False,
                                 max_per_source_per_day=7)
        india=select_india_preview_articles(mixed,sources,NOW)
        self.assertEqual(len(selected),50)
        self.assertEqual(len(india),50)
        self.assertEqual(len({x.identity for x in selected+india}),100)
        self.assertTrue(all(x.source.startswith("Global") for x in selected))
        self.assertTrue(all(x.source.startswith("India") for x in india))
        self.assertLessEqual(max(Counter(x.source for x in selected).values()),7)
        self.assertLessEqual(max(Counter(x.source for x in india).values()),4)

    def test_no_india_news_is_mislabelled_as_global_just_to_fill_quota(self):
        items=[self.article(i,"india","India Feed") for i in range(15)]
        selected=global_preview_candidates(items,[{"name":"India Feed","region":"india"}])
        self.assertEqual(selected,[])

    def test_non_preview_original_pipeline_and_posting_limits_stay_intact(self):
        main=(ROOT/"newsbot/__main__.py").read_text()
        settings=(ROOT/"config/settings.json").read_text()
        self.assertIn('if args.preview else stories',main)
        self.assertIn('max_per_source_per_day=(7 if args.dashboard_limit else',main)
        self.assertIn('"daily_draft_limit": 9',settings)
        self.assertIn('"publishing_enabled": false',settings)
        self.assertIn('PUBLISH_ENABLED=false',
                      (ROOT/"scripts/build_cloudflare_preview.sh").read_text())


if __name__=="__main__":
    unittest.main()
