/**
 * SignalDesk's shared RSS collector. One Cron invocation every 15 minutes,
 * one public KV snapshot for all visitors. No per-visitor RSS fetches.
 *
 * No AI inference, GitHub credentials, user data, X APIs, posting, or DMs.
 * Fresh collection is exclusively in scheduled(); fetch() only reads KV.
 */
import { XMLParser } from "fast-xml-parser";
import feeds from "../config/sources.json" with {type:"json"};
import newSources from "../config/extra-news-sources.json" with {type:"json"};
import {ARCHIVE_TTL_SECONDS, archiveDate, historyKey, mergeDailyArchive, historyParams, queryArchive} from "./archive.mjs";
import {sameNewsEvent, editorialSignals} from "./intelligence.mjs";
import {recoverRecentStories,coverageSummary} from "./source-reliability.mjs";
import {imageFromRssEntry, safeNewsImage} from "../dashboard/news-image.mjs";

export const CRON = "*/15 * * * *";
const MAX_AGE_MS = 36 * 60 * 60 * 1000;
const INDIA_MAX_AGE_MS = 72 * 60 * 60 * 1000; // Match India daily preview, including weekends.
const MAX_FUTURE_MS = 10 * 60 * 1000;
const MAX_FEED_BYTES = 400_000;
const MAX_ITEMS_PER_FEED = 75;
const MAX_STORIES = 50;
const MAX_INDIA_STORIES = 50;
const MIN_STORIES = 5;
const MAX_PER_SOURCE = 7;
const MAX_CONCURRENT = 4;
const FETCH_TIMEOUT_MS = 9_000;
const SNAPSHOT_KEY = "signaldesk:news:snapshot:v1";
const SAFE_CATEGORIES = ["technology", "saas", "markets", "world", "policy", "factcheck"];
const WORDS = /(fact.?check|misinformation|disinformation|election|parliament|geopolitic|diplomac|government|policy|tariff|trade|war|conflict|summit|treaty|foreign|economy|inflation|business|ai|artificial intelligence|technology|software|startup|saas|enterprise|cloud|launch|product|funding|invest|revenue|earnings|market|shares|stocks|business|security|developer|openai|anthropic|nvidia|microsoft|google|apple|finance|bank|economy|nifty|sensex|rbi|sebi|ipo|nse|bse|rupee|bengaluru|mumbai|indian)/i;
const SPAM = /\b(subscribe now|sponsored|advertisement|coupon|giveaway|deal of the day|best discounts)\b/i;
const INDIA_MARKERS = /\b(?:india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|gurugram|noida|rbi|sebi|nifty|sensex|nse|bse|rupee|rupees|lakh|crore|isro|aadhaar|upi|fintech india)\b/i;
const INDIA_PREVIEW_CONTEXT = /\b(?:in india|across india|india-based|indian startup|indian government|reserve bank of india|india\x27s market|indian stock market)\b/i;
// Strong India-specific institutions and market terms in RSS summaries; generic publisher country doesn't qualify.
const INDIA_LOCAL_CONTEXT = /\b(?:rbi|reserve bank of india|sebi|nifty|sensex|bse|nse|npci|aadhaar|upi|rupees?|lakhs?|crores?|bengaluru|bangalore|hyderabad|gurugram|mumbai|new delhi)\b/i;
function isIndiaStory(article) {
  // A country-specific source may supply stories without naming India in the
  // headline. Generic Indian technology publishers are NOT proof of relevance.
  return article.region === "india" || INDIA_MARKERS.test(article.title);
}

