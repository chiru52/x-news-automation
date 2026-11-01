"""Conservative country attribution for the daily public news snapshot.

Publisher nationality alone is not proof of an India-related story. The only
publisher-level exemption is an explicit region=india in sources.json.
"""
import re

INDIA_HEADLINE = re.compile(
    r"\b(?:india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|"
    r"pune|gurugram|noida|rbi|sebi|nifty|sensex|nse|bse|rupee|rupees|"
    r"lakh|crore|isro|aadhaar|upi)\b", re.I,
)
INDIA_DESCRIPTION = re.compile(
    r"\b(?:in india|across india|india-based|indian startup|"
    r"indian government|reserve bank of india|india's market|"
    r"indian stock market)\b", re.I,
)


def explicit_india_sources(sources: list[dict]) -> set[str]:
    return {s["name"] for s in sources if s.get("region") == "india"
            and isinstance(s.get("name"), str)}


def is_india_article(article, india_sources: set[str]) -> bool:
    """Works with Article objects or sanitized RSS queue dicts."""
    if isinstance(article, dict):
        title = article.get("title", "")
        summary = article.get("summary", "")
        source = article.get("source", "")
    else:
        title = article.title
        summary = article.summary
        source = article.source
    return (source in india_sources or
            bool(INDIA_HEADLINE.search(title or "")) or
            bool(INDIA_DESCRIPTION.search(summary or "")))


def global_preview_candidates(articles, sources):
    """Only non-India stories are eligible for the separate Global 50 capacity."""
    india_sources = explicit_india_sources(sources)
    return [a for a in articles if not is_india_article(a, india_sources)]


INDIA_PREVIEW_HOURS = 72  # Slightly wider weekend coverage; never claim these are all from today.
INDIA_PREVIEW_SOURCE_CAP = 8  # Do not let one publisher fill all 50 slots.


def select_india_preview_articles(articles, sources, now, *,
                                  lookback_hours=INDIA_PREVIEW_HOURS, max_articles=50,
                                  exclude_promotional=True):
    """Use the existing safe editorial selector, but on India candidates only.

    The India-specific evidence filter determines eligibility, not the narrow
    technology/markets/SaaS keyword list used by the original X draft bot.
    The 72-hour rolling window covers weekend news gaps without asserting that
    older stories happened today. It never changes publishing quotas or persisted
    history and never pads with unrelated international articles.
    """
    from .preview_ranking import rank_preview_stories
    india_sources = explicit_india_sources(sources)
    eligible = [a for a in articles if is_india_article(a, india_sources)]
    return rank_preview_stories(
        eligible, now, limit=max_articles, lookback_hours=lookback_hours,
        max_per_source=INDIA_PREVIEW_SOURCE_CAP, max_saas_funding=4,
        exclude_promotional=exclude_promotional, max_us_futures=1,
    )
