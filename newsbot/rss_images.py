"""Article-specific RSS/Atom cover images for the existing static preview.

Do not fetch article pages, feed logos or image URLs here. This module only
reads embedded RSS image attributes and passes safe URLs downstream.
"""
from urllib.parse import urlsplit
import re

MEDIA_NS = "{http://search.yahoo.com/mrss/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif"}


def safe_image_url(value):
    if not isinstance(value, str) or not 0 < len(value) <= 1400:
        return ""
    if any(ord(c) <= 32 or ord(c) >= 127 or c in '<>"\'\\' for c in value):
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or not host or len(host) > 250 or
                parts.username or parts.password or parts.port is not None or
                host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test")) or
                ":" in host or re.fullmatch(r"\d+(?:\.\d+){3}", host) or
                re.search(r"\.(?:svgz?|gif|ico|html?|js|xml|pdf)$", parts.path, re.I)):
            return ""
        return value
    except ValueError:
        return ""


def article_image(item):
    """Extract image ONLY from this story's media elements, not channel artwork."""
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
    for entry in item.findall(f"{MEDIA_NS}thumbnail"):
        url = valid(entry, thumbnail=True)
        if url:
            return url
    for entry in item.findall(f"{MEDIA_NS}content"):
        url = valid(entry)
        if url:
            return url
    for entry in item.findall("enclosure") + [
            x for x in item.findall(f"{ATOM_NS}link") if x.get("rel") == "enclosure"]:
        url = valid(entry, require_type=True)
        if url:
            return url
    return ""
