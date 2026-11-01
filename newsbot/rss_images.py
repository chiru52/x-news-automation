"""Read article-specific image metadata already embedded in publisher RSS/Atom.

No article page fetch, logo fetching, image downloading, new APIs, or paid service.
Inline HTML images are considered only inside *this article's* description or
content:encoded, after media:thumbnail, media:content, and image enclosures.
"""
from html.parser import HTMLParser
from urllib.parse import urlsplit
import re

MEDIA_NS = "{http://search.yahoo.com/mrss/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif"}
NON_ARTICLE_ARTWORK = re.compile(
    r"(?:^|[/_.-])(?:avatar|logo|favicon|icon|sprite|tracking|tracker|pixel|"
    r"spacer|placeholder|blank|transparent|advert|banner-ad|profile-photo)"
    r"(?:[/_.-]|$)|(?:[?&](?:width|w|size)=)(?:[1-9]|[1-9][0-9])(?:[&#]|$)",
    re.I,
)


def safe_image_url(value):
    if not isinstance(value, str) or not 0 < len(value) <= 1400:
        return ""
    if (any(ord(c) <= 32 or ord(c) >= 127 or c in ("<", ">", '"', "'", chr(92))
            for c in value) or
            re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.I)):
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not host or len(host) > 250 or
                parts.username or parts.password or parts.port is not None or
                host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test")) or
                ":" in host or re.fullmatch(r"\d+(?:\.\d+){3}", host) or
                re.search(r"\.(?:svgz?|gif|ico|html?|js|xml|pdf)$", parts.path, re.I) or
                NON_ARTICLE_ARTWORK.search(parts.path+"?"+parts.query)):
            return ""
        return value
    except ValueError:
        return ""


def _srcset_image(value):
    """Accept a concrete, large-resolution article image from an RSS HTML srcset."""
    for entry in reversed((value or "").split(",")[:12]):
        parts = entry.strip().split()
        if len(parts) < 2:
            continue
        descriptor = parts[-1].lower()
        if not (re.fullmatch(r"\d+w", descriptor) and int(descriptor[:-1]) >= 300 or
                re.fullmatch(r"[1-9](?:\.\d+)?x", descriptor) and
                float(descriptor[:-1]) >= 1.5):
            continue
        url = safe_image_url(parts[0])
        if url:
            return url
    return ""


class _StoryImageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image_url = ""
        self.examined = 0

    def handle_starttag(self, tag, attrs):
        if self.image_url or self.examined >= 12 or tag.lower() not in ("img", "source"):
            return
        data = dict(attrs)
        if tag.lower() == "source" and data.get("type", "").lower() not in (
                "", "image/jpeg", "image/png", "image/webp", "image/avif"):
            return
        self.examined += 1
        try:
            width = int(str(data.get("width", "0")).replace("px", ""))
            height = int(str(data.get("height", "0")).replace("px", ""))
        except ValueError:
            return
        if 0 < width < 160 or 0 < height < 90:
            return
        candidates = (
            data.get("data-src"), data.get("data-original"), data.get("data-lazy-src"),
            _srcset_image(data.get("srcset", "")),
            data.get("src"),
        )
        for value in candidates:
            url = safe_image_url(value)
            if url:
                self.image_url = url
                break


def image_from_embedded_html(value):
    """Only use supplied item-level HTML; never resolve relative links or fetch pages."""
    if not isinstance(value, str) or len(value) > 100_000:
        return ""
    parser = _StoryImageParser()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, TypeError):
        return ""
    return parser.image_url


def article_image(item):
    """Extract images from the story item, never from channel / feed artwork."""
    def valid(element, *, thumbnail=False, require_type=False):
        typ = (element.get("type") or "").split(";", 1)[0].lower()
        if require_type and typ not in ALLOWED_IMAGE_TYPES:
            return ""
        medium = (element.get("medium") or "").lower()
        url = safe_image_url(element.get("url") or element.get("href"))
        if not url:
            return ""
        try:
            width, height = int(element.get("width", 0)), int(element.get("height", 0))
        except ValueError:
            return ""
        if (0 < width < 160) or (0 < height < 90):
            return ""
        image_ext = re.search(r"\.(?:jpe?g|png|webp|avif)$", urlsplit(url).path, re.I)
        if not (thumbnail or typ in ALLOWED_IMAGE_TYPES or medium == "image" or image_ext):
            return ""
        return url

    for parent in [item, *item.findall(f"{MEDIA_NS}group")]:
        for element in parent.findall(f"{MEDIA_NS}thumbnail"):
            url = valid(element, thumbnail=True)
            if url:
                return url
        for element in parent.findall(f"{MEDIA_NS}content"):
            url = valid(element)
            if url:
                return url
    for element in item.findall("enclosure") + [
            x for x in item.findall(f"{ATOM_NS}link") if x.get("rel") == "enclosure"]:
        url = valid(element, require_type=True)
        if url:
            return url

    # HTML within the article's own RSS summary or content, never the feed logo.
    for path in ("description", f"{CONTENT_NS}encoded",
                 f"{ATOM_NS}summary", f"{ATOM_NS}content"):
        node = item.find(path)
        if node is not None:
            url = image_from_embedded_html(node.text)
            if url:
                return url
    return ""