const XML = new XMLParser({
  ignoreAttributes:false, attributeNamePrefix:"@_", removeNSPrefix:true,
  textNodeName:"#text", processEntities:false, trimValues:true,
  parseTagValue:false, parseAttributeValue:false,
});
const BASE_HEADERS = {
  "content-type":"application/json; charset=utf-8",
  "cache-control":"public, max-age=60, stale-while-revalidate=300",
  "x-content-type-options":"nosniff",
  "referrer-policy":"no-referrer",
  // Every cached response varies by browser origin; no wildcard access.
  "vary":"Origin",
};
function res(status, body, headers={}) {
  return new Response(JSON.stringify(body), {status, headers:{...BASE_HEADERS,...headers}});
}
function unescapeText(v) {
  return String(v ?? "")
    .replace(/&amp;/gi,"&").replace(/&lt;/gi,"<").replace(/&gt;/gi,">")
    .replace(/&quot;/gi,'"').replace(/&#39;|&apos;/gi,"'")
    .replace(/&#(x[0-9a-f]+|\d+);/gi, (match, n) => {
      const cp = n[0].toLowerCase()==="x" ? parseInt(n.slice(1),16) : Number(n);
      return cp > 0 && cp <= 0x10ffff && ![0x2028,0x2029].includes(cp)
        ? String.fromCodePoint(cp) : "";
    });
}
function plain(value, max=400) {
  const v = typeof value === "object" && value !== null
    ? (value["#text"] ?? "") : value;
  const text = unescapeText(v).replace(/<[^>]*>/g," ")
    .replace(/[\x00-\x1f\x7f]/g," ").replace(/\s+/g," ").trim();
  return text.slice(0,max);
}
function validUrl(value) {
  if (typeof value !== "string" || value.length > 2000 || /\s/.test(value)) return "";
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password ||
        url.hostname === "localhost" || /^\d+(\.\d+){3}$/.test(url.hostname)) return "";
    for (const key of [...url.searchParams.keys()]) {
      if (/^utm_/i.test(key) || ["fbclid","gclid","mc_cid","mc_eid"].includes(key.toLowerCase()))
        url.searchParams.delete(key);
    }
    url.hash="";
    url.pathname=url.pathname.replace(/\/+$/,"") || "/";
    return url.href;
  } catch { return ""; }
}
function atomLink(entry) {
  const links = Array.isArray(entry.link) ? entry.link : [entry.link];
  const selected = links.find(e => e && (typeof e === "string" ||
      !e["@_rel"] || e["@_rel"]==="alternate"));
  return typeof selected === "string" ? selected : selected?.["@_href"] ?? "";
}
export function parseFeed(xml, feed, nowMs=Date.now()) {
  if (typeof xml !== "string" || xml.length > MAX_FEED_BYTES * 1.2) throw Error("Invalid feed");
  const root=XML.parse(xml);
  // A 200 response containing HTML (or malformed markup) is not a healthy feed.
  if(/<!DOCTYPE|<!ENTITY/i.test(xml) ||
     !(root?.rss?.channel && typeof root.rss.channel==="object" ||
       root?.feed && typeof root.feed==="object"))
    throw Error("Invalid RSS or Atom document");
  const raw = root?.rss?.channel?.item ?? root?.feed?.entry ?? [];
  const entries=(Array.isArray(raw) ? raw : [raw]).slice(0,MAX_ITEMS_PER_FEED);
  const result=[];
  for (const entry of entries) {
    if (!entry || typeof entry !== "object") continue;
    const title=plain(entry.title,260);
    const link=validUrl(entry.link && !root?.feed ? plain(entry.link,2000) : atomLink(entry));
    const date=new Date(plain(entry.pubDate ?? entry.published ?? entry.updated ?? entry.date,65)).getTime();
    const preview=plain(entry.description ?? entry.summary ?? "",170);
    const region=feed.region === "india" || INDIA_MARKERS.test(title) ||
      INDIA_PREVIEW_CONTEXT.test(preview) || INDIA_LOCAL_CONTEXT.test(preview) ? "india" : "global";
    // Country attribution precedes freshness filtering: 36–72h India articles
    // are legitimate weekend coverage, not stale Global stories.
    if (!title || !link || !Number.isFinite(date) ||
        date < nowMs - (region==="india" ? INDIA_MAX_AGE_MS : MAX_AGE_MS) ||
        date > nowMs + MAX_FUTURE_MS ||
        SPAM.test(title) || !WORDS.test(title)) continue;
    const image_url=imageFromRssEntry(entry);
    result.push({
      title, source_url:link, publisher:feed.name, feed_url:feed.url,
      category:feed.category, published_at:new Date(date).toISOString(),
      source_preview:feed.headline_only ? "" :
        preview.length>=35 && preview.toLowerCase()!==title.toLowerCase() ? preview : "",
      image_url:feed.disable_images ? "" : image_url,
      region,
    });
  }
  return result;
}
function approximateXLength(text) {
  return String(text).replace(/https?:\/\/[^\s]+/gi,"x".repeat(23)).length;
}
function makePost(item) {
  const isQuestion=/\?$/.test(item.title) || /\b(?:will|could|might|may)\b/i.test(item.title);
  let thought = {
    technology:"I'm curious what changes for people actually using the technology.",
    saas:"What matters next is whether customers see a real difference.",
    markets:"I'd look at the underlying figures before drawing conclusions.",
    world:"I'd check several original reports before reaching a conclusion.",
    policy:"I'd read the underlying policy or official statement before reacting.",
    factcheck:"This is a publisher fact-check. I'd read the evidence before repeating any claim.",
  }[item.category];
  if (isQuestion) thought="It's still a question. I'd check the actual details before making a call.";
  if (/earnings/i.test(item.title)) thought="I'd compare the actual earnings numbers before jumping to conclusions.";
  if (/funding|raises?\s+[$€£₹]/i.test(item.title)) thought="I'm more interested in what the team builds next than the headline alone.";
  const reserve=2+approximateXLength(item.source_url)+2+thought.length;
  const allowed=Math.max(15,270-reserve);
  const title=item.title.length > allowed ? item.title.slice(0,allowed-1).trimEnd()+"…" : item.title;
  return title+"\n\n"+thought+"\n\n"+item.source_url;
}
export async function publicItem(article, allArticles=[article], nowMs=Date.now()) {
  const buf=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(article.source_url));
  const id=[...new Uint8Array(buf)].slice(0,12).map(v=>v.toString(16).padStart(2,"0")).join("");
  const signals=editorialSignals(article,allArticles,nowMs);
  const post=makePost(article);
  return {
    id,title:article.title,description:"Publisher report. Verify all claims before sharing.",
    source_preview:article.source_preview,
    image_url:safeNewsImage(article.image_url),
    context_status:article.source_preview ? "rss_preview" : "headline_only",
    publisher:article.publisher,source_url:article.source_url,post,
    category:article.category,region:isIndiaStory(article) ? "india" : "global",
    published_at:article.published_at,status:"unverified",
    trend_score:signals.score,coverage_feeds:signals.coverage_feeds,
    trend_reason:signals.reason,
  };
}
export function selectIndiaStories(stories) {
  const perSource = new Map();
  const selected=[];
  const candidates=stories.filter(isIndiaStory).sort((a,b)=>
    new Date(b.published_at)-new Date(a.published_at));
  for(const story of candidates){
    if(!SAFE_CATEGORIES.includes(story.category)) continue;
    if(selected.some(previous=>sameNewsEvent(previous,story))) continue;
    if((perSource.get(story.publisher)||0)>=8) continue;
    selected.push(story);
    perSource.set(story.publisher,(perSource.get(story.publisher)||0)+1);
    if(selected.length>=MAX_INDIA_STORIES) break;
  }
  return selected;
}
export function selectStories(stories) {
  const filtered=stories.filter(story=>!isIndiaStory(story)).sort((a,b)=>
    new Date(b.published_at)-new Date(a.published_at));
  const sourceCounts=new Map(),accepted=[];
  const buckets=Object.fromEntries(SAFE_CATEGORIES.map(c=>[c,[]]));
  for (const story of filtered) {
    if (!SAFE_CATEGORIES.includes(story.category)) continue;
    if (accepted.some(previous=>sameNewsEvent(previous,story))) continue;
    const count=sourceCounts.get(story.publisher)||0;
    if (count >= MAX_PER_SOURCE) continue;
    accepted.push(story);
    sourceCounts.set(story.publisher,count+1);
    buckets[story.category].push(story);
  }
  const result=[];
  while (result.length < MAX_STORIES) {
    let changed=false;
    for (const category of SAFE_CATEGORIES) {
      if (buckets[category].length && result.length < MAX_STORIES) {
        result.push(buckets[category].shift());
        changed=true;
      }
    }
    if (!changed) break;
  }
  return result;
}
async function collectOne(feed, fetcher, nowMs) {
  if (!SAFE_CATEGORIES.includes(feed.category) || !validUrl(feed.url)) return {articles:[],error:true,feed};
  try {
    const response=await fetcher(feed.url,{headers:{"user-agent":"SignalDeskRSSReader/1.0"},
      signal:AbortSignal.timeout(FETCH_TIMEOUT_MS)});
    if (!response.ok || Number(response.headers.get("content-length")||0)>MAX_FEED_BYTES)
      throw Error("Feed unavailable");
    const raw=await response.text();
    if (new TextEncoder().encode(raw).length>MAX_FEED_BYTES) throw Error("Feed too large");
    return {articles:parseFeed(raw,feed,nowMs),error:false,feed};
  } catch { return {articles:[],error:true,feed}; }
}
export async function collect(env, {fetcher=fetch,nowMs=Date.now()}={}) {
  if (!env?.NEWS_CACHE?.put) throw Error("Shared KV binding missing");
  // Keep the same Cron and two KV writes per successful cycle; no visitor-triggered feeds.
  const sources=[...feeds,...newSources].filter(x=>SAFE_CATEGORIES.includes(x.category)).slice(0,32);
  const results=[];
  for(let i=0;i<sources.length;i+=MAX_CONCURRENT) {
    results.push(...await Promise.all(sources.slice(i,i+MAX_CONCURRENT).map(s=>collectOne(s,fetcher,nowMs))));
  }
  const freshArticles=results.flatMap(x=>x.articles);
  // Never refresh a snapshot on cached stories alone. At least five truly new
  // eligible headlines must arrive before a fresh snapshot is published.
  const freshSelected=selectStories(freshArticles);
  const freshIndia=selectIndiaStories(freshArticles);
  if(freshSelected.length+freshIndia.length < MIN_STORIES)
    return {ok:false,reason:"insufficient_new_stories",count:freshSelected.length};
  const failedFeeds=results.filter(x=>x.error).map(x=>x.feed);
  let carried=[];
  if(failedFeeds.length && env.NEWS_CACHE.get){
    try {
      const previous=await env.NEWS_CACHE.get(SNAPSHOT_KEY);
      carried=recoverRecentStories(previous?JSON.parse(previous):null,failedFeeds,nowMs);
    } catch { /* Fallback is optional; never prevent fresh news updates. */ }
  }
  const allArticles=[...freshArticles,...carried];
  const selected=selectStories(allArticles);
  const indiaSelected=selectIndiaStories(allArticles);
  const news=await Promise.all(selected.map(article=>publicItem(article,allArticles,nowMs)));
  const india_news=await Promise.all(indiaSelected.map(article=>publicItem(article,allArticles,nowMs)));
  const retainedNews=selected.filter(article=>article.carried_from_previous).length;
  const retainedIndia=indiaSelected.filter(article=>article.carried_from_previous).length;
  const warnings=[];
  if(failedFeeds.length)warnings.push("some_feed_sources_unavailable");
  if(retainedNews||retainedIndia)warnings.push("recent_cached_stories_retained");
  const data={schema_version:1,generated_at:new Date(nowMs).toISOString(),news,india_news,drafts:[],
    warnings,coverage:coverageSummary(sources,results,retainedNews,retainedIndia)};
  await env.NEWS_CACHE.put(SNAPSHOT_KEY,JSON.stringify(data));
  // Optional archive is bounded to one day-key per Cron. Failure cannot
  // corrupt or interrupt the working live-feed update.
  let archive_written=false;
  if(env.NEWS_CACHE.get) {
    try {
      const day=archiveDate(nowMs), key=historyKey(day);
      const previous=await env.NEWS_CACHE.get(key,"json");
      const merged=mergeDailyArchive(previous,[...india_news,...news],nowMs);
      await env.NEWS_CACHE.put(key,JSON.stringify(merged),{expirationTtl:ARCHIVE_TTL_SECONDS});
      archive_written=true;
    } catch { /* Keep live RSS available even when history KV fails. */ }
  }
  return {ok:true,count:news.length,archive_written,failed_sources:results.filter(x=>x.error).length};
}
async function handleReadOnlyRequest(request,env) {
  const u=new URL(request.url);
  if (request.method!=="GET" && request.method!=="HEAD")
    return res(405,{error:"Read-only endpoint"});
  if (u.pathname==="/health")
    return res(200,{status:"read_only",x_posting_enabled:false,ai_generation_enabled:false});
  if (u.pathname==="/archive") {
    if (!env?.NEWS_CACHE?.get) return res(503,{error:"Archive cache not configured"});
    const params=historyParams(u);
    if(!params) return res(400,{error:"Invalid archive filters or date"});
    try {
      // Max 30 day-key reads, all public RSS data, no upstream RSS fetch.
      const buckets=await Promise.all(params.dates.map(async day=>{
        try {return await env.NEWS_CACHE.get(historyKey(day),"json");}
        catch {return null;}
      }));
      return res(200,queryArchive(buckets,params));
    } catch {return res(503,{error:"Archive temporarily unavailable"});}
  }
  if (u.pathname!=="/feed") return res(404,{error:"Not found"});
  if (!env?.NEWS_CACHE?.get) return res(503,{error:"Feed cache not configured"});
  try {
    const payload=await env.NEWS_CACHE.get(SNAPSHOT_KEY);
    if (!payload) return res(503,{error:"Feed has not been collected yet"});
    const data=JSON.parse(payload);
    if (data.schema_version!==1 || !Array.isArray(data.news) || data.news.length<MIN_STORIES ||
        !Array.isArray(data.india_news) || data.india_news.length>MAX_INDIA_STORIES ||
        data.india_news.some(item=>item.region!=="india") ||
        !Number.isFinite(new Date(data.generated_at).getTime()))
      return res(503,{error:"Cached feed invalid"});
    if (Date.now()-new Date(data.generated_at).getTime()>90*60*1000)
      return res(503,{error:"Cached feed is stale"});
    return res(200,data);
  } catch { return res(503,{error:"Cached feed unavailable"}); }
}
// Exact public dashboard origins, without credentials or wildcard CORS.
const ALLOWED_DASHBOARD_ORIGINS=new Set([
  "https://news.littlekingchess.com",
  "https://signaldesk-preview.pages.dev",
]);
export async function handleRequest(request,env){
  const response=await handleReadOnlyRequest(request,env);
  const origin=request.headers.get("Origin");
  if(!ALLOWED_DASHBOARD_ORIGINS.has(origin))return response;
  const headers=new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin",origin);
  headers.set("Vary","Origin");
  return new Response(request.method==="HEAD"?null:response.body,{
    status:response.status,statusText:response.statusText,headers,
  });
}
export default {
  fetch:handleRequest,
  async scheduled(controller,env,ctx) {
    // Never triggered by website visitors. No user-provided parameters.
    await collect(env);
  },
};
