"""Bounded one-article extraction for manual Copilot editorial review.

Fetches public HTTPS pages on a small publisher allowlist, without redirects.
Extracted paragraphs are *one publisher's unverified claims*, not corroboration.
Never submits, approves, schedules, or publishes content.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_HTML_BYTES = 1_200_000  # Modern article HTML can include substantial CSS/JS
MAX_EXCERPT_CHARS = 3_200
MAX_PARAGRAPHS = 8
TIMEOUT_SECONDS = 8
MAX_SAME_HOST_REDIRECTS = 2

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
        self.structured = []
        self.jsonld = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (tag == "script" and str(attrs.get("type", "")).lower()
                == "application/ld+json" and self.jsonld is None):
            self.jsonld = []
        if tag in self.IGNORED:
            self.ignored_depth += 1
        if tag in {"article", "main"}:
            self.main_depth += 1
        if tag == "p" and self.ignored_depth == 0 and self.current is None:
            self.current = []
            self.current_in_main = self.main_depth > 0

    def handle_endtag(self, tag):
        if tag == "script" and self.jsonld is not None:
            raw_json = "".join(self.jsonld)
            self.jsonld = None
            if len(raw_json) <= 160_000:
                try:
                    self.structured.append(json.loads(raw_json))
                except (ValueError, RecursionError):
                    pass
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
        if self.jsonld is not None:
            self.jsonld.append(data)
        if self.current is not None and self.ignored_depth == 0:
            self.current.append(data)


def _structured_article_body(nodes: list) -> str:
    """Retrieve only articleBody from explicitly typed NewsArticle JSON-LD."""
    def find(node, depth=0):
        if depth > 12:
            return ""
        if isinstance(node, list):
            for item in node[:40]:
                found = find(item, depth+1)
                if found:
                    return found
        if isinstance(node, dict):
            types = node.get("@type", [])
            names = [types] if isinstance(types, str) else types
            if isinstance(names, list) and any(str(t).lower() in {
                "article", "newsarticle", "blogposting", "analysisnewsarticle",
                "reportagenewsarticle"
            } for t in names):
                body = node.get("articleBody")
                if isinstance(body, str) and len(body) >= 300:
                    return body[:12_000]
            for key in ("@graph", "mainEntity", "itemListElement"):
                if key in node:
                    found = find(node[key], depth+1)
                    if found:
                        return found
        return ""
    return find(nodes)


def _short_chunks(values: list[str]) -> list[dict]:
    """Return at most 3,200 chars of actual article prose as numbered claims."""
    chunks = []
    length = 0
    seen = set()
    for value in values:
        value = SPACE.sub(" ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
        if len(value) < 65 or BOILERPLATE.match(value):
            continue
        if value[:80] in seen:
            continue
        seen.add(value[:80])
        # Truncate individual paragraphs rather than emit the publisher's article.
        snippet = value[:550]
        room = MAX_EXCERPT_CHARS - length
        if room < 65:
            break
        snippet = snippet[:room]
        chunks.append({"id": f"P{len(chunks)+1}", "text": snippet})
        length += len(snippet)
        if len(chunks) >= MAX_PARAGRAPHS:
            break
    return chunks if length >= 260 and len(chunks) >= 2 else []


def extract_paragraphs(source: bytes) -> list[dict]:
    """Extract bounded article prose from HTML paragraphs or article JSON-LD."""
    parser = ParagraphExtractor()
    parser.feed(source.decode("utf-8", errors="replace"))
    preferred = [text for text, inside in parser.paragraphs if inside]
    if sum(map(len, preferred)) >= 260:
        chosen = _short_chunks(preferred)
        if chosen:
            return chosen
    # JSON-LD can contain real articleBody even on JS-rendered news sites.
    body = _structured_article_body(parser.structured)
    if body:
        fragments = re.split(r"\n\s*\n", body)
        if len(fragments) < 2:
            # Prefer sentence groups over splitting on arbitrary characters.
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", body)
            fragments = []
            current = ""
            for sentence in sentences:
                if current and len(current) + len(sentence) > 270:
                    fragments.append(current.strip())
                    current = ""
                current += " " + sentence
            if current.strip():
                fragments.append(current.strip())
        chunks = _short_chunks(fragments)
        if chunks:
            return chunks
    # Only use outside-article paragraphs when there is substantial coherent prose.
    all_text = [text for text, _inside in parser.paragraphs]
    if len(all_text) >= 3 and sum(map(len, all_text)) >= 700:
        return _short_chunks(all_text)
    return []



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
    client = opener or build_opener(NoRedirect())
    original_host = host
    current = url
    body = b""
    for hop in range(MAX_SAME_HOST_REDIRECTS + 1):
        request = Request(current, headers={
            "Accept": "text/html",
            "Accept-Language": "en",
            "User-Agent": "XNewsEditorialReview/1.0 (human review; no crawling)",
        }, method="GET")
        try:
            with client.open(request, timeout=TIMEOUT_SECONDS) as response:
                # Even custom test clients must not silently follow redirects.
                if response.geturl() != current:
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
            break
        except HTTPError as exc:
            # Follow at most two *same-host* HTTPS canonical redirects. No
            # cross-domain redirects, paywall workarounds or cookies.
            if exc.code not in (301, 302, 303, 307, 308) or hop >= MAX_SAME_HOST_REDIRECTS:
                result["reason"] = ("redirect_blocked" if 300 <= exc.code < 400
                                    else "http_unavailable")
                return result
            location = exc.headers.get("Location", "")
            next_url = urljoin(current, location)
            if (not location or public_article_host(next_url) != original_host or
                    urlsplit(next_url).hostname != original_host or next_url == current):
                result["reason"] = "redirect_blocked"
                return result
            try:
                (dns_check or require_public_dns)(original_host)
            except (ValueError, OSError, socket.gaierror):
                result["reason"] = "dns_not_public_or_unavailable"
                return result
            current = next_url
        except (URLError, OSError, ValueError, TimeoutError):
            result["reason"] = "network_or_http_error"
            return result
    excerpts = extract_paragraphs(body)
    if not excerpts:
        result["reason"] = "no_reliable_article_text"
        return result
    result.update(status="extracted_unverified", reason=None, paragraphs=excerpts)
    return result
