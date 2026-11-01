"""Pure deterministic Global/India public-preview editorial ranking tests."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from newsbot.core import Article, render_outputs
from newsbot.preview_ranking import rank_preview_stories
from newsbot.regions import global_preview_candidates, select_india_preview_articles
from newsbot.dashboard_export import build_bundle

NOW=datetime(2026,11,1,12,0,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]


def story(i, *, age=1, title=None, publisher="Paper A", category="markets"):
    return Article(
        title=title or f"Local markets trading activity story number {i}",
        source=publisher,
        link=f"https://news.example.com/{publisher.lower().replace(' ','-')}/{i}",
        published_at=(NOW-timedelta(hours=age)).isoformat(),
        category=category,
        summary="A dated publisher report that requires independent verification before sharing."
    )


class PublicEditorialRankingTests(unittest.TestCase):
    def test_stronger_reported_event_can_outrank_trivial_newer_story(self):
        older=story(1,age=5,title="Central bank approves interest rate reduction affecting economy")
        newer=story(2,age=1,title="Markets discussion continues during the trading day")
        ranked=rank_preview_stories([newer,older],NOW,lookback_hours=36)
        self.assertEqual([x.identity for x in ranked],
                         [older.identity,newer.identity])

    def test_top_50_scores_complete_pool_not_only_first_50_rss_entries(self):
        routine=[story(i,age=2,title=f"Markets discussion in ordinary article number {i}",
                       publisher=f"Source {i%13}") for i in range(70)]
        important=story(900,age=3,title="Central bank approves interest rate reduction and announces policy",
                        publisher="Source 2")
        chosen=rank_preview_stories(routine+[important],NOW,lookback_hours=36,
                                    max_per_source=7)
        self.assertEqual(len(chosen),50)
        self.assertIn(important.identity,{x.identity for x in chosen})

    def test_india_72_and_global_36_windows_stay_independent(self):
        src=[{"name":"India Publisher","region":"india"}]
        global_set=[
            story(1,age=20,publisher="Global Publisher"),
            story(2,age=60,publisher="Global Publisher")]
        india_set=[
            story(3,age=60,publisher="India Publisher"),
            story(4,age=74,publisher="India Publisher")]
        global_selected=rank_preview_stories(global_preview_candidates(
            global_set+india_set,src),NOW,lookback_hours=36)
        india_selected=select_india_preview_articles(
            global_set+india_set,src,NOW)
        self.assertEqual([a.identity for a in global_selected],[global_set[0].identity])
        self.assertEqual([a.identity for a in india_selected],[india_set[0].identity])

    def test_deduplicate_titles_urls_and_source_caps_without_inventing_stories(self):
        near1=story(1,title="Global company announces new bank policy after regulator decision today",
                    publisher="Publisher A")
        near2=story(2,title="Global company announces new bank policy after regulator decision today!",
                    publisher="Publisher B")
        list_of_stories=[near1,near2]+[
            story(i+20,publisher="Publisher A",age=1,
                  title=f"Markets policy report about company number {i} today")
            for i in range(20)]
        ranked=rank_preview_stories(list_of_stories,NOW,lookback_hours=36,
                                    max_per_source=3,limit=50)
        self.assertLessEqual(len(ranked),4)
        self.assertLessEqual(Counter(x.source for x in ranked)["Publisher A"],3)
        self.assertEqual(sum(x.identity in {near1.identity,near2.identity} for x in ranked),1)
        self.assertEqual(len({x.identity for x in ranked}),len(ranked))

    def test_deterministic_under_feed_order_changes_and_future_dated_rejection(self):
        pool=[story(i,publisher=f"Publisher {i%7}",age=(i%8)+1) for i in range(35)]
        a=rank_preview_stories(pool,NOW,lookback_hours=36,limit=20)
        b=rank_preview_stories(list(reversed(pool)),NOW,lookback_hours=36,limit=20)
        self.assertEqual([x.identity for x in a],[x.identity for x in b])
        future=Article(title="Important policy change approved",link="https://x.example/future",
                       source="Publisher",published_at=(NOW+timedelta(hours=1)).isoformat())
        old=story(999,age=80)
        self.assertEqual(rank_preview_stories([future,old],NOW,lookback_hours=36),[])

    def test_no_paid_calls_external_network_or_auto_x_publishing(self):
        text=(ROOT/"newsbot/preview_ranking.py").read_text()
        entry=(ROOT/"newsbot/__main__.py").read_text()
        settings=(ROOT/"config/settings.json").read_text()
        self.assertNotIn("requests.get",text)
        self.assertNotIn("urlopen(",text)
        self.assertNotIn("httpx.",text)
        self.assertIn('if args.preview and args.dashboard_limit is not None',entry)
        self.assertIn('if not args.preview:',entry)
        self.assertIn('"publishing_enabled": false',settings)
        self.assertIn('PUBLISH_ENABLED=false',
                      (ROOT/"scripts/build_cloudflare_preview.sh").read_text())

    def test_generated_bundle_keeps_ranked_source_order(self):
        import tempfile
        news=[story(i,age=1,publisher=f"Source {i%7}") for i in range(17)]
        chosen=rank_preview_stories(news,NOW,lookback_hours=36,limit=10)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            render_outputs(chosen,root,NOW,[],preview_only=True)
            from json import loads
            queue=loads((root/"review_queue.json").read_text())
            result=build_bundle(queue,[],root/"site")
        self.assertEqual([x["source_url"] for x in result["news"]],
                         [x.link for x in chosen])
