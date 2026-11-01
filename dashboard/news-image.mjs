/** Article-specific publisher RSS/Atom image metadata, never article-page scraping.
 * Shared by the read-only news Worker and dashboard; no external image APIs.
 */
const NON_ARTICLE_ARTWORK=/(?:^|[/_.-])(?:avatar|logo|favicon|icon|sprite|tracking|tracker|pixel|spacer|placeholder|blank|transparent|advert|banner-ad|profile-photo)(?:[/_.-]|$)|(?:[?&](?:width|w|size)=)(?:[1-9]|[1-9][0-9])(?:[&#]|$)/i;
export function safeNewsImage(value) {
  if(typeof value!=="string" || value.length>1400 ||
     /[\s\\<>"'\x00-\x1f\x7f]/.test(value) ||
     /%(?:0[0-9a-f]|1[0-9a-f]|7f)/i.test(value) ||
     !/^[\x21-\x7e]+$/.test(value)) return "";
  try {
    const url=new URL(value);
    if(url.protocol!=="https:" || url.username || url.password || url.port ||
       !url.hostname || url.hostname.length>250 ||
       url.hostname==="localhost" || url.hostname.endsWith(".localhost") ||
       /^\d+(?:\.\d+){3}$/.test(url.hostname) || url.hostname.includes(":") ||
       /(?:^|\.)(?:local|internal|test)$/.test(url.hostname) ||
       /\.(?:svgz?|gif|ico|html?|js|xml|pdf)$/i.test(url.pathname) ||
       NON_ARTICLE_ARTWORK.test(url.pathname+url.search))return "";
    return url.href;
  }catch{return "";}
}
const asArray=value=>Array.isArray(value)?value:value?[value]:[];
const imageType=entry=>/^(?:image\/(?:jpeg|png|webp|avif))(?:;|$)/i.test(String(entry?.["@_type"]||""));
function plausibleSize(entry) {
  const width=Number(entry?.["@_width"]),height=Number(entry?.["@_height"]);
  return !(Number.isFinite(width)&&width>0&&width<160) &&
         !(Number.isFinite(height)&&height>0&&height<90);
}
function imageCandidate(entry,forced=false) {
  if(!entry||typeof entry!=="object"||!plausibleSize(entry))return "";
  const value=safeNewsImage(entry["@_url"]||entry["@_href"]);
  if(!value)return "";
  const imagePath=/\.(?:jpe?g|png|webp|avif)$/i.test(new URL(value).pathname);
  return forced||imageType(entry)||entry["@_medium"]==="image"||imagePath?value:"";
}
function decodeImageAttribute(value){
  return String(value||"").replace(/&amp;/gi,"&").replace(/&quot;/gi,'"')
    .replace(/&#39;|&apos;/gi,"'").replace(/&#(x[0-9a-f]+|\d+);/gi,(_,number)=>{
      const code=number[0].toLowerCase()==="x"?parseInt(number.slice(1),16):Number(number);
      return code>0&&code<=0x10ffff?String.fromCodePoint(code):"";
    });
}
function srcsetImage(srcset) {
  for(const candidate of String(srcset||"").split(",").slice(0,12).reverse()){
    const parts=candidate.trim().split(/\s+/);
    if(parts.length<2)continue;
    const scale=parts[parts.length-1];
    if(!(/^\d+w$/i.test(scale)&&Number(scale.slice(0,-1))>=300 ||
         /^[1-9](?:\.\d+)?x$/i.test(scale)&&Number(scale.slice(0,-1))>=1.5))continue;
    const url=safeNewsImage(decodeImageAttribute(parts[0]));
    if(url)return url;
  }
  return "";
}
function itemText(value){
  if(typeof value==="string")return value;
  return typeof value?.["#text"]==="string"?value["#text"]:"";
}
/** Extract only the first plausible image in an RSS item's embedded HTML. */
export function imageFromEmbeddedHtml(html){
  if(typeof html!=="string"||html.length>100000)return "";
  const tags=html.match(/<(?:img|source)\b[^>]{0,3000}>/gi)||[];
  for(const tag of tags.slice(0,12)){
    const attrs={};
    for(const match of tag.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)){
      attrs[match[1].toLowerCase()]=decodeImageAttribute(match[2]??match[3]??match[4]);
    }
    const type=String(attrs.type||"").toLowerCase();
    if(/^<source\b/i.test(tag)&&type&&!/^(?:image\/(?:jpeg|png|webp|avif))$/.test(type))continue;
    const width=Number(String(attrs.width||"0").replace(/px$/i,""));
    const height=Number(String(attrs.height||"0").replace(/px$/i,""));
    if(width>0&&width<160||height>0&&height<90)continue;
    for(const candidate of [attrs["data-src"],attrs["data-original"],attrs["data-lazy-src"],
      srcsetImage(attrs.srcset),attrs.src]){
      const url=safeNewsImage(candidate);
      if(url)return url;
    }
  }
  return "";
}
export function imageFromRssEntry(entry) {
  if(!entry||typeof entry!=="object")return "";
  // Prefer structured item-level media, including media:group, before inline HTML.
  const parents=[entry,...asArray(entry.group).filter(x=>x&&typeof x==="object")];
  for(const parent of parents){
    for(const candidate of asArray(parent.thumbnail)){
      const image=imageCandidate(candidate,true);
      if(image)return image;
    }
    for(const candidate of asArray(parent.content)){
      const image=imageCandidate(candidate);
      if(image)return image;
    }
  }
  for(const candidate of asArray(entry.enclosure)){
    if(!imageType(candidate))continue;
    const image=imageCandidate(candidate);
    if(image)return image;
  }
  for(const candidate of asArray(entry.link)){
    if(candidate?.["@_rel"]!=="enclosure"||!imageType(candidate))continue;
    const image=imageCandidate(candidate);
    if(image)return image;
  }
  for(const content of [entry.description,entry.encoded,entry.summary,entry.content]){
    const image=imageFromEmbeddedHtml(itemText(content));
    if(image)return image;
  }
  return "";
}
