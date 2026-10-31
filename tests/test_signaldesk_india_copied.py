"""India News and copy-to-history safety assertions; no X or AI calls."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IndiaCopiedDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.js=(ROOT/"dashboard/app.js").read_text("utf-8")
        cls.worker=(ROOT/"news-collector/worker.mjs").read_text("utf-8")

    def test_india_news_has_a_real_source_strategy_not_empty_menu(self):
        sources=json.loads((ROOT/"config/sources.json").read_text("utf-8"))
        self.assertLessEqual(len(sources),20)
        approved={source["url"] for source in sources if source.get("region")=="india"}
        self.assertIn("https://inc42.com/startups/feed/", approved)
        self.assertIn("https://entrepreneur.economictimes.indiatimes.com/rss/startups",approved)
        self.assertIn("https://economictimes.indiatimes.com/rssfeeds/13357270.cms",
                      {source["url"] for source in sources})
        self.assertIn("https://yourstory.com/feed",
                      {source["url"] for source in sources})
        self.assertIn('data-view="india"',self.page)
        self.assertIn('id="nav-india-count"',self.page)
        self.assertIn('function isIndiaNews(item)',self.js)
        self.assertIn('selectedView === "india"',self.js)
        self.assertIn("india_news:Array.isArray(dynamic.india_news)",self.js)
        self.assertIn("export function selectIndiaStories(stories)",self.worker)
        self.assertIn("india_news=await Promise.all(indiaSelected.map(article=>publicItem(article,allArticles,nowMs)))",self.worker)
        self.assertIn('region:isIndiaStory(article) ? "india" : "global"',self.worker)
        self.assertIn('data.india_news.some(item=>item.region!=="india")',self.worker)

    def test_copied_history_moves_out_of_feed_and_can_be_undone(self):
        self.assertIn('data-view="copied"',self.page)
        self.assertIn('id="copy-undo"',self.page)
        self.assertIn('id="undo-copy"',self.page)
        self.assertIn("onCopied();",self.js)
        self.assertIn('setWorkflowStage(item, "copied")',self.js)
        self.assertIn('rememberCopied(item)',self.js)
        self.assertIn('showCopyUndo(item, previousStage)',self.js)
        self.assertIn('["all","trending","global","india","saved"].includes(selectedView)',self.js)
        self.assertIn('["copied","archived"].includes(workflowStage(item))',self.js)
        self.assertIn('selectedView === "copied" && workflowStage(item) !== "copied"',self.js)
        self.assertIn('const copiedLibraryKey = "signaldesk:copied-library:v1"',self.js)
        self.assertIn('localStorage.setItem(copiedLibraryKey',self.js)
        self.assertIn('records.push(copy)',self.js)
        self.assertIn('setWorkflowStage(item, previousStage)',self.js)
        self.assertIn("not posted to X",self.js)

    def test_no_unapproved_publishing_or_spending_and_shared_cron_only(self):
        self.assertNotIn("api.x.com",self.js)
        self.assertNotIn("innerHTML",self.js)
        self.assertNotIn('method: "POST"',self.js)
        self.assertNotIn('method:"POST"',self.js)
        self.assertIn('export const CRON = "*/15 * * * *"',self.worker)
        self.assertNotIn("api.openai.com",self.worker)
        self.assertNotIn("api.x.com",self.worker)
        self.assertIn('if (request.method!=="GET" && request.method!=="HEAD")',self.worker)
        self.assertIn('const MAX_INDIA_STORIES = 50;',self.worker)
        for filename in (".github/workflows/deploy-news-collector.yml",
                         ".github/workflows/build-news-dashboard.yml"):
            text=(ROOT/filename).read_text("utf-8")
            self.assertIn("'config/sources.json'",text)


if __name__=="__main__":
    unittest.main()
