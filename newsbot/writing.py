"""Conservative, no-API news post suggestions from UNVERIFIED RSS headlines.

This module does not fetch or verify a publisher's original article and never
publishes anything. Its output is an editorial starting point, not an approved
or automatically fact-checked X post.
"""
from __future__ import annotations

import re

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
    if not URL.fullmatch(url):
        raise ValueError("Cannot draft without an HTTP(S) source URL")
    if not source:
        source = "RSS feed"
    # Explicit attribution reduces the risk of presenting newswire/rumor
    # headlines as claims independently verified by this bot.
    suffix = f"\n\nVia {source}: {url}"
    budget = HEADROOM - approximate_x_length(suffix)
    headline, shortened = _shorten_headline(title, budget)
    draft = headline + suffix
    assert approximate_x_length(draft) <= HEADROOM
    warnings = ["Read the original source; RSS headline has not been fact-checked."]
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
        "method": "rule_based_attributed_rss_headline",
        "approx_x_length": approximate_x_length(draft),
        "limit_approximate": True,
        "headline_shortened": shortened,
        "verification_warnings": warnings,
        "source_article_read": False,
        "fact_checked": False,
        "editor_approved": False,
        "publishable": False,
    }
