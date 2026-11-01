/**
 * Shared, pure menu taxonomy. Trending is a ranking of news (not a separate
 * region), and global/India partition the same deduplicated public news pool.
 * No requests, storage access, cookies, personal data, AI or X posting.
 */
const INDIA_MARKERS = /\b(?:india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|gurugram|noida|rbi|sebi|nifty|sensex|nse|bse|rupee|rupees|lakh|crore|isro|aadhaar|upi)\b/i;
const INDIA_FOCUSED_SOURCES = new Set(["Inc42 India Startups","ET Entrepreneur India Startups"]);
export const NEWS_VIEWS = Object.freeze(["all","trending","global","india"]);

export function isIndiaArticle(item) {
  return item?.kind === "news" && (item.region === "india" ||
    INDIA_FOCUSED_SOURCES.has(item.publisher) ||
    INDIA_MARKERS.test(item.title || ""));
}
// Keep the same conservative cross-source duplicate rules as the collector.
// Different numbers or company lead terms are *not* the same news event.
const IGNORE=new Set(["the","a","an","and","or","but","of","in","on","for","to",
  "with","at","by","from","as","after","before","new","latest","says",
  "report","reports","news","update","updates"]);
function headlineTokens(title){
  return (String(title||"").toLowerCase().match(/[a-z0-9]+(?:[.][0-9]+)?/g)||[])
    .filter(word=>!IGNORE.has(word));
}
export function nearIdenticalHeadlines(a,b){
  const aTokens=headlineTokens(a),bTokens=headlineTokens(b);
  const first=new Set(aTokens),second=new Set(bTokens);
  if(first.size<6||second.size<6)return false;
  const numbers=values=>values.filter(x=>/\d/.test(x)).join("|");
  if(numbers(aTokens)!==numbers(bTokens)||
     aTokens.slice(0,2).join("|")!==bTokens.slice(0,2).join("|"))return false;
  const shared=[...first].filter(x=>second.has(x)).length;
  return shared>=6 && shared/(first.size+second.size-shared)>=0.84;
}
export function eligibleNews(items, stageOf, storyKey) {
  const seen = new Set(), accepted=[];
  for(const item of items){
    if(item.kind!=="news"||item.history_only||
       ["copied","archived"].includes(stageOf(item)))continue;
    const key=storyKey(item.source_url)||item.id;
    if(seen.has(key)||accepted.some(previous=>nearIdenticalHeadlines(item.title,previous.title)))continue;
    seen.add(key);accepted.push(item);
  }
  return accepted;
}
function dateValue(item) {
  const value = new Date(item.published_at || item.updated_at).getTime();
  return Number.isFinite(value) ? value : 0;
}
export function topNews(items, limit=5) {
  return [...items].sort((a,b) =>
    (b.trend_score||0)-(a.trend_score||0) ||
    dateValue(b)-dateValue(a) || (a.index||0)-(b.index||0)).slice(0,limit);
}
export function newsInSection(items, view, trending=topNews(items)) {
  const trendingIds = new Set(trending.map(item=>item.id));
  return items.filter(item =>
    (view !== "india" || isIndiaArticle(item)) &&
    (view !== "global" || !isIndiaArticle(item)) &&
    (view !== "trending" || trendingIds.has(item.id))
  );
}

/** Public static Global/India queues are already ranked at collection time.
 * Preserve that rank in both views. Live Worker feeds without this ranking
 * continue to use timestamp order; workflow and archive are unaffected.
 */
export function orderPublicNews(items, view, fromLive=false) {
  const value=Array.isArray(items)?[...items]:[];
  if(!fromLive && (view==="global" || view==="india")) {
    return value.sort((a,b)=>(a.index??0)-(b.index??0) ||
      dateValue(b)-dateValue(a));
  }
  if(view==="trending")return value.sort((a,b)=>
    (b.trend_score||0)-(a.trend_score||0) ||
    dateValue(b)-dateValue(a) || (a.index||0)-(b.index||0));
  return value.sort((a,b)=>dateValue(b)-dateValue(a) ||
    (a.index||0)-(b.index||0));
}

/** Counts for the same already-filtered and deduplicated candidate list shown
 * in the UI, *before* selecting a topic. Never pad absent categories.
 * This only describes the current view, not the entire internet or RSS index.
 */
export function topicAvailability(items) {
  const counts={all:0,technology:0,world:0,policy:0,factcheck:0,saas:0,markets:0};
  for(const item of Array.isArray(items)?items:[]) {
    if(!item || typeof item!=="object")continue;
    counts.all++;
    if(Object.hasOwn(counts,item.category) && item.category!=="all")counts[item.category]++;
  }
  return counts;
}
