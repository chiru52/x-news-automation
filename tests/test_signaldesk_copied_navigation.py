"""Regression guard for copied articles and clear filters in India News."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CopiedIndiaNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "dashboard/index.html").read_text("utf-8")
        cls.js = (ROOT / "dashboard/app.js").read_text("utf-8")
        cls.css = (ROOT / "dashboard/styles.css").read_text("utf-8")

    def test_marking_copied_from_india_navigates_to_real_copied_library(self):
        handler = self.js.split('stageSelect.addEventListener("change", () => {',1)[1].split(
            '  const save = node.querySelector(".save-button")',1)[0]
        self.assertIn('const previousStage = workflowStage(item)',handler)
        self.assertIn('setWorkflowStage(item, stage)',handler)
        self.assertIn('if (stage === "copied") rememberCopied(item)',handler)
        self.assertIn('showCopyUndo(item, previousStage, false)',handler)
        self.assertIn('openCopiedLibrary()',handler)
        self.assertIn('if (stage === "copied" && selectedView !== "copied"',handler)
        self.assertIn('selectedView !== "workflow"',handler)
        self.assertIn('function openCopiedLibrary()', self.js)
        self.assertIn('setView("copied")',self.js)

    def test_view_copied_shortcut_and_undo_preserve_original_india_section(self):
        self.assertIn('id="view-copied"',self.page)
        self.assertIn('id="empty-view-copied"',self.page)
        self.assertIn('id="undo-copy"',self.page)
        self.assertIn('copyUndo = {id:item.id, previousStage, returnView:selectedView}',self.js)
        self.assertIn('fromClipboard = true',self.js)
        self.assertIn("Clipboard unchanged; nothing posted to X",self.js)
        self.assertIn('$("view-copied").addEventListener("click", openCopiedLibrary)',self.js)
        self.assertIn('$("empty-view-copied").addEventListener("click", openCopiedLibrary)',self.js)
        self.assertIn('setWorkflowStage(item, previousStage)',self.js)
        self.assertIn('setView(returnView)',self.js)
        self.assertIn("Nothing was posted to X",self.js)

    def test_empty_india_shows_copied_shortcut_and_only_real_filter_reset(self):
        section = self.js.split('  $("empty").hidden = list.length > 0;',1)[1].split(
            'function parseItem(',1)[0]
        self.assertIn('copiedIndiaCount',section)
        self.assertIn('selectedView !== "india" || copiedIndiaCount === 0',section)
        self.assertIn('$("clear-filters").hidden = !filtersActive',section)
        self.assertIn('No available India stories',section)
        self.assertIn('Your copied India articles are safe in Copied Articles',section)
        self.assertIn('No India stories match these filters',section)

    def test_clear_filters_only_resets_active_section(self):
        handler = self.js.split('$("clear-filters").addEventListener("click", () => {',1)[1].split(
            '$("view-copied").addEventListener',1)[0]
        self.assertIn('$("search-input").value = "";',handler)
        self.assertIn('query = "";',handler)
        self.assertIn('selectedCategory = "all";',handler)
        self.assertIn('selectedStage = "all";',handler)
        self.assertIn('render();',handler)
        self.assertNotIn('setView("all")',handler)
        self.assertNotIn('selectedView = "all"',handler)

    def test_copy_is_still_local_only_with_no_hidden_auto_posting(self):
        self.assertIn('await navigator.clipboard.writeText(post)',self.js)
        self.assertIn('onCopied();',self.js)
        self.assertIn('rememberCopied(item)',self.js)
        self.assertIn('const copiedLibraryKey = "signaldesk:copied-library:v1"',self.js)
        self.assertNotIn('api.x.com',self.js)
        self.assertNotIn('method: "POST"',self.js)
        self.assertIn('.copy-undo-actions',self.css)
        self.assertIn('.empty-actions',self.css)


if __name__ == "__main__":
    unittest.main()
