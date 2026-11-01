"""One-off, bounded GET preflight for two documented official RSS endpoints.

Metadata-only. No article page fetching, no images downloaded, no X calls,
no API keys, no storage writes. Verification is informational; a feed that
does not respond should be disabled before any production release.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from newsbot.core import fetch_feed, parse_feed
from newsbot.regions import is_india_article, explicit_india_sources

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={
  "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
  "https://www.federalreserve.gov/feeds/press_all.xml",
}
def probe():
    extras=json.loads((ROOT/"config/extra-news-sources.json").read_text(encoding="utf-8"))
    targets=[s for s in extras if s.get("source_type")=="official_primary" and s.get("url") in ALLOWED]
    now=datetime.now(timezone.utc)
    results=[]
    for source in targets:
        result={"publisher":source["name"],"status":"unverified",
                "items":0,"recent_36h":0,"images":0,"region":source["region"]}
        try:
            raw=fetch_feed(source["url"],timeout=9,max_bytes=500_000)
            items=parse_feed(raw,source["name"],source["category"])
            recent=[x for x in items
                    if now-timedelta(hours=36)<=datetime.fromisoformat(x.published_at)
                    <=now+timedelta(minutes=10)]
            result.update(status="rss_ok" if items else "empty",items=len(items),
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
