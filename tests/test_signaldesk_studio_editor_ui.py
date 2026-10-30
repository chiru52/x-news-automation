"""SignalDesk X Content Studio remains an offline, user-reviewed copying workflow."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ContentStudioUITests(unittest.TestCase):
    def test_editable_thread_and_source_review_controls(self):
        html=(ROOT/"dashboard/index.html").read_text("utf-8")
        js=(ROOT/"dashboard/app.js").read_text("utf-8")
        styles=(ROOT/"dashboard/styles.css").read_text("utf-8")
        self.assertIn('class="studio-format-thread"',html)
        self.assertIn('class="studio-format-post active"',html)
        self.assertEqual(html.count('class="studio-thread-input"'),3)
        self.assertEqual(html.count('class="studio-thread-copy"'),3)
        self.assertIn('class="studio-thread-reviewed"',html)
        self.assertIn('type="checkbox"',html)
        self.assertIn('function renderThread()',js)
        self.assertIn('threadReviewCheckbox.checked=false',js)
        self.assertIn('if(!threadReviewCheckbox.checked||!reviewThread(',js)
        self.assertIn('rememberThread(item.id,threadParts,defaultThread)',js)
        self.assertIn('copy.disabled = !text.trim() || estimate > 280;',js)
        self.assertIn('if(approximateXLength(post)>280)',js)
        self.assertIn('signaldesk:thread-drafts:v1',js)
        self.assertIn('.studio-thread-input',styles)
    def test_no_x_publishing_or_unverified_ai_claims(self):
        js=(ROOT/"dashboard/app.js").read_text("utf-8")
        studio=(ROOT/"dashboard/studio.mjs").read_text("utf-8")
        self.assertNotIn("api.x.com",js)
        self.assertNotIn("api.x.com",studio)
        self.assertNotIn("api.openai.com",studio)
        self.assertIn("nothing",js.lower())
        self.assertIn("Publisher: ",studio)
        self.assertIn('reviewThread(parts,sourceUrl)',studio)

if __name__=="__main__":
    unittest.main()
