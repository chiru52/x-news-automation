/** Conservative, deterministic RSS news intelligence.
 * A matching headline is NOT verification of a claim or social-media popularity.
 * Compare titles and numeric facts, then count separate publisher groups.
 */
const WORDS=/[a-z0-9]+(?:[.][0-9]+)?/gi;
const IGNORED=new Set(["the","a","an","and","or","but","of","in","on","for","to","with","at","by","from","as","after","before","new","latest","says","report","reports","news","update","updates"]);
const CONCRETE=/\b(?:launch(?:es|ed)?|releas(?:es|ed)?|unveil(?:s|ed)?|acquir(?:es|ed)?|funding|rais(?:es|ed)?|earnings|revenue|regulat(?:ion|or)|security|vulnerability|merger|ipo|investment|ban)\b/i;
const SPECULATIVE=/\b(?:will|could|might|may|should|rumou?r|predict(?:s|ion)?|forecast)\b|\?$/i;
function tokens(title) {
  return String(title||"").toLowerCase().match(WORDS)?.filter(w=>!IGNORED.has(w))||[];
}
export function canonicalArticleUrl(value){
  try {
    const u=new URL(value);
    if(u.protocol!=="https:"||u.username||u.password)return "";
    for(const key of [...u.searchParams.keys()]){
      if(/^utm_/i.test(key)||["fbclid","gclid","mc_cid","mc_eid"].includes(key.toLowerCase()))
        u.searchParams.delete(key);
    }
    u.hash="";
    u.pathname=u.pathname.replace(/\/+$/,"")||"/";
    return u.href;
  }catch{return "";}
}
export function sameNewsEvent(a,b) {
  const ua=canonicalArticleUrl(a?.source_url),ub=canonicalArticleUrl(b?.source_url);
  if(ua&&ub&&ua===ub)return true;
  const ta=tokens(a?.title),tb=tokens(b?.title);
  const sa=new Set(ta),sb=new Set(tb);
  if(sa.size<6||sb.size<6)return false;
  // Preserve numeric order and repetition: 10/20 is not 20/10.
  const nums=t=>t.filter(x=>/\d/.test(x)).join("|");
  if(nums(ta)!==nums(tb))return false;
  // Protect separate companies and later updates that share generic wording.
  if(ta.slice(0,2).join("|")!==tb.slice(0,2).join("|"))return false;
  const shared=[...sa].filter(x=>sb.has(x)).length;
  return shared>=6 && shared/(sa.size+sb.size-shared)>=.84;
}
function publisherGroup(article) {
  const publisher=String(article?.publisher||"").toLowerCase();
  if(publisher.startsWith("cnbc"))return "cnbc";
  if(publisher.startsWith("bbc"))return "bbc";
  if(publisher.startsWith("yahoo finance"))return "yahoo";
  if(publisher.startsWith("et ") || publisher.startsWith("economic times"))return "economic-times";
  if(publisher.startsWith("product hunt"))return "product-hunt";
  // Prefer explicit feed identity when known; never guess distinct publishers
  // from multiple feeds belonging to the same media organization.
  const url=String(article?.feed_url||article?.source_url||"");
  try {
    const host=new URL(url).hostname.toLowerCase().replace(/^www\./,"");
    return host;
  }catch{return publisher||"unknown";}
}
const clamp=(v,min,max)=>Math.min(max,Math.max(min,v));
export function editorialSignals(article,allArticles,nowMs=Date.now()){
  const ageHours=Math.max(0,(nowMs-new Date(article.published_at).getTime())/3600000);
  const groups=new Set([publisherGroup(article)]);
  for(const other of allArticles) {
    const ts=new Date(other.published_at).getTime();
    if(!Number.isFinite(ts)||ts<nowMs-36*3600000||ts>nowMs+10*60000)continue;
    if(sameNewsEvent(article,other))groups.add(publisherGroup(other));
    if(groups.size>=20)break;
  }
  const count=groups.size;
  const concrete=CONCRETE.test(article.title);
  const speculative=SPECULATIVE.test(article.title);
  const score=clamp(Math.round(65-ageHours*1.25+(concrete?11:0)-
    (speculative?14:0)+Math.min(count-1,3)*9),0,100);
  const reason=count>1
    ? "Similar headlines from "+count+" publisher groups (not independently verified)"
    : concrete
      ? "Recent headline about a reported development"
      : "Headline relevance and freshness; no social trend data";
  return {score,coverage_feeds:count,reason};
}
export function removeRepeatedNews(items) {
  const unique=[];
  for(const item of items){
    if(!unique.some(previous=>sameNewsEvent(previous,item)))unique.push(item);
  }
  return unique;
}
