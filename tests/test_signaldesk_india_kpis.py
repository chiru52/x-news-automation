"""Region-specific KPI counters must use the current news section, not draft cards."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RegionKpisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.script=(ROOT/"dashboard/app.js").read_text("utf-8")

    def test_top_kpis_have_dynamic_geographic_labels(self):
        for kind in ("news","trending","ready"):
            self.assertIn(f'id="count-{kind}-label"', self.page)
            self.assertIn(f'id="count-{kind}"', self.page)
        for label in ("India news stories", "India trending picks", "India ready to copy",
                      "Global news stories", "Global trending picks", "Global ready to copy"):
            self.assertIn(label, self.script)

    def test_available_news_excludes_copied_archived_and_history(self):
        section=self.script.split("function availableNews()",1)[1].split(
            "function trendingPicks()",1)[0]
        self.assertIn("eligibleNews(records, workflowStage, canonicalStoryUrl)",section)
        helper=(ROOT/"dashboard/news-sections.mjs").read_text("utf-8")
        self.assertIn('item.kind !== "news"', helper)
        self.assertIn("item.history_only", helper)
        self.assertIn('["copied","archived"].includes(stageOf(item))',helper)
        self.assertIn("seen.add(key)",helper)

    def test_kpi_switches_between_global_india_and_trending(self):
        section=self.script.split("function filteredNewsForCurrentView()",1)[1].split(
            "function setView(view)",1)[0]
        self.assertIn("newsInSection(availableNews(), selectedView, trendingPicks())",section)
        helper=(ROOT/"dashboard/news-sections.mjs").read_text("utf-8")
        self.assertIn('view !== "india" || isIndiaArticle(item)',helper)
        self.assertIn('view !== "global" || !isIndiaArticle(item)',helper)
        self.assertIn('view !== "trending" || trendingIds.has(item.id)',helper)
        self.assertIn('selectedCategory === "all" || item.category === selectedCategory',section)
        self.assertIn("item.title,item.description,item.publisher,item.post",section)
        self.assertIn("global.length",section)
        self.assertIn("india.length",section)
        self.assertIn("news.length",section)
        self.assertIn("trending.length",section)
        self.assertIn('"nav-global-count"',section)
        self.assertIn('"nav-india-count"',section)

    def test_view_and_topic_filters_keep_counts_accurate(self):
        self.assertIn("function setView(view)",self.script)
        self.assertIn("function setCategory(category)",self.script)
        self.assertIn("function render() {\n  updateCounts();",self.script)
        self.assertIn("selectedView = view;",self.script)
        self.assertIn("selectedCategory = category;",self.script)
        self.assertIn('selectedView === "global" && isIndiaNews(item)',self.script)
        self.assertNotIn("api.x.com",self.script)
        self.assertNotIn("innerHTML",self.script)
        self.assertNotIn('method: "POST"',self.script)


if __name__=="__main__":
    unittest.main()
