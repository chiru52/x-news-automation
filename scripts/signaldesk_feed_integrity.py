"""Validate *actual* public RSS story data before claiming a healthy feed.

Only processes already-fetched JSON. No HTTP, credentials, KV, AI or publishing.
Rejects invalid provenance and old headlines even if the feed clock is recent.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import re
from urllib.parse import urlsplit

CATEGORIES = frozenset(("technology", "saas", "markets", "world", "policy", "factcheck"))
SECTIONS = (("news", "global", 36), ("india_news", "india", 72))
ID = re.compile(r"^[a-f0-9]{24}$")
TRACKING = frozenset(("fbclid", "gclid", "mc_cid", "mc_eid"))


def parse_time(value):
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        time = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return time.astimezone(dt.timezone.utc) if time.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def source_url_ok(value):
    if not isinstance(value, str) or not 10 < len(value) <= 2000 or re.search(r"\s", value):
        return False
    try:
        p = urlsplit(value)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        host = p.hostname.lower()
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return "." in host and len(host) <= 253
    except ValueError:
        return False


def inspect_feed_stories(snapshot, generated_at):
    """Return one bounded error reason; never expose article text or publisher URLs."""
    if not isinstance(snapshot, dict):
        return "Feed JSON is not an object"
    seen_ids, seen_links = set(), set()
    for key, region, max_hours in SECTIONS:
        stories = snapshot.get(key)
        if not isinstance(stories, list):
            return f"{key} array missing"
        if (key == "news" and not 5 <= len(stories) <= 50) or len(stories) > 50:
            return f"{key} count outside allowed range"
        for article in stories:
            if not isinstance(article, dict):
                return f"{key} has non-object story"
            identifier = article.get("id")
            link = article.get("source_url")
            if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in seen_ids:
                return f"{key} has invalid or duplicate article ID"
            seen_ids.add(identifier)
            if not source_url_ok(link) or link in seen_links:
                return f"{key} has unsafe or duplicate publisher link"
            seen_links.add(link)
            if article.get("region") != region:
                return f"{key} has incorrect region"
            if article.get("category") not in CATEGORIES:
                return f"{key} has unknown topic"
            if not isinstance(article.get("title"), str) or not 3 <= len(article["title"].strip()) <= 260:
                return f"{key} has invalid headline"
            if not isinstance(article.get("publisher"), str) or not 2 <= len(article["publisher"].strip()) <= 120:
                return f"{key} has missing publisher attribution"
            published = parse_time(article.get("published_at"))
            if published is None:
                return f"{key} has invalid publication time"
            age_minutes = (generated_at - published).total_seconds() / 60
            if age_minutes < -10 or age_minutes > max_hours * 60:
                return f"{key} has headline outside {max_hours}-hour region window"
            if article.get("status") != "unverified":
                return f"{key} is not an unverified editorial story"
            photo = article.get("image_url", "")
            if photo and not source_url_ok(photo):
                return f"{key} has unsafe image URL"
    return None
