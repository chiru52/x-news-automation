"""RSS news collection, filtering and review output. No publishing functionality."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

ATOM = "{http://www.w3.org/2005/Atom}"
HTML_TAGS = re.compile(r"<[^>]*>")
SPACES = re.compile(r"\s+")
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass(frozen=True)
class Article:
    title: str
    link: str
    source: str
    published_at: str
    summary: str = ""
    category: str = "technology"

    @property
    def identity(self) -> str:
        return hashlib.sha256(canonical_url(self.link).encode("utf-8")).hexdigest()


def clean_text(value: str | None) -> str:
    return SPACES.sub(" ", html.unescape(HTML_TAGS.sub(" ", value or ""))).strip()


def canonical_url(value: str) -> str:
    parts = urlsplit((value or "").strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ValueError("Article URL must be HTTP(S)")
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path.rstrip("/") or "/", urlencode(query), ""))


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try:
            value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def parse_feed(data: bytes, source: str, category: str = "technology") -> list[Article]:
    """Parse RSS or Atom without visiting news article links."""
    root = ET.fromstring(data)
    items = root.findall("./channel/item") if root.tag == "rss" else root.findall(f"{ATOM}entry")
    articles = []
    for item in items:
        atom = item.tag == f"{ATOM}entry"
        title = clean_text(item.findtext(f"{ATOM}title" if atom else "title"))
        if atom:
            links = item.findall(f"{ATOM}link")
            chosen = next((el for el in links if el.get("rel", "alternate") == "alternate"), None)
            link = chosen.get("href", "") if chosen is not None else ""
            raw_date = item.findtext(f"{ATOM}published") or item.findtext(f"{ATOM}updated")
            summary = item.findtext(f"{ATOM}summary") or item.findtext(f"{ATOM}content")
        else:
            link = item.findtext("link") or ""
            raw_date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            summary = item.findtext("description")
        published = parse_date(raw_date)
        if not title or published is None:
            continue
        try:
            link = canonical_url(link)
        except ValueError:
            continue
        articles.append(Article(title=title[:400], link=link, source=source,
                                published_at=published.isoformat(), summary=clean_text(summary)[:600],
                                category=category))
    return articles


def fetch_feed(url: str, timeout: int = 12, max_bytes: int = 1_500_000) -> bytes:
    if urlsplit(url).scheme.lower() != "https":
        raise ValueError("Feed sources must use HTTPS")
    req = Request(url, headers={"User-Agent": "XNewsDraftCollector/0.1 (RSS feed reader)"})
    with urlopen(req, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Feed exceeded size limit")
    return data


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen": {}, "seen_titles": {}, "daily_drafts": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(state.get("seen"), dict) and isinstance(state.get("daily_drafts"), dict):
            state.setdefault("seen_titles", {})
            return state
    except (json.JSONDecodeError, OSError, AttributeError):
        pass
    raise ValueError(f"Invalid history: {path}. Refusing to reselect potentially duplicate news.")


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.casefold())


def select_articles(articles: Iterable[Article], state: dict, now: datetime,
                    daily_limit: int = 5, lookback_hours: int = 36,
                    timezone_name: str = "Europe/Stockholm") -> list[Article]:
    """Choose up to daily_limit unique, recently published items per local calendar day."""
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    now = now.astimezone(timezone.utc)
    day = now.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    count = int(state["daily_drafts"].get(day, 0))
    remaining = max(0, daily_limit - count)
    minimum = now - timedelta(hours=lookback_hours)
    state.setdefault("seen_titles", {})
    results = []
    seen_in_run, titles_in_run = set(), set()
    for article in sorted(articles, key=lambda a: a.published_at, reverse=True):
        published = datetime.fromisoformat(article.published_at)
        if published.tzinfo is None:
            continue
        published = published.astimezone(timezone.utc)
        if not minimum <= published <= now + timedelta(minutes=10):
            continue
        key = article.identity
        title = title_key(article.title)
        if (key in state["seen"] or title in state["seen_titles"]
                or key in seen_in_run or title in titles_in_run):
            continue
        if len(results) >= remaining:
            break
        seen_in_run.add(key)
        titles_in_run.add(title)
        results.append(article)
    for article in results:
        state["seen"][article.identity] = now.isoformat()
        state["seen_titles"][title_key(article.title)] = now.isoformat()
    state["daily_drafts"][day] = count + len(results)
    cutoff = now - timedelta(days=45)
    state["seen"] = {key: when for key, when in state["seen"].items()
                     if (parse_date(when) or now) >= cutoff}
    state["seen_titles"] = {key: when for key, when in state["seen_titles"].items()
                            if (parse_date(when) or now) >= cutoff}
    state["daily_drafts"] = {key: count for key, count in state["daily_drafts"].items()
                             if key >= cutoff.date().isoformat()}
    return results


def draft_template(article: Article) -> str:
    """Provide an editorial placeholder; never claim AI has verified the article."""
    note = "Why it matters: [Write one verified insight after reading the article.]"
    link = f"Source: {article.link}"
    allowed = 280 - len(note) - len(link) - 4
    if allowed < 10:
        # Don't output a misleading 280-character post when the URL is too long.
        return f"Review source URL (too long for post): {article.link}\n{note}"
    title = article.title[:allowed]
    if len(article.title) > allowed:
        title = title[:-1].rstrip() + "…"
    return f"{title}\n\n{note}\n\n{link}"


def render_outputs(articles: list[Article], outdir: Path, now: datetime, errors: list[str]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    queue = [{**asdict(item), "draft": draft_template(item), "status": "NEEDS_HUMAN_REVIEW",
              "publishable": False} for item in articles]
    payload = {"generated_at": now.isoformat(), "draft_count": len(queue),
               "publishing_enabled": False, "articles": queue, "feed_errors": errors}
    (outdir / "review_queue.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# News review queue", "", "> No posts were published or sent to Buffer/X.",
             "> Editorial review templates; NOT final AI-written posts.", "",
             f"Generated: {now.isoformat()}", f"Drafts: {len(queue)}", ""]
    if not queue:
        lines += ["No eligible stories found. Check feed availability and logs.", ""]
    for index, item in enumerate(queue, 1):
        lines += [f"## {index}. {item['title']}", "", f"- Source: {item['source']}",
                  f"- Published: {item['published_at']}", f"- Article: {item['link']}",
                  "- Status: NEEDS_HUMAN_REVIEW", "", "```text", item["draft"], "```", ""]
    if errors:
        lines += ["## Feed errors", "", *[f"- {error}" for error in errors], ""]
    (outdir / "review_queue.md").write_text("\n".join(lines), encoding="utf-8")
