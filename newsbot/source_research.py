"""Bounded one-article extraction for manual Copilot editorial review.

Fetches public HTTPS pages on a small publisher allowlist, without redirects.
Extracted paragraphs are *one publisher's unverified claims*, not corroboration.
Never submits, approves, schedules, or publishes content.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_HTML_BYTES = 400_000
MAX_EXCERPT_CHARS = 3_200
MAX_PARAGRAPHS = 8
TIMEOUT_SECONDS = 8

# This is a narrow publisher allowlist, NOT an arbitrary URL fetcher.
# Includes named RSS publishers and a few common finance syndication targets.
# Remove or expand domains only after reviewing their security and terms.
PUBLISHER_DOMAINS = frozenset((
    "bbc.com", "bbc.co.uk", "arstechnica.com", "theverge.com",
    "cnbc.com", "producthunt.com", "thesaasnews.com",
    "finance.yahoo.com", "techcrunch.com", "saastr.com",
    "news.ycombinator.com", "stocktwits.com", "marketwatch.com",
    "reuters.com", "benzinga.com", "investing.com",
))

SPACE = re.compile(r"\s+")
BOILERPLATE = re.compile(
    r"^(?:advertisement|sign up|subscribe|read more|related stories|"
    r"all rights reserved|follow us|share this|cookie settings)\b", re.I
)


def public_article_host(url: str) -> str | None:
    """Allow HTTPS on the publisher whitelist, with no ports or userinfo."""
    if not isinstance(url, str) or len(url) > 2500:
        return None
    if any(c.isspace() or ord(c) < 32 for c in url):
        return None
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if (parts.scheme != "https" or parts.username or parts.password
                or parts.port not in (None, 443) or not host or
                host.startswith(".") or host.endswith(".")):
            return None
    except ValueError:
        return None
    return host if any(
        host == domain or host.endswith("." + domain)
        for domain in PUBLISHER_DOMAINS
    ) else None


def require_public_dns(host: str) -> None:
    """Reject publisher DNS results containing non-global IPs before fetching.

    DNS resolution is repeated by urllib; host allowlisting/no redirects are the
    principal safeguards. Never treat DNS checks alone as SSRF protection.
    """
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not infos:
        raise ValueError("No DNS answers")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("Non-public DNS address")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ParagraphExtractor(HTMLParser):
    """Collect visible <p> elements, preferring <main> or <article> content."""

    IGNORED = {"script", "style", "noscript", "nav", "footer", "header",
               "aside", "form", "svg", "iframe", "button"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored_depth = 0
        self.main_depth = 0
        self.current = None
        self.current_in_main = False
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORED:
            self.ignored_depth += 1
        if tag in {"article", "main"}:
            self.main_depth += 1
        if tag == "p" and self.ignored_depth == 0 and self.current is None:
            self.current = []
            self.current_in_main = self.main_depth > 0

    def handle_endtag(self, tag):
        if tag == "p" and self.current is not None:
            value = SPACE.sub(" ", html.unescape(" ".join(self.current))).strip()
            if 55 <= len(value) <= 2000 and not BOILERPLATE.match(value):
                self.paragraphs.append((value, self.current_in_main))
            self.current = None
        if tag in self.IGNORED:
            self.ignored_depth = max(0, self.ignored_depth - 1)
        if tag in {"article", "main"}:
            self.main_depth = max(0, self.main_depth - 1)

    def handle_data(self, data):
        if self.current is not None and self.ignored_depth == 0:
            self.current.append(data)


def extract_paragraphs(source: bytes) -> list[dict]:
    """Return bounded numbered snippets; no raw HTML or full-article artifact."""
    parser = ParagraphExtractor()
    # Ignore untrusted charset claims; replacement avoids decode failures.
    parser.feed(source.decode("utf-8", errors="replace"))
    preferred = [text for text, inside in parser.paragraphs if inside]
    all_text = [text for text, _inside in parser.paragraphs]
    candidates = preferred if len(" ".join(preferred)) >= 400 else all_text
    snippets = []
    length = 0
    for paragraph in candidates:
        paragraph = paragraph[:550]
        if length + len(paragraph) > MAX_EXCERPT_CHARS:
            paragraph = paragraph[:max(0, MAX_EXCERPT_CHARS - length)]
        if len(paragraph) < 55:
            break
        snippets.append({"id": f"P{len(snippets)+1}", "text": paragraph})
        length += len(paragraph)
        if len(snippets) >= MAX_PARAGRAPHS or length >= MAX_EXCERPT_CHARS:
            break
    # Some RSS links contain only nav/paywall/JS placeholder text.
    return snippets if len(snippets) >= 2 and length >= 300 else []


def fetch_evidence(url: str, *, opener=None, dns_check=None) -> dict:
    """Fetch exactly one allowlisted HTTPS article. Failure returns RSS fallback.

    opener and dns_check enable network-free tests; production uses DNS checks
    and a no-redirect opener. Never return page HTML or cookies.
    """
    host = public_article_host(url)
    result = {
        "status": "unavailable",
        "reason": "domain_not_allowed_or_insecure",
        "source_url": url,
        "publisher_host": host,
        "paragraphs": [],
    }
    if not host:
        return result
    try:
        (dns_check or require_public_dns)(host)
    except (ValueError, OSError, socket.gaierror):
        result["reason"] = "dns_not_public_or_unavailable"
        return result
    request = Request(url, headers={
        "Accept": "text/html",
        "Accept-Language": "en",
        "User-Agent": "XNewsEditorialReview/1.0 (human review; no crawling)",
    }, method="GET")
    try:
        client = opener or build_opener(NoRedirect())
        with client.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != url:
                result["reason"] = "redirect_blocked"
                return result
            mime = str(response.headers.get("Content-Type", "")).split(";")[0].strip().lower()
            if mime not in ("text/html", "application/xhtml+xml"):
                result["reason"] = "unsupported_media_type"
                return result
            size = response.headers.get("Content-Length")
            if size is not None and int(size) > MAX_HTML_BYTES:
                result["reason"] = "too_large"
                return result
            body = response.read(MAX_HTML_BYTES + 1)
            if len(body) > MAX_HTML_BYTES:
                result["reason"] = "too_large"
                return result
    except HTTPError as exc:
        result["reason"] = "redirect_blocked" if 300 <= exc.code < 400 else "http_unavailable"
        return result
    except (URLError, OSError, ValueError, TimeoutError):
        result["reason"] = "network_or_http_error"
        return result
    excerpts = extract_paragraphs(body)
    if not excerpts:
        result["reason"] = "no_reliable_article_text"
        return result
    result.update(status="extracted_unverified", reason=None, paragraphs=excerpts)
    return result
