/** Deterministic diagnostics from the public feed only.
 * No network, APIs, storage, unpublished data or X publishing.
 */
export function describeIndiaCoverage({items=[],copiedItems=[],fromLive=false,coverage=null,filtered=false}={}){
  const available=items.filter(x=>x?.kind==="news");
  const uniquePublishers=new Set(available.map(x=>x.publisher).filter(x=>typeof x==="string"&&x.trim()));
  const copied=copiedItems.filter(x=>x?.kind==="news").length;
  const count=available.length;
  const summary=count===0
    ?"No currently available India stories in this feed."
    :count+" India "+(count===1?"story":"stories")+" from "+uniquePublishers.size+
      " "+(uniquePublishers.size===1?"publisher":"publishers")+" in the available feed.";
  const source=fromLive?"Latest live collector snapshot.":"Daily fallback snapshot; live collector data was not used.";
  const failures=fromLive&&coverage&&Number.isInteger(coverage.india_sources_failed)&&coverage.india_sources_failed>0
    ?" "+coverage.india_sources_failed+" India-focused "+(coverage.india_sources_failed===1?"feed":"feeds")+" reported unavailable in the latest collection."
    :"";
  const copiedHint=copied?" "+copied+" India "+(copied===1?"article is":"articles are")+" in Copied Articles.":"";
  const filterHint=filtered?" Topic or keyword filters may reduce the visible results.":"";
  return summary+" "+source+failures+copiedHint+filterHint+" For older headlines, use News Archive.";
}
