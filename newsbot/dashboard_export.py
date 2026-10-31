"""Export a private static SignalDesk dashboard bundle from safe review data.

Exposes only allowed display fields to a public news page. No X publishing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .editorial_inbox import IssueValidationError, parse_issue
from .news_quality import unique_stories
from .source_context import preview_from_rss
from .regions import explicit_india_sources, is_india_article

REPO = "varadachiru/x-news-automation"
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "dashboard"
INDIA_SOURCES = explicit_india_sources(json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8")))
CATEGORIES = frozenset(("technology", "saas", "markets"))
MAX_ISSUES = 200
MAX_ITEMS = 200
SAFE_TEXT = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(value, limit=500):
    if not isinstance(value, str):
        return ""
    return SAFE_TEXT.sub(" ", value).strip()[:limit]


def source_url(value):
    url = clean(value, 2000)
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username or
            parts.password or any(c.isspace() for c in url)):
        return ""
    return url


def safe_image_url(value):
    """Only public HTTPS publisher-supplied article thumbnails, never scrape pages."""
    import re
    if (not isinstance(value, str) or not 0 < len(value) <= 1400 or
            any(c.isspace() or ord(c) < 32 or c in ('<', '>', '"', "'", chr(92)) for c in value)):
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not host or len(host) > 250 or
                parts.username or parts.password or parts.port is not None or
                host == "localhost" or host.endswith(".localhost") or
                host.endswith((".local", ".internal", ".test")) or
                ":" in host or re.fullmatch(r"\d+(?:\.\d+){3}", host) or
                re.search(r"\.(?:svgz?|gif|ico|html?|js|xml|pdf)$", parts.path, re.I)):
            return ""
        return value
    except (ValueError, AttributeError):
        return ""


def categorize(text, fallback="technology"):
    candidate = clean(text, 500).lower()
    if any(phrase in candidate for phrase in ("stock", "earnings", "shares", "trading",
                                            "market", "interest rate", "bank", "nasdaq",
                                            "nifty", "wall street")):
        return "markets"
    if any(phrase in candidate for phrase in ("startup", "saas", "funding", "series a",
                                            "venture capital", "subscription", "seed round")):
        return "saas"
    return fallback if fallback in CATEGORIES else "technology"



def bounded_trend(value: object) -> dict:
    """Accept only a bounded computed heuristic, never arbitrary RSS text."""
    default = {"score": 0, "coverage_feeds": 1, "reason": "Headline relevance and recency"}
    if not isinstance(value, dict) or not value:
        return default
    score = value.get("score")
    count = value.get("coverage_feeds")
    reason = value.get("reason")
    if (type(score) is not int or not 0 <= score <= 100 or
            type(count) is not int or not 1 <= count <= 20 or
            reason not in ("Headline relevance and recency",
                           "Fresh headline about a reported development",
                           f"Headline relevance and {count} matching RSS feeds",
                           f"Headline relevance and {count} matching publishers")):
        raise ValueError("Unexpected or unsafe editorial signal metadata")
    return {"score": score, "coverage_feeds": count, "reason": reason}


def read_news(queue: dict, field: str = "articles") -> list[dict]:
    """Only use source-attributed review suggestions, never untrusted HTML."""
    if not isinstance(queue, dict) or queue.get("publishing_enabled") is not False:
        raise ValueError("Unsafe queue: publishing must be disabled")
    if field not in ("articles", "india_articles") or not isinstance(queue.get(field, []), list):
        raise ValueError("News queue has no articles")
    out, seen = [], set()
    for article in queue.get(field, [])[:MAX_ITEMS]:
        if not isinstance(article, dict) or article.get("publishable") is not False:
            raise ValueError("Unsafe or malformed news article")
        url = source_url(article.get("link"))
        title = clean(article.get("title"), 260)
        if not url or not title or url in seen:
            continue
        seen.add(url)
        category = article.get("category")
        if category not in CATEGORIES:
            category = categorize(title)
        suggestion = clean(article.get("suggested_post") or article.get("draft"), 1000)
        source_preview = preview_from_rss(article.get("summary"), title)
        out.append({
            "id": hashlib.sha256(url.encode()).hexdigest()[:24],
            "title": title,
            "description": "Publisher report. Verify all claims before sharing.",
            "source_preview": source_preview,
            "image_url": safe_image_url(article.get("image_url") or article.get("thumbnail")),
            "context_status": "rss_preview" if source_preview else "headline_only",
            "publisher": clean(article.get("source"), 100),
            "source_url": url,
            "post": suggestion,
            "category": category,
            "region": "india" if is_india_article(article, INDIA_SOURCES) else "global",
            "published_at": clean(article.get("published_at"), 50),
            "status": "unverified",
            "trend_score": bounded_trend(article.get("trend", {}))["score"],
            "coverage_feeds": bounded_trend(article.get("trend", {}))["coverage_feeds"],
            "trend_reason": bounded_trend(article.get("trend", {}))["reason"],
        })
    return unique_stories(out)


def read_drafts(issues: list[dict]) -> list[dict]:
    """Export only approved-for-display *fields*, not evidence or issue bodies."""
    if not isinstance(issues, list) or len(issues) > MAX_ISSUES:
        raise ValueError("Invalid or oversized private Issue list")
    out, seen = [], set()
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        names = {x.get("name") if isinstance(x, dict) else x
                 for x in issue.get("labels", [])}
        if "ai-draft-review" not in names:
            continue
        # Strict parser verifies non-publication markers and publisher URL.
        try:
            parsed = parse_issue(issue)
        except (IssueValidationError, TypeError, KeyError, ValueError) as exc:
            raise ValueError("Unsafe private AI Issue: export stopped") from exc
        url = source_url(parsed.get("source_url"))
        num = parsed.get("number")
        if not url or not isinstance(num, int) or num < 1 or num in seen:
            raise ValueError("Invalid private draft identity or URL")
        seen.add(num)
        if parsed["status"] == "rejected":
            continue
        text = clean(parsed.get("edited_draft") or parsed.get("proposed_draft"), 1000)
        title = clean(parsed.get("title"), 260)
        if not title:
            raise ValueError("AI Issue is missing title")
        out.append({
            "id": str(num),
            "title": title,
            "description": "AI-assisted draft. Verify the original reporting before copying.",
            "publisher": urlsplit(url).hostname or "",
            "source_url": url,
            "post": text,
            "category": categorize(title),
            "updated_at": clean(issue.get("updated_at") or issue.get("updatedAt"), 50),
            "status": parsed["status"],
        })
    return unique_stories(sorted(out, key=lambda x: int(x["id"]), reverse=True))


def fetch_private_issues() -> list[dict]:
    """Use the ephemeral GitHub Actions token, never expose it to the site."""
    import os
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("GitHub Actions token required")
    def get(path):
        response = subprocess.run(["gh", "api", path], text=True, capture_output=True,
                                  check=True, timeout=30)
        return json.loads(response.stdout)
    repo = get(f"repos/{REPO}")
    if repo.get("private") is not True or repo.get("full_name") != REPO:
        raise ValueError("Refusing to export from a non-private or unexpected repository")
    output = []
    for page in range(1, 4):
        chunk = get(f"repos/{REPO}/issues?state=all&labels=ai-draft-review&per_page=100&page={page}")
        if not isinstance(chunk, list):
            raise ValueError("GitHub Issues returned unexpected data")
        output.extend(chunk)
        if len(output) > MAX_ISSUES:
            raise ValueError("Too many editorial drafts: abort rather than truncate")
        if len(chunk) < 100:
            return output
    raise ValueError("Issue history exceeds maximum export size")



# Explicit public contract. Never export private GitHub issue bodies, full
# publisher evidence, analysis, transcripts, URLs into private issues or tokens.
PUBLIC_TOP = {"schema_version","generated_at","news","india_news","drafts","warnings"}
PUBLIC_NEWS = {"id","title","description","publisher","source_url","post","category","region","published_at","status","trend_score","coverage_feeds","trend_reason","source_preview","context_status","image_url"}
PUBLIC_DRAFT = {"id","title","description","publisher","source_url","post","category","updated_at","status"}
PRIVATE_MARKERS = (
    "github_pat_", "ghp_", "gho_", "ghs_", "ghu_", "ghr_",
    "-----begin private key", "-----begin rsa private key",
    "cloudflare_api_token", "github_editor_token", "gh_token=",
    "x_api_secret", "access_aud", "publication_authorized=",
    "## copilot's full analysis", "## supporting publisher excerpts",
    "<!--", "<pre>", "</pre>",
)


def validate_public_bundle(data: dict) -> None:
    """Fail closed before copying the site to an anonymous public endpoint."""
    if not isinstance(data, dict) or set(data) != PUBLIC_TOP or data["schema_version"] != 1:
        raise ValueError("Unexpected public dashboard schema")
    if not isinstance(data["generated_at"], str) or not data["generated_at"]:
        raise ValueError("Public dashboard timestamp required")
    for kind, keys in (("news", PUBLIC_NEWS), ("india_news", PUBLIC_NEWS), ("drafts", PUBLIC_DRAFT)):
        entries = data[kind]
        if not isinstance(entries, list) or len(entries) > (15 if kind == "india_news" else MAX_ITEMS):
            raise ValueError("Malformed or oversized public news feed")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != keys:
                raise ValueError("Unexpected public article fields")
            if kind in ("news", "india_news"):
                signal = bounded_trend({"score": entry["trend_score"],
                                        "coverage_feeds": entry["coverage_feeds"],
                                        "reason": entry["trend_reason"]})
                if signal["score"] != entry["trend_score"]:
                    raise ValueError("Invalid news trend score")
            if any(not isinstance(value, str) for key, value in entry.items()
                   if key not in ("trend_score", "coverage_feeds")):
                raise ValueError("Public article fields must all be strings")
            if (not entry["id"] or not entry["title"] or entry["category"] not in CATEGORIES
                    or source_url(entry["source_url"]) != entry["source_url"]):
                raise ValueError("Unsafe public article")
            if kind in ("news", "india_news"):
                if entry["region"] not in ("india", "global") or (kind == "india_news" and entry["region"] != "india"):
                    raise ValueError("Invalid news region")
                if entry["image_url"] and safe_image_url(entry["image_url"]) != entry["image_url"]:
                    raise ValueError("Unsafe RSS thumbnail URL")
                if entry["context_status"] not in ("rss_preview", "headline_only"):
                    raise ValueError("Unsupported RSS source context status")
                if (len(entry["source_preview"]) > 170 or
                        (entry["context_status"] == "headline_only") != (entry["source_preview"] == "")):
                    raise ValueError("Invalid or mismatched RSS preview context")
                if entry["status"] != "unverified":
                    raise ValueError("Unverified RSS suggestions cannot be marked reviewed")
            if kind == "drafts" and entry["status"] not in ("pending", "reviewed"):
                raise ValueError("Rejected or unknown AI drafts cannot be published")
    if not isinstance(data["warnings"], list) or any(
            warning != "some_feed_sources_unavailable" for warning in data["warnings"]):
        raise ValueError("Unexpected public feed warnings")
    serialized = json.dumps(data, ensure_ascii=False).lower()
    if any(marker in serialized for marker in PRIVATE_MARKERS):
        raise ValueError("Private evidence marker or token-like text in public feed")


def build_bundle(queue: dict, issues: list[dict], dest: Path, *, generated_at=None):
    if dest.resolve() == ASSETS.resolve():
        raise ValueError("Refusing to overwrite source assets")
    news = read_news(queue)
    india_news = [item for item in read_news(queue, "india_articles") if item["region"] == "india"][:15]
    drafts = read_drafts(issues)
    time_value = generated_at or datetime.now(timezone.utc).isoformat()
    result = {
        "schema_version": 1,
        "generated_at": time_value,
        "news": news,
        "india_news": india_news,
        "drafts": drafts,
        "warnings": ["some_feed_sources_unavailable"] if queue.get("feed_errors") else [],
    }
    validate_public_bundle(result)
    dest.mkdir(parents=True, exist_ok=True)
    for filename in ("index.html", "account.html", "account.mjs", "auth-config.json", "styles.css", "account-visual.css", "app.js", "studio.mjs", "perspective.mjs", "cloud-sync.mjs", "workspace-transfer.mjs", "review-desk.mjs", "refresh-clock.mjs", "news-sections.mjs", "coverage-note.mjs", "news-image.mjs", "news-explorer.mjs", "archive-client.mjs", "feed-config.json", "_headers"):
        shutil.copyfile(ASSETS / filename, dest / filename)
    (dest / "data.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--issues-file", type=Path, help="Offline test/preview only")
    parser.add_argument("--github", action="store_true", help="Read private GitHub AI Draft Issues")
    opts = parser.parse_args()
    if opts.github == bool(opts.issues_file):
        parser.error("Choose exactly one of --github or --issues-file")
    queue = json.loads(opts.queue.read_text(encoding="utf-8"))
    issues = (fetch_private_issues() if opts.github else
              json.loads(opts.issues_file.read_text(encoding="utf-8")))
    result = build_bundle(queue, issues, opts.output)
    print("SignalDesk bundle built locally: %d news, %d AI drafts. "
          "NO Cloudflare deployment, no X post, no publication approval." %
          (len(result["news"]), len(result["drafts"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
