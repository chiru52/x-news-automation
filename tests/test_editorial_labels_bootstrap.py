"""Safety checks for the one-time GitHub editorial label bootstrap.

This checks the intent of the workflow without network/API access or publishing.
"""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/bootstrap-editorial-labels.yml"


class EditorialLabelsBootstrapTests(unittest.TestCase):
    def test_scope_and_trigger_are_narrow(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("branches: [main]", text)
        self.assertIn("paths:\n      - '.github/workflows/bootstrap-editorial-labels.yml'", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("  issues: write", text)
        self.assertIn("  contents: read", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)

    def test_only_editorial_decision_labels_are_created(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        create_lines = [line.strip() for line in text.splitlines()
                        if line.strip().startswith("gh label create ")]
        self.assertEqual(create_lines, [
            "gh label create ai-editor-reviewed --repo \"$GH_REPO\" \\",
            "gh label create ai-editor-rejected --repo \"$GH_REPO\" \\",
        ])
        self.assertIn("test \"$GH_REPO\" = \"varadachiru/x-news-automation\"", text)
        self.assertIn("All drafts remain unchanged.", text)
        self.assertNotIn("gh issue edit", text)
        self.assertNotIn("gh issue close", text)
        self.assertNotIn("X_API_KEY", text)
        self.assertNotIn("PUBLISH_ENABLED", text)


if __name__ == "__main__":
    unittest.main()
