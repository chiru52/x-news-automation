"""Explainable, conservative headline relevance. Not AI or fact-checking.

A source category is only a hint. For selection, require a recognizable
headline topic; summary matches can add context but cannot qualify alone.
All scores are editorial heuristics and MUST NOT be used as publication approval.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

TOPIC_TERMS = {
    "technology": (
        "ai", "artificial intelligence", "machine learning", "llm", "openai",
        "anthropic", "chatgpt", "grok", "deepseek", "semiconductor", "chip",
        "gpu", "cybersecurity", "data breach", "ransomware", "cloud computing",
        "cloud service", "developer", "coding", "robot", "robotics",
        "quantum computing", "data center", "datacenter", "iphone", "android",
        "macbook", "smartphone", "software", "hardware", "technology",
    ),
    "markets": (
        "stocks", "stock", "shares", "share price", "investor", "investors",
        "earnings", "revenue", "quarterly profit", "inflation", "interest rate",
        "rate cut", "rate hike", "federal reserve", "fed", "central bank",
        "nasdaq", "s&p 500", "dow jones", "market index", "indices", "equities",
        "stock market", "bond yields", "treasury yields", "ipo", "gdp",
        "unemployment", "economic growth", "recession", "bitcoin",
        "cryptocurrency", "oil prices", "gold prices", "nifty", "sensex",
        "nse", "bse", "market cap",
    ),
    "saas": (
        "saas", "software as a service", "startup", "start-up", "startups",
        "founder", "funding round", "seed round", "series a", "series b",
        "venture capital", "b2b", "enterprise software", "business software",
        "subscription", "crm", "productivity", "workflow", "automation",
        "no-code", "low-code", "mobile app", "web app", "ai app", "platform",
        "app launch", "product launch", "customer support software",
    ),
}
IMPACT_TERMS = (
    "launches", "launched", "launch", "unveils", "released", "releases",
    "acquires", "acquired", "acquisition", "merger", "funding",
    "raises", "raised", "files for", "reports", "surges", "plunges",
    "cuts", "cut", "beats", "misses", "breakthrough", "ban",
)


def _matched(text: str, terms: tuple[str, ...]) -> list[str]:
    """Whole phrase/word matching avoids 'ai' inside 'said' or 'app' in 'Apple'."""
    return [term for term in terms
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, flags=re.I)]


def assess_story(title: str, summary: str, category: str,
                 published_at: datetime, now: datetime) -> dict:
    """Return a transparent ranking score; never infer factual correctness."""
    title_terms = _matched(title, TOPIC_TERMS.get(category, ()))
    summary_terms = _matched(summary, TOPIC_TERMS.get(category, ()))
    impact = _matched(title, IMPACT_TERMS)
    age_hours = max(0.0, (now.astimezone(timezone.utc)
                          - published_at.astimezone(timezone.utc)).total_seconds() / 3600)
    if not title_terms:
        return {"score": 0, "topic_match": False, "headline_terms": [],
                "summary_terms": summary_terms[:5], "impact_terms": impact[:3],
                "reason": "No category-specific headline term; needs manual triage"}
    score = (4 + min(len(title_terms) - 1, 3)
             + (1 if summary_terms else 0)
             + (2 if impact else 0)
             + (2 if age_hours <= 6 else 1 if age_hours <= 24 else 0))
    return {"score": score, "topic_match": True, "headline_terms": title_terms[:6],
            "summary_terms": summary_terms[:5], "impact_terms": impact[:3],
            "reason": "Keyword-based editorial ranking only; not verified"}

def is_saas_funding_headline(title: str) -> bool:
    """Detect capital-raising announcements, not SaaS product releases."""
    return bool(re.search(
        r"\b(?:series[ -]?[a-f]|pre-seed|seed round|funding round)\b"
        r"|\braises?\s+(?:[$€£₹¥]|\d[\d,.]*)",
        title, flags=re.I
    ))



PROMOTIONAL_OFFER = re.compile(
    r"\b(?:save (?:up to )?(?:[$€£₹¥]\s?\d+|\d+%)|"
    r"early[- ]bird(?: pricing| tickets?)?|"
    r"tickets? (?:on sale|available)|"
    r"register (?:now|today)|"
    r"buy (?:your )?tickets?|"
    r"promo code|discount(?:ed)? (?:tickets?|passes?)|"
    r"passes? (?:before|on sale))\b",
    flags=re.I,
)

US_FUTURES = re.compile(r"\bfutures\b", flags=re.I)
US_INDEX = re.compile(r"\b(?:nasdaq|dow|s&p\s*500|s\s*&\s*p\s*500)\b", flags=re.I)


def is_promotional_headline(title: str) -> bool:
    """Clear ticket, sale, or registration pitches, not all conference reporting."""
    return bool(PROMOTIONAL_OFFER.search(title))


def is_us_index_futures_headline(title: str, category: str = "markets") -> bool:
    """Conservatively group multiple index-futures market snapshots for review."""
    return category == "markets" and bool(US_FUTURES.search(title) and US_INDEX.search(title))
