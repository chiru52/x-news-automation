"""Stage 25: quality-first story ranking, clearer context, safe share URLs."""
from datetime import datetime, timezone, timedelta
import unittest
from pathlib import Path

from newsbot.story_history import normalize_url, choose_story_order, editorial_priority
from newsbot.copilot_review import make_prompt, evaluate_review, render_summary, select_research_evidence
from newsbot.ai_drafts import suggested_clean_draft


NOW = datetime(2026, 10, 29, 18, tzinfo=timezone.utc)
RAW = "https://finance.yahoo.com/markets/stocks/articles/pinnacle-stock-flat-post-q3-162800922.html?.tsrc=rss&utm_source=feed"
SHARE = "https://finance.yahoo.com/markets/stocks/articles/pinnacle-stock-flat-post-q3-162800922.html"


def item(idx, title, category, score=8):
    host = "finance.yahoo.com" if category == "markets" else "www.thesaasnews.com"
    return {
        "link": f"https://{host}/news/story-{idx}",
        "title": title,
        "category": category,
        "relevance": {"score": score},
        "published_at": (NOW-timedelta(hours=2)).isoformat(),
        "publishable": False,
        "source": "News",
        "summary": "",
    }


def queue(*items):
    return {"generated_at": NOW.isoformat(), "publishing_enabled": False,
            "preview_only": True, "articles": list(items)}


HISTORY = {"review_only": True, "stories": [], "count": 0}
ROWS = [
    {"id": "P1", "text": "Pinnacle Bankshares Corporation reported rising net interest income in the third quarter. It described loan growth and costs."},
    {"id": "P2", "text": "The company's noninterest costs rose more slowly than net interest income in the reported quarter."},
]


class StoryPriorityTests(unittest.TestCase):
    def test_quality_first_chooses_product_announcement_over_stock_and_funding(self):
        q = queue(
            item(1, "Pinnacle Stock Flat Post Q3 Earnings Despite Loan Growth", "markets", 12),
            item(2, "Cloud software startup launches AI automation for developers", "saas", 8),
            item(3, "New security model released for AI developers", "technology", 7),
            item(4, "Startup raises $30M Series A funding round", "saas", 10),
        )
        order = choose_story_order(q, 1, HISTORY, strategy="quality_first")
        self.assertEqual(order[0], 3)
        self.assertEqual(order[1], 2)
        self.assertEqual(order[-1], 1)
        self.assertGreater(editorial_priority(q["articles"][1]),
                           editorial_priority(q["articles"][3]))

    def test_preferred_first_still_honors_manual_article(self):
        q = queue(
            item(1, "Pinnacle Stock Flat Post Q3 Earnings", "markets", 9),
            item(2, "New AI model released", "technology", 8),
        )
        self.assertEqual(choose_story_order(q, 1, HISTORY,
                                             strategy="preferred_first")[0], 1)
        self.assertEqual(choose_story_order(q, 1, HISTORY)[0], 1)
        with self.assertRaises(ValueError):
            choose_story_order(q, 1, HISTORY, strategy="unknown")

    def test_duplicate_and_stale_sources_still_skipped_before_quality_ranking(self):
        old = item(1, "New AI model released", "technology", 9)
        recent = item(2, "Software automation launches new tool", "saas", 5)
        stale = item(3, "New cloud product launched", "technology", 9)
        stale["published_at"] = (NOW - timedelta(hours=50)).isoformat()
        q = queue(old, recent, stale)
        history = {"review_only": True, "stories": [{"link": old["link"], "title": old["title"]}], "count": 1}
        self.assertEqual(choose_story_order(q, 1, history,
                                             strategy="quality_first"), [2])
        visited = []
        def fetch(url):
            visited.append(url)
            return {"source_url": url, "status": "extracted_unverified",
                    "reason": None, "paragraphs": ROWS}
        selected = select_research_evidence(q, 1, fetcher=fetch, history=history,
                                            strategy="quality_first")
        self.assertEqual(selected["selected_index"], 2)
        self.assertEqual(visited, [recent["link"]])
        self.assertIn("already_reviewed", [a["reason"] for a in selected["attempts"]])
        self.assertIn("stale_or_ineligible", [a["reason"] for a in selected["attempts"]])

    def test_quality_first_falls_back_when_top_publisher_blocked(self):
        q = queue(item(1, "AI model released", "technology"),
                  item(2, "Cloud security tools launched", "saas"),
                  item(3, "Stock price is flat post Q3 earnings", "markets"))
        visited=[]
        def fetch(url):
            visited.append(url)
            if url == q["articles"][0]["link"]:
                return {"status":"unavailable","reason":"http_unavailable",
                        "source_url":url,"paragraphs":[]}
            return {"status":"extracted_unverified","reason":None,
                    "source_url":url,"paragraphs":ROWS}
        result = select_research_evidence(q,1,fetcher=fetch,history=HISTORY,
                                           strategy="quality_first")
        self.assertEqual(result["selected_index"], 2)
        self.assertEqual(len(visited),2)

    def test_no_unused_fresh_candidates_never_calls_fetcher(self):
        q=queue(item(1,"AI model released","technology"))
        history={"review_only":True,"stories":[{"link":q["articles"][0]["link"],"title":"AI model released"}],"count":1}
        def forbidden(_):
            raise AssertionError("would have spent model or network budget")
        output = select_research_evidence(q,1,fetcher=forbidden,history=history,
                                           strategy="quality_first")
        self.assertEqual(output["reason"],"no_unused_fresh_candidates")
        self.assertEqual(output["status"],"unavailable")

    def test_incomplete_user_supplied_category_does_not_become_fact(self):
        q=queue(item(1,"Something happened","unknown",20))
        self.assertEqual(editorial_priority(q["articles"][0]),0)
        self.assertEqual(choose_story_order(q,1,HISTORY,strategy="quality_first"),[1])


