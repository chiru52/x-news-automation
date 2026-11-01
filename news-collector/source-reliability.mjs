/** Source availability fallback. No extra RSS requests and no extra KV writes.
 * Only recover already-public, recent headlines for a publisher whose feed
 * actually failed this collection. Never manufacture current article dates.
 */
import {safeNewsImage} from "../dashboard/news-image.mjs";
const PREVIOUS_MAX_AGE_MS=90*60*1000;
const HEADLINE_MAX_AGE_MS=36*60*60*1000;
const INDIA_HEADLINE_MAX_AGE_MS=72*60*60*1000;
const FUTURE_ALLOWANCE_MS=10*60*1000;
function safeHttps(raw) {
  if(typeof raw!=="string"||raw.length>2000||/\s/.test(raw))return false;
  try{
    const u=new URL(raw);
    return u.protocol==="https:"&&!u.username&&!u.password&&
      u.hostname!=="localhost"&&!/^\d+(?:\.\d+){3}$/.test(u.hostname);
  }catch{return false;}
}
export function recoverRecentStories(snapshot,failedFeeds,nowMs) {
  if(!snapshot||snapshot.schema_version!==1||!Array.isArray(snapshot.news)||
    !Array.isArray(snapshot.india_news)||snapshot.news.length>50||
    snapshot.india_news.length>50||!Array.isArray(failedFeeds)||failedFeeds.length>32)return [];
  const snapshotTime=new Date(snapshot.generated_at).getTime();
  if(!Number.isFinite(snapshotTime)||snapshotTime>nowMs+FUTURE_ALLOWANCE_MS||
     nowMs-snapshotTime>PREVIOUS_MAX_AGE_MS)return [];
  const byName=new Map(failedFeeds.filter(feed=>feed&&
    typeof feed.name==="string"&&safeHttps(feed.url)&&
    ["technology","saas","markets","world","policy","factcheck"].includes(feed.category)).map(feed=>[feed.name,feed]));
  const accepted=[],seen=new Set();
  for(const item of [...snapshot.india_news,...snapshot.news]){
    if(!item||typeof item!=="object"||!byName.has(item.publisher)||
      !/^[0-9a-f]{24}$/.test(item.id||"")||seen.has(item.id)||
      !safeHttps(item.source_url)||typeof item.title!=="string"||
      item.title.length<10||item.title.length>260||
      !["india","global"].includes(item.region)||item.status!=="unverified"||
      item.category!==byName.get(item.publisher).category)continue;
    const published=new Date(item.published_at).getTime();
    if(!Number.isFinite(published)||nowMs-published>(item.region==="india"?INDIA_HEADLINE_MAX_AGE_MS:HEADLINE_MAX_AGE_MS)||
      published>nowMs+FUTURE_ALLOWANCE_MS)continue;
    seen.add(item.id);
    accepted.push({
      title:item.title,source_url:item.source_url,publisher:item.publisher,
      feed_url:byName.get(item.publisher).url,
      category:item.category,region:item.region,
      published_at:item.published_at,
      source_preview:typeof item.source_preview==="string"&&
        item.source_preview.length<=170?item.source_preview:"",
      image_url:safeNewsImage(item.image_url),
      carried_from_previous:true,
    });
    if(accepted.length>=100)break;
  }
  return accepted;
}
export function coverageSummary(sources,results,carriedNews=0,carriedIndia=0){
  const failed=results.filter(entry=>entry.error);
  return {
    sources_checked:sources.length,
    sources_failed:failed.length,
    sources_with_recent_stories:results.filter(entry=>!entry.error&&entry.articles.length>0).length,
    india_sources_checked:sources.filter(feed=>feed.region==="india").length,
    india_sources_with_recent_stories:results.filter(entry=>
      entry.feed?.region==="india"&&!entry.error&&entry.articles.length>0).length,
    india_sources_failed:failed.filter(entry=>entry.feed?.region==="india").length,
    retained_news:carriedNews,
    retained_india:carriedIndia,
  };
}
