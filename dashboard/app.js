import {postStarters, researchGuide, draftFromNotes, approximateXCharacters as studioXCharacters} from "./studio.mjs";
import {nextFeedCheckAt, shouldCheckAfterReturn} from "./refresh-clock.mjs";
import {isIndiaArticle, eligibleNews, topNews, newsInSection} from "./news-sections.mjs";
import {archiveEndpoint, archiveQuery, archiveResponse} from "./archive-client.mjs";
const $ = (id) => document.getElementById(id);
const CATEGORIES = {
  technology: {label: "AI & technology", cls: "technology"},
  saas: {label: "Startups & SaaS", cls: "saas"},
  markets: {label: "Markets & finance", cls: "markets"}
};
let records = [], selectedView = "all", selectedCategory = "all", selectedStage = "all", query = "";
let visibleCount = 12;
let historyOpen = false, historyItems = [], historyTotal = 0;
let historyPage = 0, historyHasMore = false, historyRequest = 0;
function archiveMode() {return selectedView === "archive" && historyOpen;}
function trackHistoryItem(item) {
  // Copied archive cards need to appear in the existing personal library.
  // Keep this historical item out of the current live news metrics.
  if(archiveMode() && !records.some(value=>value.id===item.id))
    records.push({...item,history_only:true});
}

function setArchiveVisibility() {
  $("archive-entry").hidden = true; // History is accessed from the dedicated Archive navigation.
  $("archive-controls").hidden = !archiveMode();
  $("archive-toggle").setAttribute("aria-expanded", String(archiveMode()));
}
function exitArchive() {
  historyOpen = false;
  historyRequest++;
  historyItems = [];
  historyTotal = 0;
  historyPage = 0;
  historyHasMore = false;
  setArchiveVisibility();
}
async function loadHistory(page=0) {
  if(!archiveMode()) return;
  const requestId=++historyRequest;
  $("archive-status").textContent="Searching saved public news…";
  $("archive-search").disabled=true;
  const endpoint=archiveEndpoint(liveFeedUrl);
  const options={
    days:Number($("archive-days").value),
    date:$("archive-date").value || null,
    region:$("archive-region").value,
    publisher:$("archive-publisher").value,
    sort:$("archive-sort").value,
    category:selectedCategory,
    q:$("search-input").value.trim().slice(0,100),
    page
  };
  const url=archiveQuery(endpoint,options);
  if(!url) {
    $("archive-search").disabled=false;
    $("archive-status").textContent="History is not available from this news source.";
    return;
  }
  try {
    const response=await fetch(url,{cache:"no-store",credentials:"omit",mode:"cors"});
    if(!response.ok) throw Error("News history HTTP "+response.status);
    const data=await response.json();
    if(!archiveResponse(data)) throw Error("Invalid archive result");
    if(requestId!==historyRequest || !archiveMode()) return;
    historyItems=data.news.map((item,i)=>parseItem(item,"news",i)).filter(Boolean);
    historyTotal=data.total;
    historyPage=data.page;
    historyHasMore=data.has_more;
    const publisherSelect=$("archive-publisher");
    const selected=publisherSelect.value;
    publisherSelect.replaceChildren(new Option("All publishers",""),
      ...data.publishers.map(name=>new Option(name,name)));
    if([...publisherSelect.options].some(option=>option.value===selected))
      publisherSelect.value=selected;
    $("archive-status").textContent= data.available_days===0
      ? "History is building from today. Previous days cannot be backfilled automatically."
      : data.total+" matching articles across "+data.available_days+
        " saved UTC day(s). Public RSS headlines only; verify publishers.";
    $("archive-pagination").hidden=!(data.total>60);
    $("archive-page-label").textContent="Page "+(historyPage+1)+" · "+historyTotal+" matches";
    $("archive-prev").disabled=historyPage===0;
    $("archive-next").disabled=!historyHasMore;
    visibleCount=60;
    render();
  } catch (_) {
    if(requestId!==historyRequest || !archiveMode()) return;
    historyItems=[];historyTotal=0;historyHasMore=false;
    $("archive-pagination").hidden=true;
    $("archive-status").textContent="News history is temporarily unavailable. Latest news remains accessible.";
    render();
  } finally {
    if(requestId===historyRequest) $("archive-search").disabled=false;
  }
}

let loadedSnapshot = "";
let feedCheckInProgress = false;
let lastFeedCheckAt = 0;
// Spread client cache reads across ~45 seconds so multiple visitors do not
// hit the same shared feed endpoint simultaneously.
const feedCheckJitterMs = Math.floor(Math.random() * 45000);
function showBrowserCheckStatus(ok) {
  const label = $("last-checked-display");
  if (!label) return;
  const now = new Intl.DateTimeFormat(undefined, {
    hour:"2-digit", minute:"2-digit"
  }).format(new Date());
  label.textContent = (ok ? "Browser checked " : "Browser check failed ") + now;
}
function isIndiaNews(item) { return isIndiaArticle(item); }
let copyUndo = null;
function showCopyUndo(item, previousStage, fromClipboard = true) {
  copyUndo = {id:item.id, previousStage, returnView:selectedView};
  $("copy-undo-message").textContent = fromClipboard
    ? "Copied to clipboard and moved to Copied Articles. Nothing was posted to X."
    : "Marked as Copied and moved to Copied Articles. Clipboard unchanged; nothing posted to X.";
  $("copy-undo").hidden = false;
}
function hideCopyUndo() {
  copyUndo = null;
  $("copy-undo").hidden = true;
}
function openCopiedLibrary() {
  // A search entered in India must not make the newly copied article vanish
  // again when navigating to the Copied Articles library.
  $("search-input").value = "";
  query = "";
  setView("copied");
}

