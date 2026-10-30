"""Topic writer is in workflow, source-aware, local, and manual-copy only."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TopicWriterUITests(unittest.TestCase):
    def test_topic_writer_controls_and_no_sidebar_change(self):
        html=(ROOT/"dashboard/index.html").read_text()
        js=(ROOT/"dashboard/app.js").read_text()
        css=(ROOT/"dashboard/styles.css").read_text()
        nav=html.split('<nav class="nav-items"',1)[1].split("</nav>",1)[0]
        self.assertNotIn("Topic Writer",nav)
        for control in ("topic-writer-toggle","topic-writer","topic-writer-subject",
                "topic-writer-angle","topic-writer-insight","topic-writer-source",
                "topic-writer-build","topic-writer-draft","topic-writer-length",
                "topic-writer-status","topic-writer-reviewed","topic-writer-copy"):
            self.assertIn('id="'+control+'"',html)
        self.assertIn('topicWriterOpen=false',js)
        self.assertIn('function openTopicWriter()',js)
        self.assertIn('class="studio-topic"',html)
        self.assertIn('function openTopicWriterFromStory(item)',js)
        self.assertIn('function closeTopicWriter()',js)
        self.assertIn('composeTopicDraft({',js)
        self.assertIn('reviewTopicDraft(topicDraft.value',js)
        self.assertIn('topicReviewed.checked=false;',js)
        self.assertIn('topicCopy.disabled=!review.valid||!topicReviewed.checked',js)
        self.assertIn('signaldesk:topic-writer:v1',js)
        self.assertIn('handleCopy(topicDraft.value.trim(),topicCopy',js)
        self.assertIn('.topic-writer-grid{display:grid',css)
        self.assertIn('@media(max-width:900px){.topic-writer-grid{grid-template-columns:1fr}',css)

    def test_no_new_external_ai_or_x_publishing(self):
        js=(ROOT/"dashboard/app.js").read_text()
        helper=(ROOT/"dashboard/perspective.mjs").read_text()
        self.assertNotIn('api.openai.com',helper)
        self.assertNotIn('api.x.com',helper)
        self.assertNotIn('fetch(',helper)
        self.assertNotIn('innerHTML',js)
        self.assertNotIn('method:"POST"',helper)

if __name__=="__main__":
    unittest.main()
