"""Review Desk stays in My Workflow and does not publish to X."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ReviewDeskUITests(unittest.TestCase):
    def test_review_in_workflow_not_separate_sidebar(self):
        html=(ROOT/"dashboard/index.html").read_text()
        js=(ROOT/"dashboard/app.js").read_text()
        nav=html.split('<nav class="nav-items"',1)[1].split("</nav>",1)[0]
        self.assertNotIn("Review desk",nav)
        self.assertIn('id="review-desk-toggle"',html)
        self.assertIn('id="review-desk" class="review-desk"',html)
        self.assertIn('id="review-select-left"',html)
        self.assertIn('id="review-select-right"',html)
        self.assertIn('id="review-text-left"',html)
        self.assertIn('id="review-text-right"',html)
        self.assertIn('class="review-add"',html)
        self.assertIn('function openReviewDesk(itemId="")',js)
        self.assertIn('function closeReviewDesk()',js)
        self.assertIn('function renderReviewDesk()',js)
        self.assertIn('reviewCandidates(records,workflowStage,edits,threadEdits)',js)
        self.assertIn('reviewPost(textarea.value,item.source_url)',js)
        self.assertIn('rememberEdit(item.id,textarea.value.slice(0,1000),original)',js)
        self.assertIn('handleCopy(textarea.value.trim(),copy,()=>{',js)
        self.assertIn('setWorkflowStage(item,"copied")',js)
    def test_no_auto_posting_or_paid_integration(self):
        js=(ROOT/"dashboard/app.js").read_text()
        helper=(ROOT/"dashboard/review-desk.mjs").read_text()
        styles=(ROOT/"dashboard/styles.css").read_text()
        self.assertNotIn("api.x.com",js)
        self.assertNotIn("api.x.com",helper)
        self.assertNotIn("api.openai.com",helper)
        self.assertNotIn("innerHTML",helper)
        self.assertIn('.review-grid{display:grid;grid-template-columns:repeat(2',styles)
        self.assertIn('@media(max-width:900px){.review-grid{grid-template-columns:1fr}',styles)

if __name__=="__main__":
    unittest.main()
