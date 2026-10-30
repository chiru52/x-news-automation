/**
 * Public, RSS-only, rolling news history. One KV archive bucket per UTC date.
 * No private GitHub drafts, user edits, login records or copied history.
 * All writes happen during the existing 15-minute Cron, never browser requests.
 */
export const ARCHIVE_PREFIX="signaldesk:news:archive:v1:";
export const ARCHIVE_DAYS=30;
export const MAX_PER_DAY=120;
export const ARCHIVE_TTL_SECONDS=32*24*60*60;
export const ARCHIVE_PAGE_SIZE=60;

export function archiveDate(nowMs) {
  return new Date(nowMs).toISOString().slice(0,10);
}
export function archiveDates(nowMs, days) {
  if (![7,30].includes(days)) throw new RangeError("History range must be 7 or 30 days");
  const today=new Date(archiveDate(nowMs)+"T00:00:00Z").getTime();
  return Array.from({length:days},(_,i)=>archiveDate(today-i*86400000));
}
export function validHistoryDate(date, nowMs) {
  if(typeof date!=="string" || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  const t=new Date(date+"T00:00:00Z").getTime();
  const today=new Date(archiveDate(nowMs)+"T00:00:00Z").getTime();
  return Number.isFinite(t) && new Date(t).toISOString().slice(0,10)===date &&
    t<=today && t>=today-(ARCHIVE_DAYS-1)*86400000;
}
export function historyKey(date) {return ARCHIVE_PREFIX+date;}
function safeHistoryItem(item){
  if(!item || typeof item!=="object" || Array.isArray(item) ||
     typeof item.id!=="string" || !/^[a-f0-9]{24}$/.test(item.id) ||
     typeof item.title!=="string" || item.title.length>260 ||
     typeof item.source_url!=="string" || !item.source_url.startsWith("https://") ||
     !["technology","saas","markets"].includes(item.category) ||
     !["india","global"].includes(item.region) ||
     item.status!=="unverified" || typeof item.post!=="string" ||
     item.post.length>900) return false;
  const date=new Date(item.published_at).getTime();
  return Number.isFinite(date);
}
export function mergeDailyArchive(existing, incoming, nowMs) {
  const date=archiveDate(nowMs);
  const keep=new Map();
  const stored=existing && existing.schema_version===1 && existing.date===date &&
    Array.isArray(existing.items) && existing.items.length<=MAX_PER_DAY ? existing.items : [];
  for(const item of [...incoming,...stored]) {
    if(!safeHistoryItem(item)) continue;
    const key=item.source_url;
    if(!keep.has(key)) keep.set(key,item);
    if(keep.size>=MAX_PER_DAY) break;
  }
  return {schema_version:1,date,updated_at:new Date(nowMs).toISOString(),
    items:[...keep.values()]};
}
export function historyParams(url, nowMs=Date.now()){
  const q=url.searchParams.get("q")||"";
  const region=url.searchParams.get("region")||"all";
  const publisher=url.searchParams.get("publisher")||"";
  const date=url.searchParams.get("date");
  const days=Number(url.searchParams.get("days")||7);
  const page=Number(url.searchParams.get("page")||0);
  const category=url.searchParams.get("category")||"all";
  const sort=url.searchParams.get("sort")||"newest";
  const expected=["q","region","publisher","date","days","page","category","sort"];
  if([...url.searchParams.keys()].some(key=>!expected.includes(key)) ||
     new Set([...url.searchParams.keys()]).size!==url.searchParams.size ||
     url.searchParams.size>8 || !["newest","oldest"].includes(sort) || q.length>100 || publisher.length>100 ||
     !["all","india","global"].includes(region) ||
     !["all","technology","saas","markets"].includes(category) ||
     !Number.isInteger(page) || page<0 || page>59 ||
     ![7,30].includes(days) || date!==null && !validHistoryDate(date,nowMs))
    return null;
  return {q:q.trim().toLocaleLowerCase(),region,publisher:publisher.trim(),
    category,sort,page, dates:date ? [date] : archiveDates(nowMs,days),
    days:date ? 1 : days, date:date||null};
}
export function queryArchive(buckets, params) {
  const seen=new Set(), all=[];
  for(const bucket of buckets){
    if(!bucket || bucket.schema_version!==1 ||
       !params.dates.includes(bucket.date) ||
       !Array.isArray(bucket.items) || bucket.items.length>MAX_PER_DAY) continue;
    for(const item of bucket.items){
      if(!safeHistoryItem(item) || seen.has(item.source_url)) continue;
      seen.add(item.source_url);
      if(params.region!=="all" && item.region!==params.region ||
         params.category!=="all" && item.category!==params.category ||
         params.publisher && item.publisher!==params.publisher ||
         params.q && ![item.title,item.publisher,item.source_preview||""]
           .some(x=>typeof x==="string" && x.toLocaleLowerCase().includes(params.q))) continue;
      all.push(item);
    }
  }
  const order=params.sort==="oldest" ? 1 : -1;
  all.sort((a,b)=>order*(new Date(a.published_at)-new Date(b.published_at)) ||
    a.source_url.localeCompare(b.source_url));
  const publishers=[...new Set(buckets.flatMap(bucket=>
    Array.isArray(bucket?.items)?bucket.items.map(x=>x.publisher).filter(x=>typeof x==="string" && x.length<=100):[]))].sort().slice(0,100);
  // Independent of query filters and pagination; count unique public URLs.
  const unique=new Map();
  const savedDates=[];
  for(const bucket of buckets) {
    if(!bucket || bucket.schema_version!==1 || !params.dates.includes(bucket.date) ||
       !Array.isArray(bucket.items) || bucket.items.length>MAX_PER_DAY) continue;
    if(bucket.items.some(safeHistoryItem)) savedDates.push(bucket.date);
    for(const item of bucket.items) {
      if(safeHistoryItem(item) && !unique.has(item.source_url))
        unique.set(item.source_url,item);
    }
  }
  const archived=[...unique.values()];
  const stats={
    articles:archived.length,
    global:archived.filter(x=>x.region==="global").length,
    india:archived.filter(x=>x.region==="india").length,
    earliest_date:savedDates.length ? [...savedDates].sort()[0] : null,
    latest_date:savedDates.length ? [...savedDates].sort().at(-1) : null
  };
  const offset=params.page*ARCHIVE_PAGE_SIZE;
  return {schema_version:1,archive:true,days:params.days,date:params.date,
    available_days:buckets.filter(x=>Array.isArray(x?.items)&&x.items.length>0).length,
    total:all.length,page:params.page,page_size:ARCHIVE_PAGE_SIZE,
    has_more:offset+ARCHIVE_PAGE_SIZE<all.length,
    publishers,stats,news:all.slice(offset,offset+ARCHIVE_PAGE_SIZE)};
}
