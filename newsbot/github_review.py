"""Render private GitHub editorial reviews. This module NEVER publishes to X."""
import argparse
import html
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo


def escape(value):
    raw = html.escape(re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip(), quote=False)
    return re.sub(r"([\\*_{}\[\]()#+.!|>~-])", r"\\\1", raw)


def link_url(url):
    url = str(url or "").strip()
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.netloc or any(c.isspace() for c in url):
        return None
    return quote(url, safe="/:?&=%#@+~,-._!")


def review_date(queue):
    at = datetime.fromisoformat(queue["generated_at"])
    if at.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return at.astimezone(ZoneInfo("Europe/Stockholm")).date().isoformat()


def check_safety(queue):
    if queue.get("publishing_enabled") is not False:
        raise ValueError("Unsafe queue: publishing must be disabled")
    if any(item.get("publishable") is not False for item in queue.get("articles", [])):
        raise ValueError("Unsafe article: publishing must be disabled")


def render(queue):
    check_safety(queue)
    items = queue.get("articles", [])
    lines = [
        "# News editorial review — " + review_date(queue), "",
        "> **PRIVATE EDITORIAL WORKSHEET.** Nothing here is fact-checked, approved",
        "> for publication, scheduled, or sent to X. Checking boxes never authorizes posting.",
        "",
        "Candidates: " + str(len(items)) + " · Mode: "
        + ("preview" if queue.get("preview_only") else "daily"), "",
        "Edit this Issue using the GitHub web editor; use comments to discuss.",
        "Open source articles and verify claims before writing your own post.", "",
    ]
    if not items:
        lines += ["No fresh candidate stories in this run.", ""]
    for index, item in enumerate(items, 1):
        lines += [
            "## " + str(index) + ". " + escape(item.get("title")),
            "", "**Category (unverified):** " + escape(item.get("category")),
            "**Publisher:** " + escape(item.get("source")),
            "**Relevance heuristic:** " + escape((item.get("relevance") or {}).get("score", "n/a")),
        ]
        source_url = link_url(item.get("link"))
        lines.append("**Original story:** [Open article](" + source_url + ")" if source_url
                     else "**Original story:** No valid source URL — skip")
        lines += [
            "", "- [ ] Read original article and verified important claims",
            "- [ ] Shortlisted for editorial writing (NOT publication approval)",
            "- [ ] Skipped / rejected", "",
            "**Source-attributed suggested post — not verified:**", "",
        ]
        post = str(item.get("suggested_post") or item.get("draft") or "")
        lines += ["> " + escape(line) if line else ">"
                  for line in post.splitlines()]
        details = item.get("writing") or {}
        checks = details.get("verification_warnings") or []
        if checks:
            lines += ["", "**Checks before reuse:**", ""]
            lines += ["- " + escape(note) for note in checks]
        lines += ["", "**My reviewed X draft (replace this placeholder):**", "",
                  "> [Write your own verified text here]", "",
                  "**Publication approval:** NOT GRANTED", "", "---", ""]
    lines += ["<!-- Editorial only. publication_authorized=false -->", ""]
    return "\n".join(lines)


def open_or_reuse_issue(queue, repo, directory):
    check_safety(queue)
    if not queue.get("articles"):
        print("No candidates: no Issue created")
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository")
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("GH_TOKEN required for GitHub editorial issue")
    title = "News editorial review — " + review_date(queue)
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all",
         "--limit", "1000", "--json", "title,url"],
        check=True, capture_output=True, text=True)
    items = json.loads(result.stdout)
    url = next((item["url"] for item in items if item.get("title") == title), None)
    directory.mkdir(parents=True, exist_ok=True)
    if not url:
        bodyfile = directory / "github_issue_body.md"
        bodyfile.write_text(render(queue), encoding="utf-8")
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--title", title,
             "--body-file", str(bodyfile)],
            check=True, capture_output=True, text=True)
        url = result.stdout.strip()
        if not url.startswith("https://github.com/"):
            raise RuntimeError("Unexpected GitHub Issue link")
        print("Created editorial Issue:", url)
    else:
        print("Reusing editable Issue; existing human edits preserved:", url)
    (directory / "github_issue_link.txt").write_text(url + "\n", encoding="utf-8")
    return url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["summary", "issue"])
    ap.add_argument("--queue", default="output/review_queue.json")
    ap.add_argument("--directory", default="output")
    opts = ap.parse_args()
    path = Path(opts.queue)
    if not path.exists():
        print("No queue to review")
        return 0 if opts.action == "summary" else 1
    queue = json.loads(path.read_text(encoding="utf-8"))
    directory = Path(opts.directory)
    check_safety(queue)
    if opts.action == "issue":
        open_or_reuse_issue(queue, os.environ.get("GITHUB_REPOSITORY", ""), directory)
    else:
        issuefile = directory / "github_issue_link.txt"
        url = issuefile.read_text(encoding="utf-8").strip() if issuefile.exists() else ""
        summary = render(queue)
        if url:
            summary = "**[Open editable daily review Issue](" + url + ")**\n\n" + summary
        target = os.environ.get("GITHUB_STEP_SUMMARY")
        if target:
            with open(target, "a", encoding="utf-8") as f:
                f.write(summary + "\n")
        else:
            print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
