"""Regression checks for browser-only editing in public SignalDesk cards.

No browser secrets, server editing, X API, GitHub issue writes or publishing.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SignalDeskInlineEditTests(unittest.TestCase):
    def test_editor_controls_are_real_and_accessible(self):
        page = (ROOT / "dashboard/index.html").read_text("utf-8")
        self.assertIn('class="compose-panel" hidden', page)
        self.assertIn('class="compose-input"', page)
        self.assertIn('maxlength="1000"', page)
        self.assertIn('class="edit-button"', page)
        self.assertIn('aria-expanded="false"', page)
        self.assertIn('class="reset-edit"', page)
        self.assertIn('Copy post', page)
        self.assertIn('Edits stay in this browser', page)

    def test_copy_uses_live_edited_content_not_original_closure(self):
        source = (ROOT / "dashboard/app.js").read_text("utf-8")
        self.assertIn('const editsKey = "signaldesk:edits:v1";', source)
        self.assertIn('const edits = new Map();', source)
        self.assertIn('localStorage.setItem(editsKey, JSON.stringify(Object.fromEntries(edits)))', source)
        self.assertIn('rememberEdit(item.id, editor.value.slice(0, 1000), suggestion)', source)
        self.assertIn('copy.addEventListener("click", () => handleCopy(currentDraft().trim(), copy, () => {', source)
        self.assertIn('setWorkflowStage(item, "copied")', source)
        self.assertIn('rememberEdit(item.id, suggestion, suggestion)', source)
        self.assertIn('tag.textContent = edits.has(item.id)', source)
        self.assertIn('copy.disabled = !text.trim()', source)

    def test_no_server_or_x_write_path(self):
        source = (ROOT / "dashboard/app.js").read_text("utf-8")
        self.assertNotIn("innerHTML", source)
        self.assertNotIn("api.x.com", source)
        self.assertNotIn("github.com/api", source)
        self.assertNotIn('method: "POST"', source)
        self.assertNotIn("fetch(", source.replace('fetch("./data.json", {cache: "no-store"})', ""))
        self.assertIn('postText.textContent = text', source)

    def test_local_editor_looks_consistent(self):
        styles = (ROOT / "dashboard/styles.css").read_text("utf-8")
        self.assertIn(".compose-panel{", styles)
        self.assertIn(".compose-input{", styles)
        self.assertIn(".draft-actions{", styles)


if __name__ == "__main__":
    unittest.main()
