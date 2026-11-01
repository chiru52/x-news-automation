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


def select_india_preview_articles(articles, sources, now, *,
                                  lookback_hours=36, max_articles=50,
                                  exclude_promotional=True):
    """Use the existing safe editorial selector, but on India candidates only.

    The India-specific evidence filter determines eligibility, not the narrow
    technology/markets/SaaS keyword list used by the original X draft bot.
    This never changes publishing quotas or persisted history and does not pad
    India results with unrelated international articles.
    """
    from .core import select_articles
    india_sources = explicit_india_sources(sources)
    eligible = [a for a in articles if is_india_article(a, india_sources)]
    empty_preview_state = {"seen": {}, "seen_titles": {}, "daily_drafts": {}}
    return select_articles(
        eligible, empty_preview_state, now,
        daily_limit=max_articles, lookback_hours=lookback_hours,
        timezone_name="UTC", rank_by_relevance=False,
        category_order=("technology", "markets", "saas", "world", "policy", "factcheck"),
        max_per_source_per_day=4, max_saas_funding_per_day=4,
        exclude_promotional_headlines=exclude_promotional,
        max_us_index_futures_per_day=1,
    )
