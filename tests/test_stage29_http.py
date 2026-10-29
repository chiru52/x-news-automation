"""Stage 29 local HTTP smoke tests. Loopback only; mocked GitHub, no internet."""
import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import threading
import unittest

from newsbot.editorial_inbox import handler_factory, issue_revision


REPO = "varadachiru/x-news-automation"
SOURCE = "https://www.theverge.com/example"
MARKER = "<!-- publication_authorized=false, publishable=false, auto_sent=false -->"
BODY = (
    "# Copilot single-story editorial preview\n"
    "**Candidate 9:** Example AI news story\n"
    "**Source URL:** " + SOURCE + "\n"
    "## Clean proposed X post (manual editing required)\n"
    "<pre>Proposed source-based draft " + SOURCE + "</pre>\n"
    "**Automated format check:** Basic fields found; factual accuracy NOT assessed\n"
    "**P1 — publisher excerpt:**\n<pre>Source excerpt, unverified.</pre>\n"
    + MARKER + "\n"
    "### My edited X post (manual only)\n\n<pre>Proposed source-based draft " +
    SOURCE + "</pre>\n"
    "**Publication approval:** NOT GRANTED\n"
)


class GitHubStub:
    def __init__(self):
        self.issue = {"number": 27, "title": "AI Draft — Copilot Run 1",
                      "html_url": f"https://github.com/{REPO}/issues/27",
                      "url": f"https://github.com/{REPO}/issues/27",
                      "body": BODY,
                      "labels": [{"name": "ai-draft-review"}]}
        self.patches = []

    def __call__(self, args, *, input_data=None):
        if args == ["api", f"repos/{REPO}"]:
            return {"private": True}
        if args[:2] == ["issue", "list"]:
            return [copy.deepcopy(self.issue)]
        if args == ["api", f"repos/{REPO}/issues/27"]:
            return copy.deepcopy(self.issue)
        if args[-1] == f"repos/{REPO}/labels?per_page=100":
            return [{"name": "ai-editor-reviewed"}, {"name": "ai-editor-rejected"}]
        if "PATCH" in args:
            data = json.loads(input_data)
            self.issue["body"] = data["body"]
            self.issue["labels"] = [{"name": x} for x in data["labels"]]
            self.patches.append(copy.deepcopy(data))
            return copy.deepcopy(self.issue)
        raise AssertionError(f"Unexpected mock GitHub call: {args}")


class LocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.gh = GitHubStub()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(REPO, "local-csrf-test-token", self.gh))
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, *, body=None, headers=None):
        client = HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            client.request(method, path, body=body, headers=headers or {})
            response = client.getresponse()
            data = response.read().decode("utf-8")
            return response.status, dict(response.getheaders()), data
        finally:
            client.close()

    def test_private_dashboard_html_css_js_and_no_cache(self):
        for path, content_type in (("/", "text/html"), ("/dashboard.css", "text/css"),
                                   ("/dashboard.js", "application/javascript")):
            code, hdrs, content = self.request("GET", path)
            self.assertEqual(code, 200)
            self.assertIn(content_type, hdrs["Content-Type"])
            self.assertEqual(hdrs["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", hdrs["Content-Security-Policy"])
            self.assertTrue(content)

    def test_reads_existing_issue_without_modifying_it(self):
        code, hdrs, body = self.request("GET", "/api/inbox")
        self.assertEqual(code, 200)
        info = json.loads(body)
        self.assertEqual(info["csrf"], "local-csrf-test-token")
        self.assertEqual(len(info["issues"]), 1)
        self.assertEqual(info["issues"][0]["source_url"], SOURCE)
        self.assertFalse(info["publication_authorized"])
        self.assertFalse(self.gh.patches)

    def test_review_status_and_edit_saved_to_private_git_hub_only(self):
        _code, _hdrs, body = self.request("GET", "/api/inbox")
        issue = json.loads(body)["issues"][0]
        edit = "Revised source-checked claim. " + SOURCE
        payload = json.dumps({
            "number": 27, "revision": issue["revision"],
            "status": "reviewed", "draft": edit,
        })
        code, hdrs, result = self.request(
            "POST", "/api/review", body=payload,
            headers={"Origin": f"http://127.0.0.1:{self.port}",
                     "Content-Type": "application/json",
                     "X-CSRF-Token": "local-csrf-test-token"})
        self.assertEqual(code, 200)
        answer = json.loads(result)
        self.assertTrue(answer["saved"])
        self.assertFalse(answer["publication_authorized"])
        self.assertEqual(answer["issue"]["edited_draft"], edit)
        self.assertEqual(answer["issue"]["status"], "reviewed")
        self.assertEqual(len(self.gh.patches), 1)
        self.assertIn(MARKER, self.gh.patches[0]["body"])

    def test_cross_origin_or_missing_csrf_never_saves(self):
        _code, _hdrs, body = self.request("GET", "/api/inbox")
        revision = json.loads(body)["issues"][0]["revision"]
        payload = json.dumps({
            "number": 27, "revision": revision,
            "status": "reviewed", "draft": "Potential post",
        })
        for headers in (
            {"Origin": "https://evil.example", "Content-Type": "application/json",
             "X-CSRF-Token": "local-csrf-test-token"},
            {"Origin": f"http://127.0.0.1:{self.port}",
             "Content-Type": "application/json"},
            {"Origin": f"http://127.0.0.1:{self.port}",
             "Content-Type": "text/plain", "X-CSRF-Token": "local-csrf-test-token"},
        ):
            code, _headers, _body = self.request(
                "POST", "/api/review", body=payload, headers=headers)
            self.assertIn(code, (403, 415))
        self.assertEqual(len(self.gh.patches), 0)

    def test_stale_revision_returns_409_without_overwrite(self):
        stale = issue_revision(self.gh.issue)
        self.gh.issue["body"] += "\nAnother editor's saved changes"
        data = json.dumps({"number": 27, "revision": stale,
                           "draft": "Stale edit", "status": "pending"})
        code, _headers, msg = self.request(
            "POST", "/api/review", body=data,
            headers={"Origin": f"http://127.0.0.1:{self.port}",
                     "Content-Type": "application/json",
                     "X-CSRF-Token": "local-csrf-test-token"})
        self.assertEqual(code, 409)
        self.assertIn("refresh", msg.lower())
        self.assertFalse(self.gh.patches)

    def test_host_header_is_restricted(self):
        code, _hdrs, body = self.request(
            "GET", "/api/inbox", headers={"Host": "remote-attacker.example:1234"})
        self.assertEqual(code, 403)
        self.assertNotIn("local-csrf-test-token", body)


if __name__ == "__main__":
    unittest.main()
