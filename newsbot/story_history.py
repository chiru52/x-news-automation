"""Read-only history of private Copilot Issues and deterministic story de-duplication.

No AI call, no posting, no changes to Issues, and no output of GitHub tokens.
Existing AI Issues #19/#21 store source URL and title in the markdown body.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

URL_LINE = re.compile(r"(?m)^\*\*Source URL:\*\*\s*(https?://[^\s<]+)")
TITLE_LINE = re.compile(r"(?m)^\*\*Candidate\s+\d+:\*\*\s*(.+?)\s*$")
# No fuzzy/semantic AI similarity here: conservatively skip only strong matches.
TOKENS = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(("a", "an", "and", "at", "by", "for", "from", "in",
                       "is", "of", "on", "the", "to", "with", "new", "latest",
                       "reports", "reportedly", "says", "said"))
MAX_HISTORY_ISSUES = 1000
MAX_STORY_AGE_HOURS = 36


def normalize_url(url: str) -> str:
    """Canonical URL without tracking tokens, fragments, or trailing slash."""
    if not isinstance(url, str):
        return ""
    url = html.unescape(url).strip().rstrip(".,;")
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return ""
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return ""
        host = parsed.hostname.lower()
    except ValueError:
        return ""
    query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {
            "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source", "guccounter",
            ".tsrc", "tsrc", "cmpid", "guce_referrer",
        }
    ]
    return urlunsplit((parsed.scheme.lower(), host,
                       parsed.path.rstrip("/") or "/", urlencode(query), ""))


def title_terms(title: str) -> set[str]:
    """Conservative title matching; short generic headlines never fuzzy-match."""
    return {word for word in TOKENS.findall(str(title).lower())
            if len(word) > 1 and word not in STOPWORDS}


def story_duplicate(item: dict, seen: list[dict]) -> bool:
    """URL equivalence or high-overlap headline; avoid broad topic suppression."""
    uri = normalize_url(str(item.get("link") or ""))
    terms = title_terms(str(item.get("title") or ""))
    for previous in seen:
        old_uri = normalize_url(str(previous.get("link") or ""))
        if uri and old_uri and uri == old_uri:
            return True
        earlier = title_terms(str(previous.get("title") or ""))
        intersection = len(terms & earlier)
        union = len(terms | earlier)
        if intersection >= 4 and union and intersection / union >= 0.85:
            return True
    return False


def history_from_issues(issues: list[dict]) -> dict:
    """Parse source and title from previously generated private AI-Draft Issues.

    Fail closed if a labeled AI Draft Issue lacks a recoverable source URL;
    otherwise an edited/malformed Issue could silently defeat duplicate checks.
    """
    if not isinstance(issues, list) or len(issues) >= MAX_HISTORY_ISSUES:
        raise ValueError("Private draft history is missing or too large for safe preflight")
    stories: list[dict] = []
    for issue in issues:
        if not isinstance(issue, dict) or not isinstance(issue.get("body"), str):
            raise ValueError("Private AI Issue has malformed or unreadable body")
        body = issue["body"]
        url = URL_LINE.search(body)
        title = TITLE_LINE.search(body)
        if not url or not normalize_url(url.group(1)):
            raise ValueError("A private AI Issue is missing its original Source URL")
        # Legacy issues #19 and #21 already use the Candidate and Source URL markers.
        stories.append({
            "link": normalize_url(url.group(1)),
            "title": html.unescape(title.group(1).strip())[:400] if title else "",
        })
    return {"stories": stories, "count": len(issues), "review_only": True}


def read_history(repo: str, runner=subprocess.run) -> dict:
    """Read existing private AI Draft Issues. Any API failure stops before AI."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository")
    # Do not use untrusted Issue body as shell syntax; argv avoids shell expansion.
    result = runner([
        "gh", "issue", "list", "--repo", repo, "--state", "all",
        "--label", "ai-draft-review", "--limit", str(MAX_HISTORY_ISSUES),
        "--json", "body,title",
    ], check=True, capture_output=True, text=True, timeout=35)
    data = json.loads(result.stdout)
    return history_from_issues(data)