class CleanSourceAndPromptTests(unittest.TestCase):
    def test_strip_only_known_tracking_components(self):
        self.assertEqual(normalize_url(RAW+"#overview"), SHARE)
        meaningful="https://example.org/article?id=415&lang=en&utm_campaign=feed"
        self.assertEqual(normalize_url(meaningful), "https://example.org/article?id=415&lang=en")
        self.assertEqual(normalize_url("https://example.org/article?token=abc&.tsrc=rss"),
                         "https://example.org/article?token=abc")

    def test_source_url_display_remains_original_for_history(self):
        i=item(1,"Pinnacle Bankshares reports Q3 earnings","markets")
        i["link"]=RAW
        q=queue(i)
        evidence={"source_url":RAW,"status":"extracted_unverified","reason":None,"paragraphs":ROWS}
        model=("VERIFICATION: NOT VERIFIED\nEVIDENCE: Net interest income [P1].\n"
               "WHY_IT_MATTERS: Net interest income grew versus expense [P1][P2].\n"
               "DRAFT: Pinnacle Bankshares reported faster net interest income growth than costs. "+RAW+"\n"
               "SOURCE: "+RAW+"\nREVIEW_CHECKS: Confirm figures.")
        report=render_summary(q,1,model,evidence)
        self.assertIn("**Source URL:** "+RAW.replace("&", "&amp;"),report)
        self.assertIn("**Shareable source URL:** "+SHARE,report)
        clean=suggested_clean_draft(report)
        self.assertIn(SHARE,clean)
        self.assertNotIn(".tsrc=rss",clean)
        self.assertNotIn("utm_",clean)
        self.assertNotIn("Needs corrections:",report)

    def test_accept_shareable_url_from_model_without_inventing_facts(self):
        i=item(1,"Pinnacle Bankshares reports Q3 earnings","markets")
        i["link"]=RAW
        evidence={"source_url":RAW,"status":"extracted_unverified","reason":None,"paragraphs":ROWS}
        model=("VERIFICATION: NOT VERIFIED\nEVIDENCE: Bankshares report [P1].\n"
               "WHY_IT_MATTERS: Income versus expense [P1][P2].\n"
               "DRAFT: Pinnacle Bankshares reports loan growth. "+SHARE+"\n"
               "SOURCE: "+SHARE+"\nREVIEW_CHECKS: Confirm bank name.")
        review=evaluate_review(i,model,evidence)
        self.assertNotIn("SOURCE field does not match original article URL",review["issues"])
        self.assertNotIn("X draft missing original article URL",review["issues"])
        self.assertEqual(review["clean_draft"].count(SHARE),1)

    def test_mismatched_external_url_still_flagged(self):
        i=item(1,"Pinnacle Bankshares reports Q3 earnings","markets")
        i["link"]=RAW
        evidence={"source_url":RAW,"status":"extracted_unverified","reason":None,"paragraphs":ROWS}
        model=("VERIFICATION: NOT VERIFIED\nEVIDENCE: Bankshares report [P1].\n"
               "WHY_IT_MATTERS: Bank cost growth [P2].\n"
               "DRAFT: Pinnacle Bankshares story: https://attacker.invalid/a\n"
               "SOURCE: https://attacker.invalid/a\nREVIEW_CHECKS: Check.")
        review=evaluate_review(i,model,evidence)
        self.assertIn("SOURCE field does not match original article URL",review["issues"])
        self.assertIn("X draft missing original article URL",review["issues"])

    def test_prompt_requests_full_identity_and_specific_source_backed_insight(self):
        i=item(1,"Pinnacle earnings","markets")
        q=queue(i)
        evidence={"source_url":i["link"],"status":"extracted_unverified","reason":None,"paragraphs":ROWS}
        prompt=make_prompt(q,1,evidence)
        for phrase in ("shareable_source_url","unambiguously","Never guess a legal company name",
                       "rather than merely", "DRAFT: WITHHELD", "do not invent"):
            self.assertIn(phrase.lower(),prompt.lower())
        self.assertIn(i["link"],prompt)
        self.assertIn("Do not use tools.",prompt)

    def test_actions_quality_default_and_manual_preference_do_not_trigger_ai(self):
        path=Path(".github/workflows/copilot-one-draft.yml")
        text=path.read_text()
        self.assertIn("default: quality_first", text)
        self.assertIn("preferred_first",text)
        self.assertIn("--strategy \"$SELECTION_STRATEGY\"",text)
        self.assertIn("inputs.approve_credit_use == true",text)
        self.assertEqual(text.count("copilot -p "),1)
        self.assertNotIn("\n  schedule:",text)
        self.assertNotIn("api.x.com",text)


if __name__=="__main__":
    unittest.main()
