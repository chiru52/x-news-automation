"""No-cost explainable Top 50 selection for the PUBLIC news preview only.

A deterministic editorial *heuristic*, not factual verification or social trends.
Ranks the entire eligible regional RSS pool before the final 50-story cap.
Never used by the X publishing path. No API, model, extra feed or network calls.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
import re

from .core import Article, title_key
from .relevance import (assess_story, is_promotional_headline,
                        is_saas_funding_headline, is_us_index_futures_headline)

EVENTS = re.compile(
    r"\b(?:announces?|announced|approves?|approved|passes|passed|signs|signed|"
    r"launches?|launched|releases?|released|reports?|reported|confirms?|confirmed|"
    r"cuts?|reduced|increases?|increased|raises?|raised|acquires?|acquired|"
    r"merges?|merged|earnings|profit|losses|inflation|interest rates?|"
    r"gdp|recession|regulation|ruling|court|policy|budget|tariffs?|"
    r"sanctions?|investigation|breach|security|recalls?|"
    r"fact.?checks?|false claim|misleading|debunked|bankruptcy)\b", re.I
)
# Conservative subject signals; an unsupported headline does not score as verified.
TOPICS = re.compile(
    r"\b(?:markets?|stocks?|shares?|economy|economic|central bank|trade|"
    r"business|banking|companies|company|technology|software|ai|"
    r"artificial intelligence|startup|startups|financ(?:e|ial)|policy|"
    r"government|world|international|foreign|election|research|"
    r"fact.?check|misinformation|indian|india)\b", re.I
)
# Avoid giving the same story a high rank because it uses sensational language.
IGNORE = frozenset(("the", "a", "an", "and", "or", "but", "of", "in", "on",
                    "for", "to", "with", "at", "by", "from", "as", "after",
                    "before", "new", "latest", "says", "report", "reports",
                    "news", "update", "updates"))

def _headline_tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+(?:[.][0-9]+)?", text.lower())
            if word not in IGNORE]

def _near_duplicate(left: str, right: str) -> bool:
    a, b = _headline_tokens(left), _headline_tokens(right)
    x, y = set(a), set(b)
    if title_key(left) == title_key(right):
        return True
    if len(x) < 6 or len(y) < 6:
        return False
    # Different numbers or company/entity lead terms must not be collapsed.
    if ([v for v in a if any(c.isdigit() for c in v)] !=
            [v for v in b if any(c.isdigit() for c in v)] or a[:2] != b[:2]):
        return False
    overlap = len(x & y)
    return overlap >= 6 and overlap / len(x | y) >= .84


def _editorial_score(article: Article, now: datetime) -> int:
    published = datetime.fromisoformat(article.published_at).astimezone(timezone.utc)
    age_hours = max(0, (now - published).total_seconds() / 3600)
    # Freshness is meaningful but not everything, particularly on weekends.
    freshness = round(38 / (1 + age_hours / 18))
    events = len(EVENTS.findall(article.title))
    topic = len(TOPICS.findall(article.title))
    # Legacy topic vocabulary adds modest context for relevant tech/market stories.
    assessment = assess_story(article.title, article.summary, article.category, published, now)
    return (freshness + min(events, 2) * 8 + min(topic, 2) * 4 +
            (3 if assessment["topic_match"] else 0) +
            (2 if article.summary and len(article.summary) >= 40 else 0))


def rank_preview_stories(articles, now: datetime, *, lookback_hours: int,
                         limit: int = 50, max_per_source: int = 7,
                         max_saas_funding: int | None = None,
                         max_us_futures: int | None = None,
                         exclude_promotional: bool = True) -> list[Article]:
    """Rank a complete region's RSS pool (up to 50), deduped and source-balanced.

    No synthetic articles, date guessing, editorial truth claims, or persisted
    selection state.  User's original X selector is untouched.
    """
    if now.tzinfo is None:
        raise ValueError("now must contain a timezone")
    if not (1 <= limit <= 50 and 1 <= max_per_source <= 50 and
            1 <= lookback_hours <= 168):
        raise ValueError("Invalid public preview ranking bounds")
    now = now.astimezone(timezone.utc)
    min_date = now - timedelta(hours=lookback_hours)
    candidates: list[tuple[Article, int, float]] = []
    seen_links, seen_titles = set(), set()
    # Exact dedup BEFORE scoring ensures a duplicate cannot claim two slots.
    # Stable order on ties irrespective of publisher fetch/response order.
    for article in articles:
        if not isinstance(article, Article):
            continue
        try:
            published = datetime.fromisoformat(article.published_at)
            if published.tzinfo is None:
                continue
            published = published.astimezone(timezone.utc)
            link = article.identity
        except (ValueError, AttributeError):
            continue
        if not (min_date <= published <= now + timedelta(minutes=10)):
            continue
        if exclude_promotional and is_promotional_headline(article.title):
            continue
        token = title_key(article.title)
        if link in seen_links or token in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(token)
        candidates.append((article, _editorial_score(article, now), published.timestamp()))
    # Order makes the best scored variant survive cross-publisher duplicate
    # suppression; tie-break by published time then stable article identity.
    candidates.sort(key=lambda x: (-x[1], -x[2], x[0].title.casefold(), x[0].identity))
    result: list[Article] = []
    source_counts: Counter = Counter()
    category_counts: Counter = Counter()
    funding_count = futures_count = 0
    for _ in range(min(limit, len(candidates))):
        available = []
        for article, score, timestamp in candidates:
            if source_counts[article.source] >= max_per_source:
                continue
            if any(_near_duplicate(article.title, prev.title) for prev in result):
                continue
            if (max_saas_funding is not None and article.category == "saas" and
                is_saas_funding_headline(article.title) and funding_count >= max_saas_funding):
                continue
            if (max_us_futures is not None and
                is_us_index_futures_headline(article.title, article.category) and
                futures_count >= max_us_futures):
                continue
            # Modest diversity penalties do not turn freshness into a popularity vote.
            # Every accepted source must still have an eligible dated RSS article.
            adjusted = score - 5 * source_counts[article.source] - min(
                6, category_counts[article.category] // 4)
            available.append((adjusted, score, timestamp, article))
        if not available:
            break
        # Deterministic tie-breaks independent of RSS fetch ordering.
        best = min(available, key=lambda x: (-x[0], -x[1], -x[2],
                                              x[3].title.casefold(), x[3].identity))
        chosen = best[3]
        result.append(chosen)
        candidates = [candidate for candidate in candidates if candidate[0].identity != chosen.identity]
        source_counts[chosen.source] += 1
        category_counts[chosen.category] += 1
        if chosen.category == "saas" and is_saas_funding_headline(chosen.title):
            funding_count += 1
        if is_us_index_futures_headline(chosen.title, chosen.category):
            futures_count += 1
    return result