let liveFeedUrl = null;
let liveConfigChecked = false;
function allowCollectorUrl(value) {
  if (typeof value !== "string" || value.length > 260) return "";
  try {
    const url=new URL(value);
    if (url.protocol!=="https:" || url.username || url.password || url.port ||
        url.pathname!=="/feed" || url.search || url.hash ||
        !/^signaldesk-news-feed\.[a-z0-9-]+\.workers\.dev$/.test(url.hostname))
      return "";
    return url.href;
  } catch (_) { return ""; }
}
async function liveConfig() {
  if (liveConfigChecked) return liveFeedUrl;
  liveConfigChecked=true;
  try {
    const r=await fetch("./feed-config.json",{cache:"no-store"});
    if (!r.ok) return null;
    const config=await r.json();
    if (config.schema_version===1) liveFeedUrl=allowCollectorUrl(config.live_feed_url);
  } catch (_) { /* Daily static feed remains the fallback. */ }
  return liveFeedUrl;
}
async function readFeedData() {
  const r=await fetch("./data.json",{cache:"no-store"});
  if (!r.ok) throw Error("Static feed unavailable");
  const staticData=await r.json();
  const endpoint=await liveConfig();
  if (!endpoint) return {data:staticData,fromLive:false};
  try {
    const latest=await fetch(endpoint,{cache:"no-store",mode:"cors",credentials:"omit"});
    if (!latest.ok) return {data:staticData,fromLive:false};
    const dynamic=await latest.json();
    const dynamicDate=new Date(dynamic.generated_at).getTime();
    const staticDate=new Date(staticData.generated_at).getTime();
    // Only accept a recent, bounded, schema-compatible shared cache snapshot.
    if (dynamic.schema_version!==1 || !Array.isArray(dynamic.news) ||
        dynamic.news.length<5 || dynamic.news.length>40 ||
        !Number.isFinite(dynamicDate) || Date.now()-dynamicDate>90*60*1000 ||
        dynamicDate>Date.now()+10*60*1000 ||
        !(dynamicDate>staticDate)) return {data:staticData,fromLive:false};
    return {data:{
      schema_version:1,generated_at:dynamic.generated_at,
      news:dynamic.news,
      india_news:Array.isArray(dynamic.india_news) && dynamic.india_news.length <= 15 ? dynamic.india_news : [],
      drafts:staticData.drafts,
      warnings:[...(staticData.warnings||[]),...(dynamic.warnings||[])],
    },fromLive:true};
  } catch (_) {
    return {data:staticData,fromLive:false};
  }
}


const STAGES = ["new","reviewing","ready","copied","archived"];
const workflowKey = "signaldesk:workflow:v1";
const workflow = new Map();
try {
  const stored = JSON.parse(localStorage.getItem(workflowKey) || "{}");
  if (stored && typeof stored === "object" && !Array.isArray(stored)) {
    for (const [id, stage] of Object.entries(stored).slice(0,300)) {
      if (id.length <= 140 && STAGES.includes(stage)) workflow.set(id, stage);
    }
  }
} catch (_) { /* Browser storage is optional. */ }
const copiedLibraryKey = "signaldesk:copied-library:v1";
const copiedLibrary = new Map();
try {
  const library = JSON.parse(localStorage.getItem(copiedLibraryKey) || "[]");
  if (Array.isArray(library)) for (const entry of library.slice(-100)) {
    if (!entry || !["news","draft"].includes(entry.kind) ||
        typeof entry.id !== "string" || !/^(news|draft):[a-z0-9]{16,120}$/i.test(entry.id) ||
        typeof entry.title !== "string" || !safeSource(entry.source_url)) continue;
    copiedLibrary.set(entry.id, entry);
  }
} catch (_) { /* Copied history is optional and browser-local. */ }
function rememberCopied(item) {
  copiedLibrary.delete(item.id);
  copiedLibrary.set(item.id, {
    id:item.id, kind:item.kind, title:item.title, description:item.description,
    source_preview:item.source_preview, context_status:item.context_status,
    publisher:item.publisher, source_url:item.source_url, post:item.post,
    category:item.category, region:item.region, published_at:item.published_at,
    status:item.status, trend_score:item.trend_score,
    coverage_feeds:item.coverage_feeds, trend_reason:item.trend_reason
  });
  if (copiedLibrary.size > 100) copiedLibrary.delete(copiedLibrary.keys().next().value);
  try {localStorage.setItem(copiedLibraryKey, JSON.stringify([...copiedLibrary.values()]));}
  catch (_) {showNotice("Copied history could not be saved in this browser.");}
}
function readCopiedLibrary() {
  return [...copiedLibrary.values()].map((entry,i)=>{
    const bareId=entry.id.slice(entry.kind.length+1);
    const parsed=parseItem({...entry,id:bareId},entry.kind,i);
    return parsed && parsed.id === entry.id && workflowStage(parsed)==="copied"
      ? {...parsed,history_only:true} : null;
  }).filter(Boolean);
}
function workflowStage(item) { return workflow.get(item.id) || "new"; }
function setWorkflowStage(item, stage) {
  if (!STAGES.includes(stage)) return;
  if (stage === "new") workflow.delete(item.id);
  else workflow.set(item.id, stage);
  try { localStorage.setItem(workflowKey, JSON.stringify(Object.fromEntries(workflow))); }
  catch (_) { showNotice("Your browser could not save this status; it may reset when you close the page."); }
  updateCounts();
}
function availableNews() {
  // All news = deduplicated Global + India, excluding copied/archived stories.
  return eligibleNews(records, workflowStage, canonicalStoryUrl);
}
function trendingPicks() {
  // Top five editorial signals across BOTH geographies, not social popularity.
  return topNews(availableNews(), 5);
}

const noteKey = "signaldesk:research-notes:v1";
const researchNotes = new Map();
try {
  const raw = JSON.parse(localStorage.getItem(noteKey) || "{}");
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    for (const [id, note] of Object.entries(raw).slice(0,100)) {
      if (id.length <= 140 && typeof note === "string" && note.length <= 1200) researchNotes.set(id, note);
    }
  }
} catch (_) { /* Saved notes are optional and browser-only. */ }
function saveResearchNote(id, note) {
  if (!note.trim()) researchNotes.delete(id);
  else {
    researchNotes.delete(id);
    researchNotes.set(id, note.slice(0,1200));
    if (researchNotes.size > 100) researchNotes.delete(researchNotes.keys().next().value);
  }
  try { localStorage.setItem(noteKey, JSON.stringify(Object.fromEntries(researchNotes))); }
  catch (_) { showNotice("Research notes could not be saved on this device. Copy your notes before leaving."); }
}

