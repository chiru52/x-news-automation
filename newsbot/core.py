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

from .relevance import assess_story

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
                    timezone_name: str = "Europe/Stockholm",
                    category_order: tuple[str, ...] = ("technology", "markets", "saas"),
                    rank_by_relevance: bool = False) -> list[Article]:
    """Select fresh, unique stories fairly across categories and runs in a local day.

    The daily counter is authoritative: newly configured categories cannot override
    the remaining daily limit. Categories with no eligible articles are skipped.
    """
    if now.tzinfo is None:
        raise ValueError("now must contain a timezone")
    now = now.astimezone(timezone.utc)
    local_day = now.astimezone(ZoneInfo(timezone_name)).date()
    day = local_day.isoformat()
    count = int(state["daily_drafts"].get(day, 0))
    remaining = max(0, daily_limit - count)
    min_date = now - timedelta(hours=lookback_hours)
    state.setdefault("seen_titles", {})
    state.setdefault("daily_categories", {})
    category_counts = state["daily_categories"].setdefault(day, {})
    # Rotate the first category so that the extra two of five slots are shared.
    ordered = list(dict.fromkeys(category_order))
    if not ordered:
        raise ValueError("category_order must not be empty")
    rotation = local_day.toordinal() % len(ordered)
    ordered = ordered[rotation:] + ordered[:rotation]
    by_category: dict[str, list[Article]] = {}
    candidates = []
    for item in articles:
        published = datetime.fromisoformat(item.published_at)
        if published.tzinfo is None or not min_date <= published.astimezone(timezone.utc) <= now + timedelta(minutes=10):
            continue
        if item.identity in state["seen"] or title_key(item.title) in state["seen_titles"]:
            continue
        assessment = assess_story(item.title, item.summary, item.category, published, now)
        # Conservative filtering is enabled by the CLI, but stays opt-in for
        # compatibility with the library's existing selection API and tests.
        if rank_by_relevance and not assessment["topic_match"]:
            continue
        candidates.append((item, assessment["score"]))
    if rank_by_relevance:
        candidates.sort(key=lambda entry: (
            -entry[1], -datetime.fromisoformat(entry[0].published_at).timestamp(),
            entry[0].title.casefold(), entry[0].link))
    else:
        candidates.sort(key=lambda entry: entry[0].published_at, reverse=True)
    for item, _score in candidates:
        by_category.setdefault(item.category, []).append(item)
    # Handle any additional categories deterministically after configured ones.
    ordered.extend(sorted(set(by_category) - set(ordered)))
    selected: list[Article] = []
    run_ids: set[str] = set()
    run_titles: set[str] = set()
    while len(selected) < remaining:
        available = []
        for category in ordered:
            bucket = by_category.get(category, [])
            while bucket and (bucket[0].identity in run_ids or title_key(bucket[0].title) in run_titles):
                bucket.pop(0)
            if bucket:
                available.append(category)
        if not available:
            break
        # Pick the category with the fewest drafts so far today, tie by rotation.
        chosen = min(available, key=lambda cat: (category_counts.get(cat, 0), ordered.index(cat)))
        item = by_category[chosen].pop(0)
        selected.append(item)
        run_ids.add(item.identity)
        run_titles.add(title_key(item.title))
        category_counts[chosen] = category_counts.get(chosen, 0) + 1
    for item in selected:
        state["seen"][item.identity] = now.isoformat()
        state["seen_titles"][title_key(item.title)] = now.isoformat()
    state["daily_drafts"][day] = count + len(selected)
    cutoff = now - timedelta(days=45)
    state["seen"] = {key: timestamp for key, timestamp in state["seen"].items()
                     if (parse_date(timestamp) or now) >= cutoff}
    state["seen_titles"] = {key: timestamp for key, timestamp in state["seen_titles"].items()
                            if (parse_date(timestamp) or now) >= cutoff}
    state["daily_drafts"] = {key: total for key, total in state["daily_drafts"].items()
                             if key >= cutoff.date().isoformat()}
    state["daily_categories"] = {key: totals for key, totals in state["daily_categories"].items()
                                 if key >= cutoff.date().isoformat()}
    return selected

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


def render_outputs(articles: list[Article], outdir: Path, now: datetime, errors: list[str],
                   source_diagnostics: list[dict] | None = None) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    queue = []
    for item in articles:
        published = datetime.fromisoformat(item.published_at)
        assessment = assess_story(item.title, item.summary, item.category, published, now)
        queue.append({**asdict(item), "draft": draft_template(item),
                      "status": "NEEDS_HUMAN_REVIEW", "publishable": False,
                      "category_verified": False, "relevance": assessment})
    payload = {"generated_at": now.isoformat(), "draft_count": len(queue),
               "publishing_enabled": False, "articles": queue, "feed_errors": errors,
               "source_diagnostics": source_diagnostics or []}
    (outdir / "review_queue.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# News review queue", "", "> No posts were published or sent to Buffer/X.",
             "> Editorial review templates; NOT final AI-written posts.", "",
             f"Generated: {now.isoformat()}", f"Drafts: {len(queue)}", ""]
    if not queue:
        lines += ["No eligible stories found. Check feed availability and logs.", ""]
    for index, item in enumerate(queue, 1):
        lines += [f"## {index}. {item['title']}", "", f"- Source-assigned category (unverified): {item['category']}", f"- Source: {item['source']}",
                  f"- Published: {item['published_at']}", f"- Article: {item['link']}",
                  f"- Relevance score (heuristic): {item['relevance']['score']}",
                  f"- Matched headline terms: {', '.join(item['relevance']['headline_terms']) or 'none'}",
                  "- Status: NEEDS_HUMAN_REVIEW", "", "```text", item["draft"], "```", ""]
    if errors:
        lines += ["## Feed errors", "", *[f"- {error}" for error in errors], ""]
    if source_diagnostics:
        lines += ["## Source health", "",
                  "Counts reflect parsed RSS entries and fresh entries within the lookback window.",
                  "They do not confirm that a story belongs in the source's category.", ""]
        for stat in source_diagnostics:
            lines.append(f"- {stat['source']} [{stat['category']}]: "
                         f"{stat['parsed_articles']} parsed / {stat['recent_articles']} recent"
                         f" — {stat['status']}")
        lines.append("")
    (outdir / "review_queue.md").write_text("\n".join(lines), encoding="utf-8")
