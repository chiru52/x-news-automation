"""Save a completed Copilot editorial preview as a private, editable GitHub Issue.

This is GitHub-only issue management. No X, Buffer, AI, or publishing API.
Runs in a separate GitHub Actions job, without Copilot credentials.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from pathlib import Path

LABEL = "ai-draft-review"

def suggested_clean_draft(body: str) -> str:
    """Extract the bounded, escaped clean copy from the trusted review format."""
    marker = "## Clean proposed X post (manual editing required)"
    section = body.split(marker, 1)
    if len(section) != 2:
        return ""
    before_next_section = section[1].split("\n## ", 1)[0]
    match = re.search(r"<pre>(.*?)</pre>", before_next_section, re.S)
    if not match:
        return ""
    draft = html.unescape(match.group(1)).strip()
    if not draft or len(draft) > 2000:
        return ""
    return draft



def run_gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True,
                          timeout=30).stdout.strip()


def save_private_review(repo: str, run_id: str, body_file: Path) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[0-9]{1,24}", run_id):
        raise ValueError("Invalid Actions run identifier")
    if not os.environ.get("GH_TOKEN"):
        raise ValueError("GH_TOKEN is required for private GitHub Issue")
    body = body_file.read_text(encoding="utf-8")
    if (len(body.encode("utf-8")) > 40_000 or
            "**REVIEW ONLY" not in body or
            "publication_authorized=false, publishable=false, auto_sent=false" not in body):
        raise ValueError("Refusing to file an unsafe or unexpectedly large draft")
    # Prevent accidental publication of private AI drafts if the repo is
    # ever made public. This check is performed immediately before issue API.
    if run_gh(["api", f"repos/{repo}", "--jq", ".private"]) != "true":
        raise ValueError("AI Drafts require a PRIVATE repository")

    title = f"AI Draft — Copilot Run {run_id}"
    existing = json.loads(run_gh([
        "issue", "list", "--repo", repo, "--state", "all",
        "--limit", "1000", "--json", "title,url",
    ]))
    for item in existing:
        if item.get("title") == title:
            # Never overwrite prior manual editor changes, even on rerun.
            return str(item["url"])

    run_link = f"https://github.com/{repo}/actions/runs/{run_id}"
    clean = suggested_clean_draft(body)
    # Do not prefill a risky draft in the manual editor. Review remains visible
    # above, but suspicious citation/quantity gaps or format failures require
    # the human to actively resolve them before copying any text.
    evidence_warning = "**Automated evidence precheck:** Needs manual attention:" in body
    format_warning = "**Automated format check:** Needs corrections:" in body
    needs_attention = evidence_warning or format_warning
    if needs_attention:
        editor_start = ("> [Resolve the flagged evidence/format gaps against the "
                        "original publisher and independent sources before writing an X post]")
    else:
        editor_start = ("<pre>" + html.escape(clean, quote=True) + "</pre>" if clean else
                        "> [No usable draft — editor must write and verify]")
    with body_file.open("a", encoding="utf-8") as out:
        out.write("\n\n---\n**Original GitHub Actions run:** " + run_link +
                  "\n\n- [ ] Read article and corroborate material claims\n"
                  "- [ ] Edit the proposed text before any manual posting\n"
                  "- [ ] Set aside / reject\n\n"
                  "### My edited X post (manual only)\n\n"
                  + editor_start + "\n\n"
                  "**Publication approval:** NOT GRANTED\n")
    run_gh(["label", "create", LABEL, "--repo", repo, "--color", "8A6FE3",
            "--description", "Private human-review AI news drafts", "--force"])
    result = run_gh([
        "issue", "create", "--repo", repo, "--title", title,
        "--label", LABEL, "--body-file", str(body_file),
    ])
    expected = f"https://github.com/{repo}/issues/"
    if not result.startswith(expected):
        raise RuntimeError("Unexpected GitHub Issue creation output")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--summary")
    args = parser.parse_args()
    url = save_private_review(args.repo, args.run_id, Path(args.draft))
    print("Private AI Draft Issue available:", url)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as out:
            out.write("## Private AI Draft created\n\n"
                      f"**[Open the editable AI draft]({url})**\n\n"
                      f"[Browse all AI drafts](https://github.com/{args.repo}/issues?q=is%3Aissue%20label%3A{LABEL})\n\n"
                      "Nothing has been verified, scheduled, or posted to X.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
