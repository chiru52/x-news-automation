"""Stage 43 static safety and accessibility tests (no external API)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase2StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "dashboard/index.html").read_text("utf-8")
        cls.script = (ROOT / "dashboard/app.js").read_text("utf-8")
        cls.module = (ROOT / "dashboard/studio.mjs").read_text("utf-8")
        cls.styles = (ROOT / "dashboard/styles.css").read_text("utf-8")

    def test_editor_and_research_controls_are_accessible(self):
        html = self.page
        for fragment in ('class="studio-open"', 'class="research-open"',
                         'aria-label="Post writing studio"', 'class="studio-panel"',
                         'class="studio-tone"', 'class="studio-use"',
                         'aria-label="Why this story matters research guide"',
                         'class="research-questions"', 'class="research-notes"',
                         'maxlength="1200"'):
            self.assertIn(fragment, html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('No-cost writing starters · not AI-generated', html)
        self.assertIn('It is not a full article analysis or fact check.', html)
        self.assertIn('Check the original article', html)

    def test_working_client_loads_module_and_applies_drafts(self):
        js = self.script
        self.assertIn('from "./studio.mjs"', js)
        self.assertIn('const variants = postStarters(item)', js)
        self.assertIn('rememberEdit(item.id, selected.text, suggestion)', js)
        self.assertIn('showEditor(true)', js)
        self.assertIn('currentDraft() !== selected.text', js)
        self.assertIn('window.confirm(', js)
        self.assertIn('guide.questions.map(', js)
        self.assertIn('li.textContent = question', js)
        self.assertIn('researchLink.href = guide.source_url', js)
        self.assertIn('previewText.textContent = guide.preview', js)
        self.assertIn('draftFromNotes(notes.value, guide.source_url)', js)
        self.assertIn('rememberEdit(item.id, draft, suggestion)', js)
        self.assertIn('class="studio-panel"', self.page)
        self.assertIn('.studio-panel,.research-panel{', self.styles)

    def test_notes_only_in_browser_with_length_limit(self):
        js = self.script
        self.assertIn('const noteKey = "signaldesk:research-notes:v1"', js)
        self.assertIn('localStorage.setItem(noteKey', js)
        self.assertIn('note.slice(0,1200)', js)
        self.assertIn('notes.addEventListener("input"', js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn('method: "POST"', js)
        self.assertNotIn("api.x.com", js)
        self.assertNotIn("api.openai.com", self.module)
        self.assertNotIn("fetch(", self.module)
        self.assertNotIn("XMLHttpRequest", self.module)

    def test_deployment_includes_helper_module(self):
        exporter = (ROOT / "newsbot/dashboard_export.py").read_text("utf-8")
        self.assertIn('"studio.mjs"', exporter)
        tests = (ROOT / ".github/workflows/tests.yml").read_text("utf-8")
        build = (ROOT / ".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn("node --test tests/signaldesk-studio.test.mjs", tests)
        self.assertIn("node --test tests/signaldesk-studio.test.mjs", build)
        self.assertIn("PUBLISH_ENABLED: 'false'", build)
        self.assertNotIn("secrets.OPENAI_API_KEY", build)
        self.assertNotIn("secrets.X_", build)
        self.assertNotIn("copilot -p", build)


if __name__ == "__main__":
    unittest.main()
