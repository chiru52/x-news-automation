"""Read-only X publishing preflight for a manually reviewed GitHub AI Draft.

No X credentials, POST requests, publishing authorization, or GitHub writes.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

REPO = "varadachiru/x-news-automation"
MARKER = "publication_authorized=false, publishable=false, auto_sent=false"
DENIAL = "**Publication approval:** NOT GRANTED"
EDIT = re.compile(
    r"(?ms)^### My edited X post \(manual only\)[ \t]*\n"
    r"(?P<edited>.*?)"
    r"(?=^\*\*Publication approval:\*\* NOT GRANTED[ \t]*$)"
)
SOURCE = re.compile(r"(?m)^\*\*Source URL:\*\*[ \t]*(https://[^\s<>]+)[ \t]*$")
CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PreflightBlocked(ValueError):
    """A safe failure that never includes private issue text or credentials."""


def validate_issue(issue: dict, number: int) -> dict:
    if not isinstance(issue, dict) or issue.get("number") != number:
        raise PreflightBlocked("Issue number mismatch")
    if issue.get("pull_request"):
        raise PreflightBlocked("Pull requests are not editorial drafts")

    labels = {label.get("name") if isinstance(label, dict) else label
              for label in issue.get("labels", [])}
    if "ai-draft-review" not in labels:
        raise PreflightBlocked("Issue lacks AI Draft label")
    if "ai-editor-reviewed" not in labels or "ai-editor-rejected" in labels:
        raise PreflightBlocked("Draft must be Reviewed and not Rejected")

    body = issue.get("body")
    if not isinstance(body, str) or len(body.encode("utf-8")) > 40000:
        raise PreflightBlocked("Invalid or oversized private draft")
    if MARKER not in body or body.count(DENIAL) != 1 or "**REVIEW ONLY" not in body:
        raise PreflightBlocked("Non-publication protections are missing")

    source = SOURCE.search(body)
    if not source:
        raise PreflightBlocked("Original publisher URL is missing")
    url = source.group(1)
    address = urlparse(url)
    if not address.hostname or address.username or address.password:
        raise PreflightBlocked("Publisher URL is unsafe")

    edits = list(EDIT.finditer(body))
    if len(edits) != 1:
        raise PreflightBlocked("Exactly one manual editor section is required")
    match = re.fullmatch(r"<pre>([\s\S]*?)</pre>", edits[0].group("edited").strip())
    if not match:
        raise PreflightBlocked("Please enter the reviewed post in the manual editor block")
    draft = html.unescape(match.group(1)).strip()
    if not draft or len(draft) > 280 or CONTROLS.search(draft):
        raise PreflightBlocked("Draft is empty, unsafe, or exceeds conservative 280 characters")
    if url not in draft:
        raise PreflightBlocked("Reviewed post must retain original publisher URL")

    return {"number": number, "url": f"https://github.com/{REPO}/issues/{number}",
            "draft": draft, "length": len(draft), "publication_authorized": False}


def render(preview: dict) -> str:
    draft = preview["draft"]
    # Choose a Markdown fence long enough to contain any editorial backticks.
    fences = re.findall(r"\x60+", draft)
    size = max(4, 1 + max((len(s) for s in fences), default=0))
    fence = chr(96) * size
    return (
        "## X news — manual-only posting preflight\n\n"
        f"**Draft:** [Issue #{preview['number']}]({preview['url']})\n\n"
        "**Status:** Reviewed, NOT approved for publishing\n\n"
        f"**Conservative length:** {preview['length']}/280 (X links count differently)\n\n"
        "**Copyable preview after your own fact-check:**\n\n"
        f"{fence}text\n{draft}\n{fence}\n\n"
        "**NOT PUBLISHED.** There is no X API access here. Reviewed labels never "
        "authorize publishing. Posting in X, if desired, is a separate manual step.\n"
    )


def github_json(path: str) -> dict:
    p = subprocess.run(["gh", "api", path], check=True, capture_output=True,
                       text=True, timeout=30)
    return json.loads(p.stdout)


def main() -> int:
    try:
        raw = os.environ.get("ISSUE_NUMBER", "")
        if not re.fullmatch(r"[1-9][0-9]{0,7}", raw):
            raise PreflightBlocked("Provide a valid positive AI Draft Issue number")
        if os.environ.get("GITHUB_REPOSITORY") != REPO:
            raise PreflightBlocked("Unexpected repository")
        if not os.environ.get("GH_TOKEN"):
            raise PreflightBlocked("Read-only GitHub token unavailable")
        repo = github_json(f"repos/{REPO}")
        if repo.get("private") is not True or repo.get("full_name") != REPO:
            raise PreflightBlocked("Repository must remain private")
        preview = validate_issue(github_json(f"repos/{REPO}/issues/{int(raw)}"), int(raw))
        summary = render(preview)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
                file.write(summary)
        else:
            print("Editorial preflight passed, no GitHub summary available. No X post made.")
        return 0
    except (PreflightBlocked, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            json.JSONDecodeError, OSError) as error:
        safe = (str(error) if isinstance(error, PreflightBlocked)
                else "Private GitHub read failed")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
                file.write("## X preflight blocked\n\n" + safe +
                           "\n\nNo X posting attempted.\n")
        print("X editorial preflight blocked: " + safe, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
