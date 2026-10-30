"""Conservative headline grouping for the public, read-only news dashboard.

Never infer factual equivalence from RSS summaries. Similarity is deliberately
strict so distinct earnings figures, companies and follow-up events stay visible.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TOKEN = re.compile(r"[a-z0-9]+(?:[.][0-9]+)?", re.I)
IGNORED = {"the", "a", "an", "and", "or", "but", "of", "in", "on", "for", "to",
           "with", "at", "by", "from", "as", "after", "before", "new", "latest",
           "says", "report", "reports", "news", "update", "updates"}
TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonical_story_url(url: str) -> str:
    """Avoid duplicate RSS links with UTM tags; do not erase meaningful params."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https" or not parts.hostname:
        return ""
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    return urlunsplit(("https", parts.netloc.lower(),
                       parts.path.rstrip("/") or "/", urlencode(query), ""))


def words(title: str) -> set[str]:
    return {token for token in TOKEN.findall(title.casefold()) if token not in IGNORED}


def same_story(a: dict, b: dict) -> bool:
    """True only for same source URL or virtually identical long headlines.

    Different dates or numerical figures may signal a genuinely new update.
    Prefer false negatives to accidentally hiding news about a separate event.
    """
    ua, ub = canonical_story_url(str(a.get("source_url", ""))), canonical_story_url(str(b.get("source_url", "")))
    if ua and ub and ua == ub:
        return True
    ta, tb = words(str(a.get("title", ""))), words(str(b.get("title", "")))
    if len(ta) < 6 or len(tb) < 6:
        return False
    # Never merge stories that disagree on numbers (revenue, dates, price etc).
    na = {t for t in ta if any(ch.isdigit() for ch in t)}
    nb = {t for t in tb if any(ch.isdigit() for ch in t)}
    if na != nb:
        return False
    # Require highly overlapping words AND same lead entities: protective
    # against separate companies announcing comparable products.
    lead_a = [w for w in TOKEN.findall(str(a.get("title", "")).casefold()) if w not in IGNORED][:2]
    lead_b = [w for w in TOKEN.findall(str(b.get("title", "")).casefold()) if w not in IGNORED][:2]
    if lead_a != lead_b:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.85


def unique_stories(items: list[dict]) -> list[dict]:
    """Keep first (preferred) item; never mutate the original feed records."""
    seen: list[dict] = []
    for item in items:
        if not any(same_story(item, other) for other in seen):
            seen.append(item)
    return seen
