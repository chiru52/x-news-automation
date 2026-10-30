"""Explainable editorial *signals* for selected RSS headlines.

These are heuristic scores for ranking the site's news feed. They do NOT
measure X/social popularity, independently corroborate claims, or fact-check.
Coverage counts RSS feeds carrying a conservatively matched headline, never
distinct independent publishers. No API calls, AI generation or publishing.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .core import Article, canonical_url
from .news_quality import same_story
from .relevance import assess_story

MAX_FEEDS = 20
KEYWORDS = re.compile(
    r"\b(?:launch(?:es|ed)?|releas(?:e|es|ed)|unveil(?:s|ed)?|"
    r"acquir(?:e|es|ed)|funding|rais(?:e|es|ed)|"
    r"earnings|revenue|regulat(?:ion|or)|"
    r"breakthrough|security|vulnerability|ban|"
    r"merger|files for)\b", re.I
)
SPECULATIVE = re.compile(
    r"\b(?:will|could|might|may|should|predict(?:s|ion)?|"
    r"rumou?r|forecast)\b|\?$", re.I
)


def match_for_coverage(article: Article, other: Article) -> bool:
    """Same article link or conservative near-identical reporting title."""
    if article.category != other.category:
        return False
    if canonical_url(article.link) == canonical_url(other.link):
        return True
    first = {"title": article.title, "source_url": article.link}
    second = {"title": other.title, "source_url": other.link}
    return same_story(first, second)


def signals_for_selected(selected: list[Article], all_stories: list[Article],
                         now: datetime, *, lookback_hours=36) -> dict[str, dict]:
    """Map selected article ID to bounded numeric signals & safe explanation.

    Ignore feed posts that are stale or future-dated, and count distinct feed
    names only once. Heuristic impact comes from title, not publisher evidence.
    """
    from datetime import timedelta
    if now.tzinfo is None:
        raise ValueError("now needs timezone")
    now = now.astimezone(timezone.utc)
    result = {}
    for article in selected:
        published = datetime.fromisoformat(article.published_at)
        relevance = assess_story(article.title, article.summary,
                                 article.category, published, now)
        feeds = {article.source}
        for candidate in all_stories:
            timestamp = datetime.fromisoformat(candidate.published_at)
            timestamp = timestamp.astimezone(timezone.utc)
            if not now - timedelta(hours=lookback_hours) <= timestamp <= now + timedelta(minutes=10):
                continue
            if match_for_coverage(article, candidate):
                feeds.add(candidate.source)
            if len(feeds) >= MAX_FEEDS:
                break
        count = min(len(feeds), MAX_FEEDS)
        # assess_story() is already a relevance/freshness heuristic. A headline
        # reporting a concrete development receives a modest impact boost.
        impact = 12 if KEYWORDS.search(article.title) else 0
        speculative = 15 if SPECULATIVE.search(article.title) else 0
        score = max(0, min(100, int(relevance["score"]) * 7 +
                             impact + min(count - 1, 3) * 8 - speculative))
        if count > 1:
            reason = f"Headline relevance and {count} matching RSS feeds"
        elif impact:
            reason = "Fresh headline about a reported development"
        else:
            reason = "Headline relevance and recency"
        result[article.identity] = {
            "score": score,
            "coverage_feeds": count,
            "reason": reason,
        }
    return result
