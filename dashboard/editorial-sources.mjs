/**
 * Public source directory: a transparent list, NOT claims that all outlets
 * are fetched. Every outlet from the owner's two source lists is represented.
 * No external API or news scraping: one local JSON request only.
 */
const STATUS={
  attributed_cc_by_3:"RSS candidate active · attribution required",
  permission_required:"Publisher permission required",
  rights_review:"Reuse terms need review",
  feed_not_confirmed:"Official feed not confirmed",
  no_official_rss:"Official public RSS unavailable",
};
export function renderSourceCatalogue(container, sources) {
  if(!container || !Array.isArray(sources) || sources.length!==19)return false;
  const groups=["global","india"];
  const output=[];
  for(const group of groups) {
    const section=document.createElement("section");
    section.className="source-group";
    const heading=document.createElement("h4");
    heading.textContent=group==="global"?"Global source requests (8)":"India source requests (11)";
    section.append(heading);
    for(const source of sources.filter(s=>s.group===group)) {
      if(typeof source.name!=="string" || typeof source.site!=="string")return false;
      let url;
      try{
        url=new URL(source.site);
        if(url.protocol!=="https:" || url.username || url.password) return false;
      }catch{return false;}
      if(!Object.hasOwn(STATUS,source.status))return false;
      const row=document.createElement("div");
      row.className="source-directory-row";
      const link=document.createElement("a");
      link.textContent=source.name;
      link.href=url.href;
      link.target="_blank";
      link.rel="noopener noreferrer";
      const status=document.createElement("span");
      status.className=source.status==="attributed_cc_by_3"?"source-status-active":"source-status-pending";
      status.textContent=STATUS[source.status];
      row.append(link,status);
      section.append(row);
    }
    output.push(section);
  }
  container.replaceChildren(...output);
  return true;
}
export async function initializeSourceCatalogue(container) {
  if(!container)return;
  try {
    const response=await fetch("./editorial-sources.json",{cache:"force-cache",credentials:"omit"});
    if(!response.ok)throw Error("Catalog missing");
    if(!renderSourceCatalogue(container,await response.json()))throw Error("Invalid catalog");
  }catch{
    container.textContent="The source directory is temporarily unavailable. Existing news remains accessible.";
  }
}
