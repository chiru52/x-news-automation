"""Read-only diagnostics for the EXISTING public SignalDesk Worker.

No Cloudflare credentials, deployment calls, KV writes or X publishing.
This report is informational: bad deployment findings are surfaced in the run
summary without making GitHub CI dependent on the live Worker availability.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request

ROOT = "https://signaldesk-news-feed.littlekingchess.workers.dev"
PREVIEW = "https://signaldesk-preview.pages.dev"
PRODUCTION = "https://news.littlekingchess.com"
UNTRUSTED = "https://unapproved.example"
MAX_BYTES = 300_000  # Room for up to 50 per region; bounded public GET
TIMEOUT_SECONDS = 12


def read_public(path: str, origin: str | None):
    """Make one bounded GET to a fixed public Worker route, never a write."""
    if path not in ("/health", "/feed", "/archive?days=7"):
        raise ValueError("Only known read-only endpoints allowed")
    headers = {"Accept": "application/json", "User-Agent": "SignalDeskReadOnlyHealthAudit/1.0"}
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(ROOT + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return {"status": response.status, "headers": dict(response.headers), "error": "body too large"}
            try:
                parsed = json.loads(data.decode("utf-8"))
            except (UnicodeError, ValueError):
                parsed = None
            return {"status": response.status, "headers": dict(response.headers), "data": parsed}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "headers": dict(exc.headers), "error": "HTTP error"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": None, "headers": {}, "error": type(exc).__name__}


def cors_verdict(headers: dict, origin: str, expected: bool) -> str:
    actual = {str(k).lower(): str(v) for k, v in headers.items()}.get(
        "access-control-allow-origin"
    )
    if expected:
        return "PASS" if actual == origin else "FAIL"
    return "PASS" if actual is None else "FAIL"


def freshness_verdict(body: object, now: dt.datetime) -> tuple[str, str]:
    if not isinstance(body, dict) or body.get("schema_version") != 1:
        return "UNKNOWN", "No schema-v1 JSON snapshot returned"
    stories = body.get("news")
    if not isinstance(stories, list) or not 5 <= len(stories) <= 50:
        return "FAIL", "Snapshot has fewer than 5 or more than 50 Global stories"
    india = body.get("india_news")
    if not isinstance(india, list) or len(india) > 50 or any(
        not isinstance(item, dict) or item.get("region") != "india" for item in india
    ):
        return "FAIL", "Separate India feed missing or malformed"
    stamp = body.get("generated_at")
    if not isinstance(stamp, str):
        return "FAIL", "Snapshot missing timestamp"
    try:
        timestamp = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("naive")
        age = (now - timestamp).total_seconds() / 60
    except ValueError:
        return "FAIL", "Snapshot timestamp invalid"
    if age < -10 or age > 90:
        return "FAIL", f"Snapshot age outside the allowed range ({age:.0f} minutes)"
    return "PASS", f"{len(stories)} Global / {len(india)} India records, snapshot age {age:.0f} minutes"


def run(fetcher=read_public, now: dt.datetime | None = None):
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    observations = [
        ("/health", PRODUCTION, True, "Production health origin"),
        ("/health", PREVIEW, True, "Preview health origin"),
        ("/health", UNTRUSTED, False, "Untrusted origin rejected"),
        ("/feed", PREVIEW, True, "Preview live feed"),
        ("/archive?days=7", PREVIEW, True, "Preview 7-day archive"),
    ]
    summary = ["# SignalDesk live Worker — read-only diagnostic", "",
               "This run does not deploy, change Cloudflare, write KV, or publish to X.", "",
               "| Check | HTTP | Origin protection | Details |",
               "|---|---|---|---|"]
    results = []
    for path, origin, is_allowed, label in observations:
        response = fetcher(path, origin)
        code = response.get("status")
        cors = cors_verdict(response.get("headers") or {}, origin, is_allowed)
        details = f"Request failed: {response['error']}" if response.get("error") else "Public endpoint read"
        if path == "/feed" and code == 200:
            verdict, detail = freshness_verdict(response.get("data"), now)
            details = f"Feed {verdict}: {detail}"
        elif path == "/health" and code == 200:
            body = response.get("data")
            details = "Read-only health confirmed" if isinstance(body, dict) and (
                body.get("status") == "read_only" and body.get("x_posting_enabled") is False
            ) else "Health JSON returned; safety flags not confirmed"
        elif path.startswith("/archive") and code == 200:
            details = "Archive endpoint returned HTTP 200 (data completeness not verified)"
        elif code is not None and code != 200:
            details = "Endpoint returned HTTP " + str(code)
        # Avoid printing response bodies, original articles or secrets.
        summary.append(f"| {label} | {code if code is not None else 'Network error'} | {cors} | {details} |")
        results.append({"label": label, "http_status": code, "cors": cors, "details": details})
    summary.extend(["", "A passing CORS check **does not confirm** Cron scheduling or the "
                    "NEWS_CACHE KV binding. Verify those settings in the Cloudflare dashboard "
                    "before any deployment. The preview must be tested in a real browser too.",
                    "", "Informational audit only; red results must be investigated manually."])
    text = "\n".join(summary) + "\n"
    print(text)
    destination = os.getenv("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as output:
            output.write(text)
    return results




PREVIEW_BASE = "https://signaldesk-preview.pages.dev"
PREVIEW_FILES = ("/data.json", "/editorial-sources.json", "/news-explorer.mjs")

def read_preview_file(path: str):
    """Strict, capped GETs to exactly three publicly deployed preview assets."""
    if path not in PREVIEW_FILES:
        raise ValueError("Unknown public preview asset")
    request = urllib.request.Request(
        PREVIEW_BASE + path,
        headers={"Accept": "application/json,text/plain", "User-Agent": "SignalDeskReadOnlyHealthAudit/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(300_001)
            if len(raw) > 300_000:
                return {"http_status": response.status, "error": "response_too_large"}
            return {"http_status": response.status, "body": raw.decode("utf-8")}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, UnicodeError) as exc:
        return {"http_status": getattr(exc, "code", None), "error": type(exc).__name__}

def preview_deployment_report(fetcher=read_preview_file):
    """Report public counts and feature availability, never individual articles."""
    parts = {path: fetcher(path) for path in PREVIEW_FILES}
    def json_data(path):
        try:
            return json.loads(parts[path].get("body",""))
        except (ValueError, TypeError):
            return None
    data = json_data("/data.json")
    sources = json_data("/editorial-sources.json")
    js = parts["/news-explorer.mjs"].get("body", "")
    # Source-level counts reveal where publisher RSS thumbnail coverage is
    # missing, without outputting URLs, article text or remote image calls.
    coverage = {}
    if isinstance(data, dict):
        for section in ("news", "india_news"):
            articles = data.get(section, [])
            if not isinstance(articles, list):
                continue
            for item in articles[:50]:
                if not isinstance(item, dict):
                    continue
                publisher = item.get("publisher", "")
                if not isinstance(publisher, str) or not 0 < len(publisher) <= 100:
                    continue
                counts = coverage.setdefault(publisher, [0, 0])
                counts[0] += 1
                counts[1] += bool(item.get("image_url"))
    publisher_summary = [
        {"publisher": pub, "stories": nums[0], "with_images": nums[1]}
        for pub, nums in sorted(coverage.items(), key=lambda x: (-x[1][0], x[0]))[:15]
    ]
    metrics = {
        "publisher_photo_coverage": publisher_summary,
        "static_global_stories": len(data.get("news", [])) if isinstance(data,dict) and isinstance(data.get("news"),list) else None,
        "static_india_stories": len(data.get("india_news", [])) if isinstance(data,dict) and isinstance(data.get("india_news"),list) else None,
        "static_stories_with_images": sum(bool(x.get("image_url")) for kind in ("news","india_news") for x in data.get(kind,[]) if isinstance(x,dict)) if isinstance(data,dict) else None,
        "catalogue_entries":len(sources) if isinstance(sources,list) else None,
        "news_explorer_has_real_image_support": "safeNewsImage(item.image_url)" in js,
        "static_generated_at":data.get("generated_at") if isinstance(data,dict) else None,
    }
    print("\n# Public SignalDesk Preview deployment check (read only)\n")
    for path in PREVIEW_FILES:
        print(f"{path}: HTTP {parts[path].get('http_status')}"+(f" ({parts[path]['error']})" if parts[path].get("error") else ""))
    for name,value in metrics.items():
        print(f"{name}: {value}")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as fp:
            fp.write("\n## Public preview files\n\n")
            for path in PREVIEW_FILES:
                fp.write(f"- {path}: HTTP {parts[path].get('http_status')}\n")
            for name,value in metrics.items():
                fp.write(f"- {name}: {value}\n")
    return metrics

if __name__ == "__main__":
    run()
    preview_deployment_report()
