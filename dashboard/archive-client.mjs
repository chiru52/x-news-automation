/** Browser-only read-only archive query construction and response validation. */
export function archiveEndpoint(feedUrl) {
  if(typeof feedUrl!=="string") return "";
  try {
    const u=new URL(feedUrl);
    if(u.protocol!=="https:" || u.pathname!=="/feed" ||
       u.search || u.hash || u.username || u.password ||
       !/^signaldesk-news-feed\.[a-z0-9-]+\.workers\.dev$/.test(u.hostname)) return "";
    u.pathname="/archive";
    return u.href;
  } catch{return "";}
}
export function archiveQuery(endpoint, options) {
  if(!endpoint || typeof options!=="object") return "";
  const url=new URL(endpoint);
  const {days,date,region,publisher,category,q,page}=options;
  if(![7,30].includes(days) ||
     !["all","india","global"].includes(region) ||
     !["all","technology","saas","markets"].includes(category) ||
     !Number.isInteger(page)||page<0||page>59||
     typeof q!=="string"||q.length>100||
     typeof publisher!=="string"||publisher.length>100) return "";
  url.searchParams.set("days",String(days));
  if(date) {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date)) return "";
    url.searchParams.set("date",date);
  }
  if(region!=="all") url.searchParams.set("region",region);
  if(category!=="all") url.searchParams.set("category",category);
  if(publisher) url.searchParams.set("publisher",publisher);
  if(q) url.searchParams.set("q",q);
  if(page>0) url.searchParams.set("page",String(page));
  return url.href;
}
export function archiveResponse(value) {
  return value?.schema_version===1 && value.archive===true &&
    Array.isArray(value.news) && value.news.length<=60 &&
    Array.isArray(value.publishers) && value.publishers.length<=100 &&
    Number.isInteger(value.total) && value.total>=0 && value.total<=3600 &&
    Number.isInteger(value.page) && value.page>=0 && value.page<=59 &&
    typeof value.has_more==="boolean";
}
