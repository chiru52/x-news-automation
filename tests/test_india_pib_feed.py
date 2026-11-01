"""PIB source is a separately labelled India-only public preview input."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.core import Article
from newsbot.regions import is_india_article, explicit_india_sources, select_india_preview_articles

ROOT = Path(__file__).resolve().parents[1]


class IndiaPibPreviewTests(unittest.TestCase):
    def test_pib_is_official_headline_only_without_images(self):
        extras = json.loads((ROOT / "config/extra-news-sources.json").read_text())
        pib = next(row for row in extras if row["name"].startswith("Press Information Bureau"))
        self.assertEqual(pib["url"], "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1")
        self.assertEqual((pib["region"], pib["category"], pib["source_type"]),
                         ("india", "policy", "official_primary"))
        self.assertIs(pib["headline_only"], True)
        self.assertIs(pib["disable_images"], True)
        self.assertIn("pib.gov.in", pib["policy_url"])

    def test_official_india_headline_is_eligible_at_fifty_hours_but_not_seventy_three(self):
        sources = json.loads((ROOT / "config/sources.json").read_text())
        sources += json.loads((ROOT / "config/extra-news-sources.json").read_text())
        now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        def release(hours, suffix):
            return Article(
                title="India government approves new banking technology policy " + suffix,
                link="https://pib.gov.in/PressReleasePage.aspx?PRID=" + suffix,
                source="Press Information Bureau (official India press releases)",
                published_at=(now-timedelta(hours=hours)).isoformat(),
                summary="",
                category="policy",
            )
        fresh, expired = release(50, "100"), release(73, "101")
        self.assertTrue(is_india_article(fresh, explicit_india_sources(sources)))
        selected = select_india_preview_articles([fresh, expired], sources, now)
        self.assertEqual([item.link for item in selected], [fresh.link])


if __name__ == "__main__":
    unittest.main()
