/** Merge approved, dated public daily stories missing from a fresh live snapshot.
 * No network, storage, X, or publisher fetches. Live items take priority.
 */
import {nearIdenticalHeadlines} from "./news-sections.mjs";
const REGIONS = [["news", "global", 36, 7], ["india_news", "india", 72, 8]];
function cleanLink(value) {
  if (typeof value !== "string" || value.length > 2000) return "";
  try {
    const url=new URL(value);
    if (url.protocol!=="https:" || url.username || url.password || url.port ||
        url.hostname==="localhost" || /\s/.test(value)) return "";
    for (const key of [...url.searchParams.keys()])
      if (/^utm_/i.test(key) || ["fbclid","gclid","mc_cid","mc_eid"].includes(key.toLowerCase()))
        url.searchParams.delete(key);
    url.hash="";
    url.pathname=url.pathname.replace(/\/+$/,"") || "/";
    return url.href;
  } catch {return "";}
}
function eligible(item, region, hours, nowMs) {
  if (!item || typeof item!=="object" || Array.isArray(item) ||
      item.region!==region || typeof item.publisher!=="string" || !item.publisher.trim() ||
      typeof item.title!=="string" || !item.title.trim() || !cleanLink(item.source_url))
    return false;
  const stamp=Date.parse(item.published_at);
  return Number.isFinite(stamp) && stamp<=nowMs+10*60_000 &&
    stamp>=nowMs-hours*60*60_000;
}
/** Keep only attributed HTTPS stories within the regional time windows and caps.
 * The additions counts are non-sensitive provenance for the UI.
 */
export function supplementLiveNews(staticData, liveData, nowMs=Date.now()) {
  if (staticData?.schema_version!==1 || liveData?.schema_version!==1 ||
      !Number.isFinite(nowMs)) throw new TypeError("Invalid public news snapshot");
  const combined={...liveData}, dailyAdditions={global:0,india:0};
  for (const [field, region, hours, publisherCap] of REGIONS) {
    const live=Array.isArray(liveData[field]) ? liveData[field] : [];
    const daily=Array.isArray(staticData[field]) ? staticData[field] : [];
    const output=[],seen=new Set(),publisherCounts=new Map();
    function include(item,isSupplement) {
      if (output.length>=50 || !eligible(item,region,hours,nowMs))return;
      const key=cleanLink(item.source_url);
      if (seen.has(key) || output.some(prev=>nearIdenticalHeadlines(prev.title,item.title)))return;
      const count=publisherCounts.get(item.publisher)||0;
      if (count>=publisherCap)return;
      seen.add(key);publisherCounts.set(item.publisher,count+1);output.push(item);
      if (isSupplement)dailyAdditions[region]++;
    }
    live.slice(0,50).forEach(item=>include(item,false));
    daily.slice(0,50).forEach(item=>include(item,true));
    combined[field]=output;
  }
  return {data:combined,dailyAdditions};
}
