"""One-off, bounded GET preflight for two documented official RSS endpoints.

Metadata-only. No article page fetching, no images downloaded, no X calls,
no API keys, no storage writes. Verification is informational; a feed that
does not respond should be disabled before any production release.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from newsbot.core import fetch_feed, parse_feed
from newsbot.regions import is_india_article, explicit_india_sources

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={
  "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
  "https://www.federalreserve.gov/feeds/press_all.xml",
  "https://www.rbi.org.in/pressreleases_rss.xml",
}
def probe():
    extras=json.loads((ROOT/"config/extra-news-sources.json").read_text(encoding="utf-8"))
    targets=[s for s in extras if s.get("source_type")=="official_primary" and s.get("url") in ALLOWED]
    now=datetime.now(timezone.utc)
    # Official PIB regions are alternate RSS listings; diagnose, don't silently
    # insert a new feed until a valid parser-compatible endpoint is confirmed.
    pib={"name":"PIB alternate RSS diagnostic","region":"india","category":"policy"}
    targets += [
        {**pib,"url":"https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"},
        {**pib,"url":"https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=48"},
    ]
    results=[]
    for source in targets:
        result={"publisher":source["name"],"status":"unverified",
                "items":0,"recent_36h":0,"recent_72h":0,"images":0,"region":source["region"]}
        try:
            raw=fetch_feed(source["url"],timeout=9,max_bytes=500_000)
            xml=ET.fromstring(raw)
            result["xml_root"]=xml.tag[:85]
            result["xml_items"]=len(xml.findall("./channel/item"))
            first=xml.find("./channel/item")
            if first is not None:
                result["rss_fields"]=sorted({x.tag.split("}")[-1] for x in first})[:16]
                result["has_title"]=bool(first.findtext("title"))
                result["has_pub_date"]=bool(first.findtext("pubDate"))
                result["has_link"]=bool(first.findtext("link"))
                from newsbot.core import parse_date
                result["pub_date_parses"]=parse_date(first.findtext("pubDate")) is not None
                result["link_scheme"]=(first.findtext("link") or "").split(":",1)[0][:9]

            result["xml_bytes"]=len(raw)
            items=parse_feed(raw,source["name"],source["category"])
            recent=[x for x in items
                    if now-timedelta(hours=36)<=datetime.fromisoformat(x.published_at)
                    <=now+timedelta(minutes=10)]
            india_window=[x for x in items if now-timedelta(hours=72)<=datetime.fromisoformat(x.published_at)<=now+timedelta(minutes=10)]
            result.update(recent_72h=len(india_window),status="rss_ok" if items else "empty",items=len(items),
                          recent_36h=len(recent),images=sum(bool(x.image_url) for x in recent))
            region=explicit_india_sources(extras)
            result["recent_in_expected_region"]=sum(
                is_india_article(item,region)==(source["region"]=="india")
                for item in recent)
        except Exception as exc:
            result["status"]="fetch_or_parse_error:"+type(exc).__name__
        results.append(result)
    print("OFFICIAL PUBLIC RSS PREFLIGHT — READ ONLY")
    for result in results:
        print(json.dumps(result,ensure_ascii=False))
    return results

if __name__=="__main__":
    probe()
