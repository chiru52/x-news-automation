"""Conservative, no-API news post suggestions from UNVERIFIED RSS headlines.

This module does not fetch or verify a publisher's original article and never
publishes anything. Its output is an editorial starting point, not an approved
or automatically fact-checked X post.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

URL = re.compile(r"https?://[^\s]+", re.I)
SPACE = re.compile(r"\s+")
NUMBER_OR_AMOUNT = re.compile(
    r"(?:[$€£₹¥]\s?\d|\b\d+(?:\.\d+)?\s?%|\b\d[\d,.]*\s?(?:million|billion|trillion)\b)",
    re.I)
UNCERTAINTY = re.compile(
    r"\b(?:rumou?r(?:ed|s)?|reportedly|alleged|allegedly|may|might|"
    r"could|expected|forecast|predict(?:s|ed|ion)?|potential|analyst[s]?|"
    r"considering|plans?|sees)\b",
    re.I)
HEADROOM = 270
URL_WEIGHT = 23

# Known *feed* homes, not necessarily the credited author of syndicated items.
# Explicit mappings avoid warning about every original BBC/Verge/SaaStr link.
KNOWN_FEED_DOMAINS = {
    "BBC Technology": ("bbc.com", "bbc.co.uk"),
    "BBC Business": ("bbc.com", "bbc.co.uk"),
    "Ars Technica": ("arstechnica.com",),
    "The Verge Tech": ("theverge.com",),
    "CNBC Markets": ("cnbc.com",),
    "CNBC Investing": ("cnbc.com",),
    "Product Hunt SaaS": ("producthunt.com",),
    "Product Hunt Productivity": ("producthunt.com",),
    "The SaaS News": ("thesaasnews.com",),
    "Yahoo Finance - Major Tech Stocks": ("finance.yahoo.com", "yahoo.com"),
    "Yahoo Finance - Market Indices": ("finance.yahoo.com", "yahoo.com"),
    "TechCrunch - Startups": ("techcrunch.com",),
    "SaaStr - SaaS Business": ("saastr.com",),
    "Hacker News - Technology": ("news.ycombinator.com", "ycombinator.com"),
}


def feed_domain_mismatch(feed_name: str, article_hostname: str) -> bool | None:
    """True: linked host differs; False: linked host matches; None: unknown feed.

    Never infer who wrote the story. Host matches are weak provenance indicators.
    """
    allowed = KNOWN_FEED_DOMAINS.get(feed_name)
    if allowed is None:
        return None
    return not any(
        article_hostname == domain or article_hostname.endswith("." + domain)
        for domain in allowed
    )



def approximate_x_length(text: str) -> int:
    """Approximate X's t.co URL weighting, not an official length validator."""
    return len(URL.sub("X" * URL_WEIGHT, text))


def _one_line(value: str, max_chars: int = 450) -> str:
    return SPACE.sub(" ", value or "").strip()[:max_chars]


def _shorten_headline(text: str, budget: int) -> tuple[str, bool]:
    if budget < 36:
        raise ValueError("Not enough room to attribute the source safely")
    if len(text) <= budget:
        return text, False
    shortened = text[:budget - 1].rsplit(" ", 1)[0].rstrip(" ,:;—-")
    if len(shortened) < 26:
        shortened = text[:budget - 1].rstrip(" ,:;—-")
    return shortened + "…", True


def suggest_post(article) -> dict:
    """Offer source-attributed, headline-only copy for later human verification.

    Intentionally does NOT use RSS summaries to infer implications, prices,
    quotes, product capabilities, or why news matters.
    """
    title = _one_line(article.title)
    if not title:
        raise ValueError("Cannot draft without an RSS headline")
    source = _one_line(article.source, 60)
    url = _one_line(article.link, 3000)
    parts = urlsplit(url)
    if not URL.fullmatch(url) or parts.scheme not in ("https", "http") or not parts.hostname:
        raise ValueError("Cannot draft without an HTTP(S) source URL")
    if not source:
        source = "RSS feed"
    # The RSS feed may syndicate external publishers. Attribution therefore
    # identifies the ACTUAL linked website rather than claiming the feed owns it.
    linked_site = parts.hostname.lower().removeprefix("www.")
    suffix = f"\n\nRead at {linked_site}: {url}"
    budget = HEADROOM - approximate_x_length(suffix)
    headline, shortened = _shorten_headline(title, budget)
    draft = headline + suffix
    assert approximate_x_length(draft) <= HEADROOM
    warnings = ["Read the linked article; RSS headline has not been fact-checked."]
    mismatch = feed_domain_mismatch(source, linked_site)
    if mismatch:
        warnings.append("Linked site differs from feed publisher; check original authorship and context.")
    if article.category == "markets":
        warnings.append("Market-sensitive claims: confirm figures, timing and source.")
    if article.category == "saas":
        warnings.append("Check the company and product really belong to the SaaS topic.")
    if NUMBER_OR_AMOUNT.search(title):
        warnings.append("Verify every number, price, valuation or percentage.")
    if UNCERTAINTY.search(title):
        warnings.append("Preserve uncertainty: this headline may be a rumor or forecast.")
    if shortened:
        warnings.append("Headline shortened: verify omitted context and qualifiers.")
    return {
        "text": draft,
        "method": "rule_based_link_attributed_rss_headline",
        "rss_feed_name": source,
        "linked_article_site": linked_site,
        "feed_domain_mismatch": mismatch,
        "approx_x_length": approximate_x_length(draft),
        "limit_approximate": True,
        "headline_shortened": shortened,
        "verification_warnings": warnings,
        "source_article_read": False,
        "fact_checked": False,
        "editor_approved": False,
        "publishable": False,
    }