# Selection is an editorial heuristic, never a statement of article quality
# or factual correctness. Prefer new products, technology and useful SaaS.
QUALITY_HINTS = re.compile(
    r"\b(?:artificial intelligence|ai|llm|model|machine learning|"
    r"cybersecurity|security|developer|robotics|cloud|semiconductor|"
    r"software|saas|automation|open source|open-source|gpu)\b", re.I
)
LAUNCH_HINTS = re.compile(r"\b(?:launch(?:es|ed)?|unveil(?:s|ed)?|releas(?:es|ed)?|"
                          r"introduc(?:es|ed)?|ships?|built|builds?|open.source)\b", re.I)
ROUTINE_MARKET_HINTS = re.compile(
    r"\b(?:stock flat|share price|stock price|q[1-4] earnings|quarterly earnings|"
    r"futures|pre.market|market open|market close)\b", re.I
)
FUNDING_HINTS = re.compile(r"\b(?:raises? \$|series [a-f]|funding round)\b", re.I)


def editorial_priority(item: dict) -> int:
    """Bounded story preference, based only on unverified RSS metadata."""
    category = str(item.get("category", "")).lower()
    headline = str(item.get("title", ""))[:400]
    base = {"technology": 45, "saas": 38, "markets": 3}.get(category, 0)
    return (base + (13 if QUALITY_HINTS.search(headline) else 0) +
            (15 if LAUNCH_HINTS.search(headline) else 0) -
            (14 if FUNDING_HINTS.search(headline) else 0) -
            (28 if ROUTINE_MARKET_HINTS.search(headline) else 0))


def choose_story_order(queue: dict, preferred_index: int, history: dict,
                       strategy: str = "preferred_first") -> list[int]:
    """Order unused fresh stories; optionally prioritize technology/SaaS first.

    Use the *existing* RSS topical/relevance filter. Fail closed on malformed
    history. Already-selected news is at most 36h old, by design.
    """
    if (not isinstance(history, dict) or history.get("review_only") is not True
            or not isinstance(history.get("stories"), list)):
        raise ValueError("Safe GitHub AI draft history is required")
    if strategy not in ("preferred_first", "quality_first"):
        raise ValueError("Unknown editorial selection strategy")
    articles = queue["articles"]
    if not isinstance(articles, list) or not 1 <= preferred_index <= len(articles) <= 9:
        raise ValueError("Invalid preview article index")
    now = datetime.fromisoformat(str(queue["generated_at"]).replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("Preview timestamp lacks timezone")
    now = now.astimezone(timezone.utc)
    choices = []
    for idx, item in enumerate(articles, 1):
        if story_duplicate(item, history["stories"]):
            continue
        published = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
        if published.tzinfo is None:
            continue
        age = now - published.astimezone(timezone.utc)
        if not -timedelta(minutes=10) <= age <= timedelta(hours=MAX_STORY_AGE_HOURS):
            continue
        raw_score = (item.get("relevance") or {}).get("score", 0)
        # Only use numerical scores; reject NaN, infinite or absurd values.
        if type(raw_score) not in (int, float) or not -10000 <= raw_score <= 10000:
            raw_score = 0
        choices.append((idx, float(raw_score), published.timestamp(), editorial_priority(item)))
    if strategy == "quality_first":
        # Keep source relevance secondary to the tech/SaaS preference.
        ranked = sorted(choices, key=lambda v: (-v[3], -v[1], -v[2], v[0]))
        return [idx for idx, *_ in ranked]
    ranked = sorted(choices, key=lambda v: (-v[1], -v[2], v[0]))
    order = [idx for idx, *_ in ranked]
    if preferred_index in order:
        order.remove(preferred_index)
        return [preferred_index] + order
    return order


def main() -> int:
    parser = argparse.ArgumentParser(description="Read only prior private AI Drafts")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = read_history(args.repo)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    # Print counts only: don't echo private Issue text or URLs into job logs.
    print(f"Loaded {out['count']} private AI Drafts for deduplication (read only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
