/** Pure, browser-local editorial review helpers. Never publish or fetch news.
 * Reviews organize existing drafts only and do not independently verify facts.
 */
import {approximateXCharacters,safeArticleUrl} from "./studio.mjs";
const WORKING=new Set(["new","reviewing","ready"]);
export function reviewCandidates(items,stageOf,edits,threadEdits){
  if(!Array.isArray(items))return [];
  const seen=new Set();
  return items.filter(item=>{
    if(!item||typeof item.id!=="string"||seen.has(item.id)||item.history_only||
       !["news","draft"].includes(item.kind)||!safeArticleUrl(item.source_url))return false;
    const stage=stageOf(item);
    if(!WORKING.has(stage))return false;
    if(item.kind!=="draft"&&stage==="new"&&!edits.has(item.id)&&!threadEdits.has(item.id))
      return false;
    seen.add(item.id);
    return true;
  }).sort((a,b)=>{
    const rank=item=>stageOf(item)==="ready"?0:stageOf(item)==="reviewing"?1:2;
    const date=item=>new Date(item.published_at||item.updated_at||0).getTime()||0;
    return rank(a)-rank(b)||date(b)-date(a);
  });
}
export function reviewPost(text,sourceUrl){
  const safe=safeArticleUrl(sourceUrl);
  if(!safe)return {valid:false,message:"The original source link is unavailable."};
  if(typeof text!=="string"||!text.trim())
    return {valid:false,message:"Write a draft before marking it ready."};
  if(text.length>1000||approximateXCharacters(text)>280)
    return {valid:false,message:"Shorten this draft to approximately 280 X characters."};
  if(!text.includes(safe))
    return {valid:false,message:"Include the original source link in your draft."};
  return {valid:true,message:"Length and source link checked. Verify the claims yourself."};
}
export function reviewCounts(items,stageOf) {
  return {total:items.length,
    reviewing:items.filter(item=>stageOf(item)==="reviewing").length,
    ready:items.filter(item=>stageOf(item)==="ready").length};
}
