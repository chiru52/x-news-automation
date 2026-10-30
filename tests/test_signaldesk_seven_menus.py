"""SignalDesk's eight-menu navigation and mutual-exclusion news contract."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class SimplifiedNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.js=(ROOT/"dashboard/app.js").read_text("utf-8")
        cls.selectors=(ROOT/"dashboard/news-sections.mjs").read_text("utf-8")

    def test_eight_main_menu_items_in_requested_order(self):
        nav=self.html.split('<nav class="nav-items" aria-label="Main navigation">',1)[1].split("</nav>",1)[0]
        views=re.findall(r'data-view="([^"]+)"',nav)
        self.assertEqual(views, ["all","trending","global","india","workflow","copied","saved","archive"])
        self.assertIn("All stories",nav)
        self.assertIn("Trending news",nav)
        self.assertIn("Global news",nav)
        self.assertIn("India news",nav)
        self.assertIn("Archive",nav)
        self.assertNotIn("X-ready drafts",nav)

    def test_sidebar_topic_section_removed_but_optional_content_filters_remain(self):
        self.assertNotIn('class="sidebar-section-label topic-label"',self.html)
        self.assertNotIn('aria-label="News categories"',self.html)
        self.assertNotIn('class="nav-item topic-item"',self.html)
        self.assertIn('aria-label="Filter category"',self.html)

    def test_drafts_preserved_and_discoverable_under_workflow(self):
        self.assertIn('data-stage="drafts"',self.html)
        self.assertIn('Prepared drafts',self.html)
        self.assertIn('selectedView === "workflow" && selectedStage === "drafts"',self.js)
        self.assertIn('selectedView === "workflow" && selectedStage !== "drafts"',self.js)
        self.assertIn('item.kind !== "draft"',self.js)
        self.assertIn('...data.drafts.map(',self.js)
        self.assertIn('item.kind === "draft" && !item.history_only',self.js)

    def test_region_news_feed_excludes_drafts_and_copied_history(self):
        self.assertIn('["all","trending","global","india"].includes(selectedView) && item.kind !== "news"',self.js)
        self.assertIn('selectedView === "global" && isIndiaNews(item)',self.js)
        self.assertIn('selectedView === "india" && !isIndiaNews(item)',self.js)
        self.assertIn('["all","trending","global","india","saved"].includes(selectedView)',self.js)
        self.assertIn('["copied","archived"].includes(workflowStage(item))',self.js)
        self.assertIn('if (["all","trending","global","india"].includes(selectedView))',self.js)
        self.assertIn('canonicalStoryUrl(item.source_url)',self.js)

    def test_trending_uses_one_combined_geographical_pool(self):
        self.assertIn('return eligibleNews(records, workflowStage, canonicalStoryUrl)',self.js)
        self.assertIn('return topNews(availableNews(), 5)',self.js)
        self.assertIn('function isIndiaNews(item) { return isIndiaArticle(item); }',self.js)
        self.assertIn('view !== "india" || isIndiaArticle(item)',self.selectors)
        self.assertIn('view !== "global" || !isIndiaArticle(item)',self.selectors)

    def test_fall_back_and_safety_preserved(self):
        self.assertIn('fetch("./data.json",{cache:"no-store"})',self.js)
        self.assertIn('Array.isArray(dynamic.india_news)',self.js)
        self.assertIn('const copiedLibraryKey = "signaldesk:copied-library:v1"',self.js)
        self.assertNotIn('method: "POST"',self.js)
        self.assertNotIn("api.x.com",self.js)
        self.assertNotIn("api.openai.com",self.selectors)
        self.assertNotIn("fetch(",self.selectors)


if __name__=="__main__":
    unittest.main()