const savedKey = "signaldesk:saved:v1";
let saved = new Set();
const editsKey = "signaldesk:edits:v1";
const edits = new Map();
try {
  const raw = JSON.parse(localStorage.getItem(editsKey) || "{}");
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    for (const [id, value] of Object.entries(raw).slice(0, 100)) {
      if (id.length <= 140 && typeof value === "string" && value.length <= 1000) edits.set(id, value);
    }
  }
} catch (_) { /* Browser storage is optional. */ }
function persistEdits() {
  try { localStorage.setItem(editsKey, JSON.stringify(Object.fromEntries(edits))); }
  catch (_) { showNotice("Your browser couldn't save this edit locally. Copy it before leaving the page."); }
}
function rememberEdit(id, content, original) {
  if (content === original) edits.delete(id);
  else {
    edits.delete(id);
    edits.set(id, content);
    if (edits.size > 100) edits.delete(edits.keys().next().value);
  }
  persistEdits();
}

try {
  const parsed = JSON.parse(localStorage.getItem(savedKey) || "[]");
  if (Array.isArray(parsed)) saved = new Set(parsed.filter(x => typeof x === "string").slice(0, 300));
} catch (_) { /* Private browsing: saved items are optional. */ }

function clean(value, max = 1000) { return typeof value === "string" ? value.slice(0, max) : ""; }
function safeSource(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : "";
  } catch (_) { return ""; }
}
// Historical bookmarked headlines stay accessible in Saved for Later on
// this browser even after the rolling 30-day public archive moves on.
const savedHistoryKey="signaldesk:saved-history:v1";
const savedHistory=new Map();
try {
  const entries=JSON.parse(localStorage.getItem(savedHistoryKey)||"[]");
  if(Array.isArray(entries)) for(const entry of entries.slice(-100)) {
    if(entry && /^news:[a-f0-9]{24}$/.test(entry.id) &&
       typeof entry.title==="string" && safeSource(entry.source_url))
      savedHistory.set(entry.id,entry);
  }
} catch (_) { /* Local storage is optional. */ }
function rememberSavedHistory(item) {
  if(archiveMode() && saved.has(item.id)) {
    trackHistoryItem(item);
    savedHistory.delete(item.id);
    savedHistory.set(item.id,{
      id:item.id,title:item.title,description:item.description,
      source_url:item.source_url,publisher:item.publisher,category:item.category,
      region:item.region,post:item.post,source_preview:item.source_preview,
      context_status:item.context_status,status:item.status,
      published_at:item.published_at,trend_score:item.trend_score,
      trend_reason:item.trend_reason,coverage_feeds:item.coverage_feeds
    });
    if(savedHistory.size>100) savedHistory.delete(savedHistory.keys().next().value);
  } else if(!saved.has(item.id)) savedHistory.delete(item.id);
  try {localStorage.setItem(savedHistoryKey,JSON.stringify([...savedHistory.values()]));}
  catch (_) {showNotice("This browser could not save the archived article locally.");}
}
function readSavedHistory() {
  return [...savedHistory.values()].map((entry,i)=>{
    const parsed=parseItem({...entry,id:entry.id.slice(5)},"news",i);
    return parsed && saved.has(parsed.id) ? {...parsed,history_only:true} : null;
  }).filter(Boolean);
}
function approximateXLength(value) {
  // Heuristic only. X generally counts HTTP(S) links as shortened t.co URLs
  // (~23 characters); emoji and premium-account limits can differ.
  return clean(value, 1000).replace(/https?:\/\/[^\s]+/gi, "x".repeat(23)).length;
}
function canonicalStoryUrl(value) {
  const safe = safeSource(value);
  if (!safe) return "";
  try {
    const url = new URL(safe);
    for (const key of [...url.searchParams.keys()]) {
      if (/^utm_/i.test(key) || ["fbclid","gclid","mc_cid","mc_eid"].includes(key.toLowerCase()))
        url.searchParams.delete(key);
    }
    url.hash = "";
    url.pathname = url.pathname.replace(/\/+$/, "") || "/";
    return url.toString();
  } catch (_) { return ""; }
}
function storyTimestamp(item) {
  const d = new Date(item.published_at || item.updated_at);
  return Number.isFinite(d.getTime()) ? d.getTime() : 0;
}
function byFreshness(a,b) {
  return storyTimestamp(b) - storyTimestamp(a) || a.index - b.index;
}
function formatDate(value, {short = false} = {}) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "Date unknown";
  return new Intl.DateTimeFormat(undefined, short
    ? {month: "short", day: "numeric"}
    : {month: "short", day: "numeric", year: "numeric"}).format(d);
}
function showNotice(message) {
  const note = $("alert");
  note.textContent = message;
  note.hidden = !message;
}
function filteredNewsForCurrentView() {
  return newsInSection(availableNews(), selectedView, trendingPicks()).filter(item =>
    (selectedCategory === "all" || item.category === selectedCategory) &&
    (!query || [item.title,item.description,item.publisher,item.post]
      .some(value => clean(value).toLocaleLowerCase().includes(query)))
  );
}
function updateCounts() {
  const news = availableNews();
  const global = news.filter(item => !isIndiaNews(item));
  const india = news.filter(isIndiaNews);
  const trending = trendingPicks();
  const filtered = filteredNewsForCurrentView();
  const geographical = ["all","india","global","trending"].includes(selectedView);
  const matchesFilters = item =>
    (selectedCategory === "all" || item.category === selectedCategory) &&
    (!query || [item.title,item.description,item.publisher,item.post]
      .some(value => clean(value).toLocaleLowerCase().includes(query)));
  const workflowItems = records.filter(item =>
    !item.history_only && (item.kind === "draft" || workflowStage(item) !== "new"));
  const copiedItems = records.filter(item => workflowStage(item) === "copied" && matchesFilters(item));
  const savedItems = records.filter(item =>
    saved.has(item.id) && !["copied","archived"].includes(workflowStage(item)) &&
    matchesFilters(item));
  if (geographical) {
    $("count-news-label").textContent = selectedView === "india" ? "India news stories"
      : selectedView === "global" ? "Global news stories"
      : selectedView === "trending" ? "Trending news stories" : "News stories";
    $("count-trending-label").textContent = selectedView === "india" ? "India trending picks"
      : selectedView === "global" ? "Global trending picks" : "Trending picks";
    $("count-ready-label").textContent = selectedView === "india" ? "India ready to copy"
      : selectedView === "global" ? "Global ready to copy" : "Ready to copy";
    $("count-news").textContent = filtered.length;
    $("count-trending").textContent = selectedView === "trending" ? filtered.length
      : filtered.filter(item => trending.some(pick => pick.id === item.id)).length;
    $("count-ready").textContent = filtered.filter(item => workflowStage(item) === "ready").length;
  } else if (selectedView === "workflow") {
    const scoped = records.filter(item =>
      (selectedStage === "all" ? workflowItems.includes(item) :
       selectedStage === "drafts" ? item.kind === "draft" && !item.history_only :
       workflowStage(item) === selectedStage) && matchesFilters(item));
    $("count-news-label").textContent = "Workflow items";
    $("count-trending-label").textContent = "Prepared drafts";
    $("count-ready-label").textContent = "Ready to copy";
    $("count-news").textContent = scoped.length;
    $("count-trending").textContent = scoped.filter(item => item.kind === "draft").length;
    $("count-ready").textContent = scoped.filter(item => workflowStage(item) === "ready").length;
  } else if (selectedView === "copied") {
    $("count-news-label").textContent = "Copied items";
    $("count-trending-label").textContent = "India copied";
    $("count-ready-label").textContent = "Global copied";
    $("count-news").textContent = copiedItems.length;
    $("count-trending").textContent = copiedItems.filter(isIndiaNews).length;
    $("count-ready").textContent = copiedItems.filter(item =>
      item.kind === "news" && !isIndiaNews(item)).length;
  } else {
    $("count-news-label").textContent = "Saved items";
    $("count-trending-label").textContent = "Saved news";
    $("count-ready-label").textContent = "Saved drafts";
    $("count-news").textContent = savedItems.length;
    $("count-trending").textContent = savedItems.filter(item => item.kind === "news").length;
    $("count-ready").textContent = savedItems.filter(item => item.kind === "draft").length;
  }
  $("nav-all-count").textContent = news.length;
  $("nav-trend-count").textContent = trending.length;
  $("nav-global-count").textContent = global.length;
  $("nav-india-count").textContent = india.length;
  $("nav-workflow-count").textContent = workflowItems.length;
  $("nav-copied-count").textContent = records.filter(item =>
    workflowStage(item) === "copied").length;
  $("nav-saved-count").textContent = records.filter(item =>
    saved.has(item.id) && !["copied","archived"].includes(workflowStage(item))).length;
  if(archiveMode()) {
    $("count-news-label").textContent="Historical matches";
    $("count-trending-label").textContent="On this page";
    $("count-ready-label").textContent="Ready on this page";
    $("count-news").textContent=historyTotal;
    $("count-trending").textContent=historyItems.length;
    $("count-ready").textContent=historyItems.filter(item=>workflowStage(item)==="ready").length;
  }
}
function setView(view) {
  exitArchive();
  selectedView = view;
  if(view === "archive") {
    const now=Date.now();
    $("archive-date").min=new Date(now-29*86400000).toISOString().slice(0,10);
    $("archive-date").max=new Date(now).toISOString().slice(0,10);
    historyOpen=true;
  }
  setArchiveVisibility();
  // Navigation means a fresh section; old searches should not make it
  // unexpectedly appear empty after switching Global ↔ India.
  $("search-input").value = "";
  query = "";
  selectedCategory = "all";
  visibleCount = 12;
  selectedStage = "all";
  $("workflow-filters").hidden = view !== "workflow";
  $("feed-disclaimer").hidden = view !== "trending";
  document.querySelectorAll("[data-stage]").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.stage === "all");
    btn.setAttribute("aria-pressed", String(btn.dataset.stage === "all"));
  });
  document.querySelectorAll("[data-view]").forEach(el => {
    const active = el.dataset.view === view;
    el.classList.toggle("active", active);
    if (active) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-filter]").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.filter === "all");
    btn.setAttribute("aria-pressed", String(btn.dataset.filter === "all"));
  });
  const titles = {
    all: "All stories", trending: "Trending news", global: "Global news",
    india: "India news", copied: "Copied articles",
    workflow: "My Workflow", saved: "Saved for later", archive: "News Archive"
  };
  const descriptions = {
    all: "Global and India news together, including trending stories. Each article appears only once.",
    trending: "Top editorial news signals from both Global and India — not social-media popularity.",
    global: "International news, excluding articles specifically relevant to India.",
    india: "India-related startups, AI, technology and markets, regardless of publisher country.",
    workflow: "Review article stages and find prepared X drafts in one workspace. Saved only in this browser.",
    copied: "Stories marked Copied or copied to your clipboard. This does not mean they were posted on X.",
    saved: "Your bookmarked articles and drafts, stored only in this browser.",
    archive: "Search historical public RSS headlines by date, region, publisher, topic and keyword."
  };
  $("feed-title").textContent = titles[view];
  $("feed-description").textContent = descriptions[view];
  render();
  if(view === "archive") loadHistory(0);
}
function setCategory(category) {
  selectedCategory = category;
  visibleCount = 12;
  document.querySelectorAll("[data-filter]").forEach(btn => {
    const active = btn.dataset.filter === category;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  if(archiveMode()) loadHistory(0);
  else render();
}
function persistSaved() {
  try { localStorage.setItem(savedKey, JSON.stringify(Array.from(saved).slice(0, 300))); }
  catch (_) { /* localStorage may be disabled */ }
  updateCounts();
}
function handleSaved(item, button) {
  if (saved.has(item.id)) saved.delete(item.id);
  else saved.add(item.id);
  rememberSavedHistory(item);
  persistSaved();
  const on = saved.has(item.id);
  button.setAttribute("aria-pressed", String(on));
  button.replaceChildren();
  const heart = document.createElement("span");
  heart.textContent = on ? "♥" : "♡";
  heart.setAttribute("aria-hidden", "true");
  button.append(heart, " ", on ? "Saved" : "Save");
  if (selectedView === "saved") render();
}
async function handleCopy(post, button, onCopied = () => {}) {
  if (!post) return;
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(post);
    onCopied();
    const label = button.querySelector("span");
    label.textContent = "Copied!";
    button.setAttribute("aria-label", "Post copied to clipboard");
    window.setTimeout(() => { if (button.isConnected) {
      label.textContent = "Copy post";
      button.setAttribute("aria-label", "Copy suggested X post");
    } }, 1900);
  } catch (_) {
    showNotice("Your browser blocked clipboard access. Try opening this page over HTTPS and enabling clipboard permission.");
  }
}
function card(item) {
  const node = $("story-card").content.firstElementChild.cloneNode(true);
  const category = CATEGORIES[item.category] || CATEGORIES.technology;
  const pill = node.querySelector(".category-pill");
  pill.textContent = category.label;
  pill.classList.add(category.cls);
  node.querySelector(".card-date").textContent = formatDate(item.published_at || item.updated_at, {short:true});
  node.querySelector(".card-title").textContent = item.title || "Untitled story";
  node.querySelector(".card-description").textContent = item.description ||
    (item.kind === "draft" ? "AI-assisted editorial draft. Check the original reporting before sharing." : "Read the original publisher report for details.");
  const trendingIds = new Set(trendingPicks().map(entry => entry.id));
  if (item.kind === "news" && trendingIds.has(item.id)) {
    node.querySelector(".trend-pill").hidden = false;
    const context = node.querySelector(".trend-reason");
    context.hidden = false;
    context.textContent = "Editorial signal " + item.trend_score + "/100 · " +
      item.trend_reason + " · Not independently verified";
  }
  const src = safeSource(item.source_url);
  const srcLink = node.querySelector(".source-link");
  if (src) {
    srcLink.href = src;
    node.querySelector(".source-publisher").textContent = clean(item.publisher, 100);
  } else {
    node.querySelector(".card-source").hidden = true;
  }
  const suggestion = clean(item.post, 1000).trim();
  const postText = node.querySelector(".draft-text");
  const chars = node.querySelector(".char-count");
  const copy = node.querySelector(".copy-button");
  const editButton = node.querySelector(".edit-button");
  const composer = node.querySelector(".compose-panel");
  const editor = node.querySelector(".compose-input");
  const reset = node.querySelector(".reset-edit");
  const tag = node.querySelector(".review-tag");
  let editing = false;
  const currentDraft = () => edits.has(item.id) ? edits.get(item.id) : suggestion;
  function refreshDraft() {
    const text = currentDraft();
    postText.textContent = text || "No draft available. Use Edit draft to write one.";
    if (!editing) editor.value = text;
    const estimate = approximateXLength(text);
    chars.textContent = "≈" + estimate + "/280 X characters (links shortened) · Verify first";
    chars.classList.toggle("over", estimate > 280);
    copy.disabled = !text.trim();
    tag.textContent = edits.has(item.id) ? "LOCALLY EDITED · VERIFY" : "REVIEW BEFORE SHARING";
    reset.disabled = !edits.has(item.id);
  }
  function showEditor(open) {
    editing = open;
    composer.hidden = !open;
    postText.hidden = open;
    editButton.textContent = open ? "Done editing" : "Edit draft";
    editButton.setAttribute("aria-expanded", String(open));
    if (open) { editor.value = currentDraft(); editor.focus(); }
  }
  editor.addEventListener("input", () => {
    rememberEdit(item.id, editor.value.slice(0, 1000), suggestion);
    refreshDraft();
  });
  reset.addEventListener("click", () => {
    rememberEdit(item.id, suggestion, suggestion);
    editor.value = suggestion;
    refreshDraft();
    editor.focus();
  });
  editButton.addEventListener("click", () => showEditor(!editing));
  copy.addEventListener("click", () => handleCopy(currentDraft().trim(), copy, () => {
    const previousStage = workflowStage(item);
    trackHistoryItem(item);
    setWorkflowStage(item, "copied");
    rememberCopied(item);
    showCopyUndo(item, previousStage);
    stageSelect.value = "copied";
    status.textContent = "Personal: Copied · not posted to X";
    if (selectedView !== "workflow" || selectedStage !== "all") render();
  }));
  refreshDraft();

  // Phase 2: offline source-attributed writing starters and research prompts.
  // These are NOT AI calls; no public browser token or paid backend is used.
  const studioToggle = node.querySelector(".studio-open");
  const researchToggle = node.querySelector(".research-open");
  const studioPanel = node.querySelector(".studio-panel");
  const researchPanel = node.querySelector(".research-panel");
  const toneSelect = node.querySelector(".studio-tone");
  const starterPreview = node.querySelector(".studio-preview");
  const starterLength = node.querySelector(".studio-length");
  const starterButton = node.querySelector(".studio-use");
  const variants = postStarters(item);
  function chooseStarter() {
    const current = variants.find(variant => variant.tone === toneSelect.value);
    const draft = current?.text || "";
    starterPreview.textContent = draft || "No valid source URL available for writing starters.";
    starterLength.textContent = "≈" + studioXCharacters(draft) + "/280 characters";
    starterButton.disabled = !draft;
  }
  chooseStarter();
  toneSelect.addEventListener("change", chooseStarter);
  function closeToolPanels() {
    studioPanel.hidden = true;
    researchPanel.hidden = true;
    studioToggle.setAttribute("aria-expanded", "false");
    researchToggle.setAttribute("aria-expanded", "false");
  }
  studioToggle.addEventListener("click", () => {
    const next = studioPanel.hidden;
    closeToolPanels();
    studioPanel.hidden = !next;
    studioToggle.setAttribute("aria-expanded", String(next));
  });
  starterButton.addEventListener("click", () => {
    const selected = variants.find(variant => variant.tone === toneSelect.value);
    if (!selected?.text) return;
    if (edits.has(item.id) && currentDraft() !== selected.text &&
        !window.confirm("Replace your saved draft with this starter? Your existing local edit will be overwritten.")) return;
    rememberEdit(item.id, selected.text, suggestion);
    refreshDraft();
    closeToolPanels();
    showEditor(true);
    showNotice("Starter loaded into your editor. Check every claim against the original source before copying.");
  });

  const guide = researchGuide(item);
  node.querySelector(".research-headline").textContent = guide.heading;
  node.querySelector(".research-publisher").textContent = "As reported by " + guide.publisher;
  const previewBox = node.querySelector(".rss-context");
  const previewText = node.querySelector(".rss-context-text");
  const previewLabel = node.querySelector(".rss-context-label");
  previewLabel.textContent = guide.preview_label;
  previewText.textContent = guide.preview || "No additional feed details were provided. Open the original source to check the story.";
  previewBox.classList.toggle("preview-missing", !guide.preview);

  const researchLink = node.querySelector(".research-source");
  if (guide.source_url) researchLink.href = guide.source_url;
  else researchLink.hidden = true;
  const questionList = node.querySelector(".research-questions");
  questionList.replaceChildren(...guide.questions.map(question => {
    const li = document.createElement("li");
    li.textContent = question;
    return li;
  }));
  const notes = node.querySelector(".research-notes");
  notes.value = researchNotes.get(item.id) || "";
  const notesToDraft = node.querySelector(".research-apply");
  function updateNotesAction() {
    notesToDraft.disabled = !notes.value.trim() || !guide.source_url;
  }
  updateNotesAction();
  notes.addEventListener("input", () => {
    saveResearchNote(item.id, notes.value);
    updateNotesAction();
  });
  notesToDraft.addEventListener("click", () => {
    const draft = draftFromNotes(notes.value, guide.source_url);
    if (!draft) return;
    if (edits.has(item.id) && currentDraft() !== draft &&
        !window.confirm("Replace your existing local edit with your research notes?")) return;
    rememberEdit(item.id, draft, suggestion);
    refreshDraft();
    closeToolPanels();
    showEditor(true);
    showNotice("Your notes are now in the post editor. Verify every claim before manually posting to X.");
  });
  researchToggle.addEventListener("click", () => {
    const next = researchPanel.hidden;
    closeToolPanels();
    researchPanel.hidden = !next;
    researchToggle.setAttribute("aria-expanded", String(next));
  });
  const status = node.querySelector(".status-info");
  const stageSelect = node.querySelector(".workflow-select");
  stageSelect.value = workflowStage(item);
  function updateStageNote(stage) {
    const messages = {
      new: "Personal: New · source not verified",
      reviewing: "Personal: Reviewing · check original source",
      ready: "Personal: Ready · self-reviewed; not fact-checked by SignalDesk",
      copied: "Personal: Copied · not posted to X",
      archived: "Personal: Archived · hidden from All stories"
    };
    status.textContent = messages[stage];
    status.classList.toggle("reviewed", stage === "ready");
  }
  updateStageNote(stageSelect.value);
  stageSelect.addEventListener("change", () => {
    const stage = stageSelect.value;
    const previousStage = workflowStage(item);
    trackHistoryItem(item);
    setWorkflowStage(item, stage);
    if (stage === "copied") rememberCopied(item);
    else if (copiedLibrary.has(item.id)) {
      copiedLibrary.delete(item.id);
      try {localStorage.setItem(copiedLibraryKey, JSON.stringify([...copiedLibrary.values()]));}
      catch (_) { /* Optional browser storage. */ }
    }
    updateStageNote(stage);
    // Choosing Copied from a dropdown is a status change, NOT a clipboard
    // operation. Navigate to where that article is stored instead of leaving
    // the user on a suddenly empty India / All Stories screen.
    if (stage === "copied" && selectedView !== "copied" && selectedView !== "workflow") {
      showCopyUndo(item, previousStage, false);
      openCopiedLibrary();
      return;
    }
    if (stage === "ready") showNotice("Ready is your personal mark. Check the source and claims before publishing manually.");
    if (selectedView === "workflow" && selectedStage !== "all" ||
        ["all","trending","global","india","saved"].includes(selectedView) &&
          ["copied","archived"].includes(stage) ||
        selectedView === "copied" && stage !== "copied") render();
  });
  const save = node.querySelector(".save-button");
  save.setAttribute("aria-pressed", String(saved.has(item.id)));
  save.querySelector("span").textContent = saved.has(item.id) ? "♥" : "♡";
  save.lastChild.textContent = saved.has(item.id) ? " Saved" : " Save";
  save.addEventListener("click", () => handleSaved(item, save));
  return node;
}
function render() {
  updateCounts();
  if(archiveMode()) {
    $("feed-title").textContent="News Archive";
    $("feed-description").textContent="Browse archived public headlines from the last 7–30 days. Collection started when history was enabled.";
    $("result-count").textContent=historyTotal+" historical matches";
    $("cards").replaceChildren(...historyItems.map(card));
    $("cards").setAttribute("aria-busy","false");
    $("more-container").hidden=true;
    $("empty").hidden=historyItems.length>0;
    $("empty-title").textContent="No archived stories match";
    $("empty-text").textContent="Try a wider period, another region, or clear your keyword and publisher filters. The archive only contains stories collected since activation.";
    $("empty-view-copied").hidden=true;
    $("clear-filters").hidden=true;
    return;
  }
  const trendIds = new Set(trendingPicks().map(item => item.id));
  let list = records.filter(item => {
    // All / Trending / Global / India are news-only. Prepared drafts live
    // under My Workflow > Prepared drafts, never mixed into news headlines.
    if (["all","trending","global","india"].includes(selectedView) && item.kind !== "news") return false;
    if (selectedView === "trending" && !trendIds.has(item.id)) return false;
    if (selectedView === "global" && isIndiaNews(item)) return false;
    if (selectedView === "india" && !isIndiaNews(item)) return false;
    if (selectedView === "copied" && workflowStage(item) !== "copied") return false;
    if (["all","trending","global","india","saved"].includes(selectedView) &&
        ["copied","archived"].includes(workflowStage(item))) return false;
    if (selectedView === "workflow" && selectedStage === "all" &&
        !(item.kind === "draft" || workflowStage(item) !== "new") ||
        selectedView === "workflow" && item.history_only && selectedStage === "all") return false;
    if (selectedView === "workflow" && selectedStage === "drafts" && item.kind !== "draft") return false;
    if (selectedView === "workflow" && selectedStage !== "drafts" &&
        selectedStage !== "all" && workflowStage(item) !== selectedStage) return false;
    if (selectedView === "saved" && !saved.has(item.id)) return false;
    if (selectedCategory !== "all" && item.category !== selectedCategory) return false;
    if (query && ![item.title, item.description, item.publisher, item.post]
      .some(t => clean(t).toLocaleLowerCase().includes(query))) return false;
    return true;
  });
  // Combine regional news without duplicates. Prepared drafts remain
  // available in My Workflow even when a related source URL also has news.
  list.sort(selectedView === "trending"
    ? (a,b) => b.trend_score - a.trend_score || byFreshness(a,b)
    : byFreshness);
  if (["all","trending","global","india"].includes(selectedView)) {
    const used = new Set();
    list = list.filter(item => {
      const url = canonicalStoryUrl(item.source_url) || item.id;
      if (used.has(url)) return false;
      used.add(url);
      return true;
    });
  }
  const noun = ["all","trending","global","india"].includes(selectedView) ? "story" : "item";
  $("result-count").textContent = list.length + " " + noun + (list.length === 1 ? "" : "s");
  const target = $("cards");
  target.replaceChildren(...list.slice(0, visibleCount).map(card));
  target.setAttribute("aria-busy", "false");
  const remaining = Math.max(0, list.length - visibleCount);
  $("more-container").hidden = remaining === 0;
  $("more-counter").textContent = Math.min(list.length, visibleCount) + " of " + list.length + " shown";
  $("load-more").textContent = "Show " + Math.min(12, remaining) + " more";
  $("empty").hidden = list.length > 0;
  const filtersActive = !!query || selectedCategory !== "all" ||
    (selectedView === "workflow" && selectedStage !== "all");
  const copiedIndiaCount = records.filter(item =>
    isIndiaNews(item) && workflowStage(item) === "copied").length;
  $("clear-filters").hidden = !filtersActive;
  $("empty-view-copied").hidden = selectedView !== "india" || copiedIndiaCount === 0;
  $("empty-view-copied").textContent = "View copied articles (" + copiedIndiaCount + ")";
  $("empty-title").textContent = !records.length
    ? "Your workspace is ready"
    : selectedView === "india"
      ? (filtersActive ? "No India stories match these filters" : "No available India stories")
      : "No matching stories";
  $("empty-text").textContent = !records.length
    ? "Build the news dashboard data in GitHub Actions to display collected news and drafts here."
    : selectedView === "india"
      ? (copiedIndiaCount
        ? "Your copied India articles are safe in Copied Articles. New India stories will appear when available."
        : "India-focused reporting appears as the shared collector finds eligible stories. Check again after the next news update.")
      : "Try another topic or search term.";
}
function parseItem(item, kind, index) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const id = clean(item.id, 120);
  if (!id || !["technology", "saas", "markets"].includes(item.category)) return null;
  return {
    id: kind + ":" + id,
    region: kind === "news" && item.region === "india" ? "india" : "global",
    kind,
    title: clean(item.title, 300),
    description: clean(item.description, 500),
    source_preview: kind === "news" ? clean(item.source_preview, 170) : "",
    context_status: kind === "news" ? clean(item.context_status, 30) : "headline_only",
    publisher: clean(item.publisher, 100),
    source_url: clean(item.source_url, 2000),
    post: clean(item.post, 1000),
    category: item.category,
    status: clean(item.status, 24),
    trend_score: kind === "news" && Number.isInteger(item.trend_score) && item.trend_score >= 0 && item.trend_score <= 100 ? item.trend_score : 0,
    coverage_feeds: kind === "news" && Number.isInteger(item.coverage_feeds) ? item.coverage_feeds : 1,
    trend_reason: kind === "news" ? clean(item.trend_reason, 160) : "",
    published_at: clean(item.published_at, 50),
    updated_at: clean(item.updated_at, 50),
    index
  };
}
async function initialize(background = false) {
  if (feedCheckInProgress) return;
  feedCheckInProgress = true;
  lastFeedCheckAt = Date.now();
  try {
    const {data,fromLive} = await readFeedData();
    if (data.schema_version !== 1 || !Array.isArray(data.news) || !Array.isArray(data.drafts) ||
        typeof data.generated_at !== "string" || Number.isNaN(new Date(data.generated_at).getTime()))
      throw new Error("Unsupported feed format");
    showBrowserCheckStatus(true);
    // An unchanged snapshot must not interrupt someone typing an edited post.
    if (background && loadedSnapshot &&
        new Date(data.generated_at).getTime() <= new Date(loadedSnapshot).getTime()) return;
    const updated = [...data.drafts.map((x,i) => parseItem(x,"draft",i)),
                     ...(Array.isArray(data.india_news) ? data.india_news : []).map((x,i) => parseItem(x,"news",i)),
                     ...data.news.map((x,i) => parseItem(x,"news",i))]
      .filter(Boolean).slice(0,300);
    const seen = new Set();
    records = updated.filter(x => {
      if (seen.has(x.id)) return false;
      seen.add(x.id);
      return true;
    });
    for (const copy of readCopiedLibrary()) {
      if (!seen.has(copy.id)) {
        records.push(copy);
        seen.add(copy.id);
      }
    }
    for(const bookmarked of readSavedHistory()) {
      if(!seen.has(bookmarked.id)){
        records.push(bookmarked);
        seen.add(bookmarked.id);
      }
    }
    loadedSnapshot = data.generated_at;
    const date = new Date(data.generated_at);
    $("updated-display").textContent = new Intl.DateTimeFormat(undefined, {
      month:"short", day:"numeric", year:"numeric", hour:"2-digit", minute:"2-digit"
    }).format(date);
    $("sync-indicator").textContent = fromLive
      ? "✓ Shared news cache updated" : "✓ Latest available snapshot";
    $("refresh-note").textContent = fromLive
      ? "News is collected approximately every 15 minutes. This browser checks shortly afterward. Last refreshed is news generation time; Browser checked shows the actual check time."
      : "Showing the latest static snapshot while the shared collector is unavailable or older. Browser checks run after scheduled news collection and when this tab becomes active." ;
    if (data.warnings?.length) showNotice("Feed note: Some sources were unavailable in the latest refresh.");
    updateCounts();
    render();
  } catch (_) {
    showBrowserCheckStatus(false);
    if (!records.length) {
      $("sync-indicator").textContent = "Feed unavailable";
      showNotice("The news feed could not be loaded. Please check the most recent GitHub dashboard build.");
      updateCounts();
      render();
    } else {
      $("sync-indicator").textContent = "Last available snapshot";
      showNotice("The latest feed check failed. Existing news remains available; we'll check again later.");
    }
  } finally {
    feedCheckInProgress = false;
  }
}
document.querySelectorAll("[data-view]").forEach(button =>
  button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-filter]").forEach(button =>
  button.addEventListener("click", () => setCategory(button.dataset.filter)));
