"""Private local editorial inbox backed by GitHub Issues.

Run with: python -m newsbot.editorial_inbox --repo owner/private-repo
Requires the GitHub CLI (gh) authenticated with access to that private repo.

Only bind localhost. Never accept tokens from browsers, never publish to X,
never call AI. Issue edits preserve publisher evidence and publication denial.
"""
from __future__ import annotations

import argparse
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import subprocess
from urllib.parse import urlsplit

from .editorial_inbox_ui import PAGE

REPO_NAME = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
EDIT_REGION = re.compile(
    r"(### My edited X post \(manual only\)\s*\n)(.*?)"
    r"(\n\*\*Publication approval:\*\* NOT GRANTED\b)", re.S
)
PRE = re.compile(r"<pre>(.*?)</pre>", re.S)
SOURCE_URL = re.compile(r"\*\*Source URL:\*\*\s*(https?://[^\s<]+)")
TITLE = re.compile(r"\*\*Candidate \d+:\*\*\s*(.+)")
EXCERPT = re.compile(r"\*\*(P\d+) — publisher excerpt:\*\*\s*<pre>(.*?)</pre>", re.S)
AI_RESPONSE = re.compile(
    r"## Copilot's full analysis \(untrusted, reference only\)\s*<pre>(.*?)</pre>", re.S
)
CLEAN_POST = re.compile(
    r"## Clean proposed X post \(manual editing required\)\s*<pre>(.*?)</pre>", re.S
)
WARN_FORMAT = re.compile(r"\*\*Automated format check:\*\*\s*([^\n]+)")
WARN_EVIDENCE = re.compile(r"\*\*Automated evidence precheck:\*\*\s*([^\n]+)")
ALLOWED = ("pending", "reviewed", "rejected")
STATUS_LABELS = {"reviewed": "ai-editor-reviewed", "rejected": "ai-editor-rejected"}
MAX_ISSUES = 400  # Fail closed on incomplete result rather than hiding draft history.
MAX_BODY_BYTES = 40000
MAX_REQUEST_BYTES = 3600
MAX_DRAFT_CHARS = 1200


class IssueConflict(Exception):
    """Local editor revision is stale; reload before overwriting Issue."""


class IssueValidationError(Exception):
    """Invalid request or unexpected GitHub Issue structure."""


def gh_json(args: list[str], *, input_data: str | None = None) -> object:
    """GitHub authentication stays in the OS-owned gh CLI; no PAT in UI."""
    cmd = ["gh", *args]
    result = subprocess.run(cmd, input=input_data, check=True, capture_output=True,
                            text=True, timeout=35)
    return json.loads(result.stdout)


def repo_is_private(repo: str, gh=gh_json) -> bool:
    if not REPO_NAME.fullmatch(repo):
        raise IssueValidationError("Expected owner/private-repository")
    info = gh(["api", f"repos/{repo}"])
    return isinstance(info, dict) and info.get("private") is True


def issue_status(labels: list[dict]) -> str:
    names = {x.get("name") for x in labels if isinstance(x, dict)}
    if STATUS_LABELS["rejected"] in names:
        return "rejected"
    if STATUS_LABELS["reviewed"] in names:
        return "reviewed"
    return "pending"


