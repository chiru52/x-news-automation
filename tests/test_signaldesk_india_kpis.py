"""India News KPI counters must describe the current section, not the global feed."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IndiaKpisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.script=(ROOT/"dashboard/app.js").read_text("utf-8")

    def test_top_kpi_labels_are_dynamically_identified(self):
        for kind in ("news","trending","ready"):
            self.assertIn(f'id="count-{kind}-label"', self.page)
            self.assertIn(f'id="count-{kind}"', self.page)
        for label in ("India news stories", "India trending picks", "India ready to copy"):
            self.assertIn(label, self.script)

    def test_india_counts_exclude_global_copied_archived_history(self):
        self.assertIn("function indiaNewsForCurrentView()", self.script)
        section=self.script.split("function indiaNewsForCurrentView()",1)[1].split(
            "function updateCounts()",1)[0]
        self.assertIn("isIndiaNews(item)", section)
        self.assertIn("!item.history_only", section)
        self.assertIn('["copied","archived"].includes(workflowStage(item))', section)
        self.assertIn('selectedCategory === "all" || item.category === selectedCategory', section)
        self.assertIn("item.title,item.description,item.publisher,item.post", section)

    def test_kpi_switches_between_global_and_india_scopes(self):
        section=self.script.split("function updateCounts()",1)[1].split(
            "function setView(",1)[0]
        self.assertIn('selectedView === "india"', section)
        self.assertIn("indiaView ? indiaNews.length : news", section)
        self.assertIn("indiaView ? indiaNews.length : news", section)
        self.assertIn("Math.min(5,indiaView ? indiaNews.length : news)", section)
        self.assertIn('indiaNews.filter(item => workflowStage(item) === "ready").length', section)
        self.assertIn('records.filter(r => workflowStage(r) === "ready").length', section)
        self.assertIn('"nav-india-count"', section)
        self.assertIn('"nav-all-count"', section)

    def test_changes_to_view_and_topic_refresh_kpis(self):
        self.assertIn('function setView(view)', self.script)
        self.assertIn('function setCategory(category)', self.script)
        self.assertIn('function render() {\n  updateCounts();', self.script)
        self.assertIn('selectedView = view;', self.script)
        self.assertIn('selectedCategory = category;', self.script)
        self.assertIn('selectedView === "india" && !isIndiaNews(item)', self.script)
        self.assertNotIn("api.x.com", self.script)
        self.assertNotIn("innerHTML", self.script)
        self.assertNotIn('method: "POST"', self.script)


if __name__ == "__main__":
    unittest.main()