document.querySelectorAll("[data-stage]").forEach(button =>
  button.addEventListener("click", () => {
    selectedStage = button.dataset.stage;
    visibleCount = 12;
    document.querySelectorAll("[data-stage]").forEach(other => {
      const active = other.dataset.stage === selectedStage;
      other.classList.toggle("active", active);
      other.setAttribute("aria-pressed", String(active));
    });
    render();
  }));
$("search-input").addEventListener("input", event => {
  query = event.target.value.trim().toLocaleLowerCase().slice(0,100);
  visibleCount = 12;
  if(archiveMode()) {
    $("archive-status").textContent="Press Search history to apply the keyword.";
    return;
  }
  render();
});
$("search-input").addEventListener("keydown", event=>{
  if(event.key==="Enter" && archiveMode()) {event.preventDefault();loadHistory(0);}
});
$("archive-toggle").addEventListener("click",()=>{
  const now=Date.now();
  const today=new Date(now).toISOString().slice(0,10);
  const oldest=new Date(now-29*86400000).toISOString().slice(0,10);
  $("archive-date").min=oldest;
  $("archive-date").max=today;
  historyOpen=true;
  visibleCount=60;
  setArchiveVisibility();
  render();
  loadHistory(0);
});
$("archive-close").addEventListener("click",()=>setView("all"));
$("archive-search").addEventListener("click",()=>loadHistory(0));
$("archive-clear-filters").addEventListener("click",()=>{
  if(!archiveMode()) return;
  $("search-input").value="";
  query="";
  $("archive-days").value="7";
  $("archive-date").value="";
  $("archive-region").value="all";
  $("archive-publisher").value="";
  $("archive-sort").value="newest";
  selectedCategory="all";
  document.querySelectorAll("[data-filter]").forEach(button=>{
    const active=button.dataset.filter==="all";
    button.classList.toggle("active",active);
    button.setAttribute("aria-pressed",String(active));
  });
  loadHistory(0);
});
$("archive-days").addEventListener("change",()=>{
  $("archive-date").value="";
  loadHistory(0);
});
$("archive-date").addEventListener("change",()=>loadHistory(0));
$("archive-region").addEventListener("change",()=>loadHistory(0));
$("archive-publisher").addEventListener("change",()=>loadHistory(0));
$("archive-sort").addEventListener("change",()=>loadHistory(0));
$("archive-prev").addEventListener("click",()=>loadHistory(Math.max(0,historyPage-1)));
$("archive-next").addEventListener("click",()=>{if(historyHasMore)loadHistory(historyPage+1);});
$("clear-filters").addEventListener("click", () => {
  // Clear only the active filters. Never switch India News to All Stories.
  $("search-input").value = "";
  query = "";
  selectedCategory = "all";
  selectedStage = "all";
  visibleCount = 12;
  document.querySelectorAll("[data-filter]").forEach(button => {
    button.classList.toggle("active", button.dataset.filter === "all");
    button.setAttribute("aria-pressed", String(button.dataset.filter === "all"));
  });
  document.querySelectorAll("[data-stage]").forEach(button => {
    button.classList.toggle("active", button.dataset.stage === "all");
    button.setAttribute("aria-pressed", String(button.dataset.stage === "all"));
  });
  render();
});
$("view-copied").addEventListener("click", openCopiedLibrary);
$("empty-view-copied").addEventListener("click", openCopiedLibrary);
$("undo-copy").addEventListener("click", () => {
  if (!copyUndo) return;
  const {id,previousStage,returnView} = copyUndo;
  const item = records.find(value => value.id === id);
  hideCopyUndo();
  if (!item) return;
  setWorkflowStage(item, previousStage);
  copiedLibrary.delete(item.id);
  try { localStorage.setItem(copiedLibraryKey, JSON.stringify([...copiedLibrary.values()])); }
  catch (_) { /* Workflow status remains the source of truth. */ }
  if (returnView && returnView !== selectedView) {
    // Restore the original workspace after Undo, including India News.
    setView(returnView);
  } else render();
});
$("load-more").addEventListener("click", () => {
  visibleCount += 12;
  render();
});
initialize();
// The collector runs at :00, :15, :30 and :45 (UTC). Check a little later
// rather than blindly 15 minutes after the visitor first opened the page.
// Only GET public cached JSON; never invoke RSS collection per visitor.
function scheduleFeedCheck() {
  const delay = Math.max(1000, nextFeedCheckAt(Date.now(), feedCheckJitterMs) - Date.now());
  window.setTimeout(() => {
    if (document.visibilityState === "visible") initialize(true);
    scheduleFeedCheck();
  }, delay);
}
scheduleFeedCheck();
// Background tabs can have their timers throttled. Check on return when the
// last check was at least two minutes ago; rapid tab switching is throttled.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" &&
      shouldCheckAfterReturn(Date.now(), lastFeedCheckAt)) initialize(true);
});