def issue_revision(issue: dict) -> str:
    """Changes to draft text or labels invalidate stale browser saves."""
    labels = sorted(x["name"] for x in issue.get("labels", [])
                    if isinstance(x, dict) and isinstance(x.get("name"), str))
    # gh issue list (GraphQL) and gh api (REST) can format timestamps
    # differently. Only compare editable contents and status labels.
    value = json.dumps([issue.get("body"), labels],
                       ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bounded(value: str, maximum: int = 1500) -> str:
    return value[:maximum].strip()


def match_text(pattern: re.Pattern, body: str, *, limit: int = 1500) -> str:
    found = pattern.search(body)
    return bounded(html.unescape(found.group(1)), limit) if found else ""


def read_edited_post(body: str) -> str:
    match = EDIT_REGION.search(body)
    if not match:
        return ""
    pre = PRE.search(match.group(2))
    return bounded(html.unescape(pre.group(1)), MAX_DRAFT_CHARS) if pre else ""


def parse_issue(issue: dict) -> dict:
    """Extract only bounded editorial data. Untrusted Issue HTML is not rendered."""
    body = issue.get("body")
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise IssueValidationError("Unexpected private AI Draft Issue body")
    if ("publication_authorized=false, publishable=false, auto_sent=false" not in body
            or "**Publication approval:** NOT GRANTED" not in body
            or not EDIT_REGION.search(body)):
        raise IssueValidationError("Refusing Issue without private review safeguards")
    raw_url = match_text(SOURCE_URL, body, limit=2500)
    parts = urlsplit(raw_url)
    if parts.scheme != "https" or not parts.hostname or any(c.isspace() for c in raw_url):
        raise IssueValidationError("Unsafe original source URL in Issue")
    # Preserve the exact original article URL; history uses this, not edited text.
    excerpts = [{
        "ref": match.group(1),
        "text": bounded(html.unescape(match.group(2)), 250),
    } for match in list(EXCERPT.finditer(body))[:4]]
    warnings = [x for x in (
        match_text(WARN_FORMAT, body, limit=380),
        match_text(WARN_EVIDENCE, body, limit=380),
    ) if x]
    return {
        "number": int(issue["number"]),
        "title": match_text(TITLE, body, limit=400) or bounded(str(issue.get("title", "")), 400),
        "url": str(issue.get("html_url") or issue.get("url") or ""),
        "source_url": raw_url,
        "proposed_draft": match_text(CLEAN_POST, body, limit=MAX_DRAFT_CHARS),
        "edited_draft": read_edited_post(body),
        "excerpts": excerpts,
        "analysis": match_text(AI_RESPONSE, body, limit=4000),
        "warnings": warnings,
        "status": issue_status(issue.get("labels", [])),
        "revision": issue_revision(issue),
        "human_verified": False,
        "publication_approved": False,
    }


def list_inbox(repo: str, gh=gh_json) -> list[dict]:
    issues = gh(["issue", "list", "--repo", repo, "--state", "all", "--label",
                 "ai-draft-review", "--limit", str(MAX_ISSUES),
                 "--json", "number,title,body,url,labels,updatedAt"])
    if not isinstance(issues, list) or len(issues) >= MAX_ISSUES:
        raise IssueValidationError("Private review Issue list is incomplete or malformed")
    return sorted((parse_issue(issue) for issue in issues),
                  key=lambda item: item["number"], reverse=True)


def build_updated_body(body: str, draft: str) -> str:
    if not isinstance(draft, str) or len(draft) > MAX_DRAFT_CHARS:
        raise IssueValidationError("Edited draft must be <= 1200 characters")
    if any(ord(c) < 32 and c not in "\n\t" for c in draft):
        raise IssueValidationError("Edited draft contains control characters")
    if "publication_authorized=false, publishable=false, auto_sent=false" not in body:
        raise IssueValidationError("Original Issue has no publication safety marker")
    if "**Publication approval:** NOT GRANTED" not in body:
        raise IssueValidationError("Original Issue is missing publication denial")
    if not EDIT_REGION.search(body):
        raise IssueValidationError("Issue has no editable review section")
    # Write only the editor's own paragraph; NEVER modify publisher evidence
    # or turn publication approval on.
    # Escape Markdown marker asterisks as entities too, so editor text
    # cannot masquerade as the fixed Publication approval boundary.
    escaped = html.escape(draft, quote=True).replace("*", "&#42;")
    editor = ("<pre>" + escaped + "</pre>" if draft.strip()
              else "> [No reviewed post entered]")
    # A callback prevents backslashes from being interpreted as regex
    # substitutions and preserves the immutable review/publishing marker.
    result, count = EDIT_REGION.subn(
        lambda match: match.group(1) + editor + match.group(3),
        body, count=1)
    if count != 1 or len(result.encode("utf-8")) > MAX_BODY_BYTES:
        raise IssueValidationError("Invalid updated review body")
    return result


def save_review(repo: str, number: int, revision: str, draft: str, status: str,
                gh=gh_json) -> dict:
    """Atomically persist editor text and reviewed/rejected labels to GitHub."""
    if not isinstance(number, int) or not 1 <= number <= 1_000_000_000:
        raise IssueValidationError("Invalid Issue number")
    if status not in ALLOWED:
        raise IssueValidationError("Unknown editorial status")
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise IssueValidationError("Invalid editor revision")
    if status == "reviewed" and not draft.strip():
        raise IssueValidationError("Reviewed drafts require text and human verification")
    issue = gh(["api", f"repos/{repo}/issues/{number}"])
    if not isinstance(issue, dict):
        raise IssueValidationError("GitHub Issue unavailable")
    labels = issue.get("labels", [])
    names = {x.get("name") for x in labels if isinstance(x, dict)}
    if "ai-draft-review" not in names:
        raise IssueValidationError("Only private AI Draft Issues may be edited")
    parse_issue(issue)  # enforce size, source, publication denial, and editor section
    if issue_revision(issue) != revision:
        raise IssueConflict("Issue changed in GitHub; refresh before saving")
    new_body = build_updated_body(issue["body"], draft)
    # Create the requested label only on an explicit user Save. No labels
    # are created merely by opening/reading the dashboard.
    if status != "pending":
        existing = gh(["api", f"repos/{repo}/labels?per_page=100"])
        if not isinstance(existing, list) or len(existing) >= 100:
            raise IssueValidationError("Cannot verify existing status labels safely")
        label = STATUS_LABELS[status]
        if label not in {x.get("name") for x in existing if isinstance(x, dict)}:
            gh(["api", "--method", "POST", f"repos/{repo}/labels",
                "--input", "-"], input_data=json.dumps({
                    "name": label,
                    "color": "2F855A" if status == "reviewed" else "C34D63",
                    "description": "Private editorial decision — never X publication approval",
                }))
    remaining = sorted((names - set(STATUS_LABELS.values())) |
                       ({STATUS_LABELS[status]} if status != "pending" else set()))
    data = {"body": new_body, "labels": remaining}
    updated = gh(["api", "--method", "PATCH", f"repos/{repo}/issues/{number}",
                  "--input", "-"], input_data=json.dumps(data, ensure_ascii=False))
    # GitHub is authoritative; reload to confirm label+body rather than claiming
    # success based solely on PATCH HTTP completion.
    if not isinstance(updated, dict) or updated.get("body") != new_body:
        raise IssueValidationError("Issue update was not confirmed")
    if issue_status(updated.get("labels", [])) != status:
        raise IssueValidationError("Issue status label was not confirmed")
    return parse_issue(updated)


def handler_factory(repo: str, csrf: str, gh=gh_json):
    """Private localhost HTTP interface: JSON-only, same-origin writes."""
    class EditorialHandler(BaseHTTPRequestHandler):
        server_version = "PrivateEditorialInbox/1.0"

        def log_message(self, fmt, *args):
            # Never echo draft text, query strings or GitHub credentials to logs.
            pass

        def send_data(self, code: int, payload: dict | list | str,
                      *, content_type: str = "application/json; charset=utf-8"):
            data = (payload.encode("utf-8") if isinstance(payload, str) else
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'none'; base-uri 'none'; "
                             "frame-ancestors 'none'; form-action 'none'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def allowed_host(self) -> bool:
            host = self.headers.get("Host", "")
            return host in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }

        def reject(self, code: int, detail: str):
            self.send_data(code, {"error": detail})

        def do_GET(self):
            if not self.allowed_host():
                return self.reject(403, "Local host only")
            if self.path == "/":
                return self.send_data(200, PAGE, content_type="text/html; charset=utf-8")
            if self.path == "/dashboard.js":
                from .editorial_inbox_ui import SCRIPT
                return self.send_data(200, SCRIPT, content_type="application/javascript; charset=utf-8")
            if self.path == "/dashboard.css":
                from .editorial_inbox_ui import STYLE
                return self.send_data(200, STYLE, content_type="text/css; charset=utf-8")
            if self.path == "/api/inbox":
                try:
                    data = list_inbox(repo, gh)
                    return self.send_data(200, {"issues": data, "csrf": csrf,
                                                "publication_authorized": False})
                except (IssueValidationError, subprocess.CalledProcessError,
                        subprocess.TimeoutExpired, ValueError):
                    return self.reject(503, "Cannot read complete private GitHub inbox")
            return self.reject(404, "Not found")

        def do_POST(self):
            if not self.allowed_host():
                return self.reject(403, "Local host only")
            if self.path != "/api/review":
                return self.reject(404, "Not found")
            origin = self.headers.get("Origin", "")
            if origin not in {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            } or self.headers.get("X-CSRF-Token") != csrf:
                return self.reject(403, "Same-origin local review required")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.reject(415, "JSON required")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.reject(400, "Invalid request size")
            if not 0 < length <= MAX_REQUEST_BYTES:
                return self.reject(413, "Review request too large")
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(request, dict):
                    raise IssueValidationError("Invalid review object")
                updated = save_review(repo, request.get("number"),
                                      request.get("revision"), request.get("draft"),
                                      request.get("status"), gh)
                return self.send_data(200, {"issue": updated, "saved": True,
                                            "publication_authorized": False})
            except IssueConflict:
                return self.reject(409, "GitHub Issue changed; refresh before saving")
            except (IssueValidationError, ValueError, TypeError):
                return self.reject(422, "Invalid review; no changes saved")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return self.reject(503, "GitHub failed; check account access and retry")
    return EditorialHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Private GitHub-backed local editorial inbox")
    parser.add_argument("--repo", default="varadachiru/x-news-automation")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    if not repo_is_private(args.repo):
        parser.error("Refusing to display drafts from a public or inaccessible repo")
    # Check the GitHub API and editor's access before opening a browser.
    list_inbox(args.repo)
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 handler_factory(args.repo, secrets.token_urlsafe(32)))
    print(f"Private editorial inbox: http://127.0.0.1:{args.port}")
    print("Requires gh CLI authentication; only this computer can connect.")
    print("Editorial GitHub Issues only. No AI or X posting. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
