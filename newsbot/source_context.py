"""Short, attributed context from selected *RSS summaries* only.

No article scraping, LLM inference, or independent fact checking. Output is a
brief plain-text feed preview suitable for public editorial review, NEVER full
publisher evidence or private GitHub notes.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

MAX_PREVIEW = 170
MIN_PREVIEW = 35
LINKS = re.compile(r"https?://[^\s<>]+", re.I)
SPACE = re.compile(r"\s+")
LOW_VALUE = re.compile(r"\b(?:subscribe now|sign up for our newsletter|cookie policy|"
                       r"click here to|advertisement|visit our website)\b", re.I)


class _PlainFeedText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        elif tag in ("p", "div", "br", "li") and not self.hidden:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1
        elif tag in ("p", "div", "li") and not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def preview_from_rss(value: object, title: str) -> str:
    """Clean, truncate and reject low-value RSS description text.

    This content is *claimed by the feed* and must be labelled accordingly.
    It is not verified article text, and must never enter an LLM by default.
    """
    if not isinstance(value, str) or len(value) > 5000:
        return ""
    parser = _PlainFeedText()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, AssertionError):
        return ""
    cleaned = SPACE.sub(" ", LINKS.sub("", html.unescape(" ".join(parser.parts)))).strip()
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", cleaned)
    cleaned = SPACE.sub(" ", cleaned).strip(" ,;:—-")
    if len(cleaned) < MIN_PREVIEW or LOW_VALUE.search(cleaned):
        return ""
    if cleaned.casefold().strip(".!?") == SPACE.sub(" ", title).casefold().strip(".!?"):
        return ""
    if len(cleaned) <= MAX_PREVIEW:
        return cleaned
    fragment = cleaned[:MAX_PREVIEW - 1]
    if " " in fragment[60:]:
        fragment = fragment.rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return fragment + "…"
