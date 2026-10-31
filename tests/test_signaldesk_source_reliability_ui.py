"""No public source diagnostics sidebar or change in manual X publishing."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class SourceReliabilityUITests(unittest.TestCase):
    def test_compact_coverage_note_and_no_new_nav(self):
        html=(ROOT/"dashboard/index.html").read_text()
        js=(ROOT/"dashboard/app.js").read_text()
        worker=(ROOT/"news-collector/worker.mjs").read_text()
        nav=html.split('<nav class="nav-items"',1)[1].split('</nav>',1)[0]
        self.assertNotIn("Source health",nav)
        self.assertNotIn("Feed diagnostics",nav)
        self.assertIn('function boundedFeedCoverage(value)',js)
        self.assertIn('coverage:boundedFeedCoverage(dynamic.coverage)',js)
        self.assertIn('" feeds supplied recent stories"',js)
        self.assertIn('recent headlines retained during outages',js)
        self.assertIn('recoverRecentStories(',worker)
        self.assertIn('if(freshSelected.length+freshIndia.length < MIN_STORIES)',worker)
        self.assertNotIn("api.x.com",worker)
        self.assertNotIn("api.openai.com",worker)
        self.assertIn('if (request.method!=="GET" && request.method!=="HEAD")',worker)

if __name__=="__main__":
    unittest.main()
