import {postStarters, researchGuide, draftFromNotes, approximateXCharacters as studioXCharacters} from "./studio.mjs";
import {nextFeedCheckAt, shouldCheckAfterReturn} from "./refresh-clock.mjs";
const $ = (id) => document.getElementById(id);
const CATEGORIES = {
  technology: {label: "AI & technology", cls: "technology"},
  saas: {label: "Startups & SaaS", cls: "saas"},
  markets: {label: "Markets & finance", cls: "markets"}
};
let records = [], selectedView = "all", selectedCategory = "all", selectedStage = "all", query = "";
let visibleCount = 12;
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
const INDIA_TERMS = /\b(?:india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|gurugram|noida|rbi|sebi|nifty|sensex|nse|bse|rupee|rupees|lakh|crore|isro|aadhaar|upi)\b/i;
const INDIA_FOCUSED_PUBLISHERS = new Set(["Inc42 India Startups","ET Entrepreneur India Startups"]);
function isIndiaNews(item) {
  return item.kind === "news" && (item.region === "india" ||
    INDIA_FOCUSED_PUBLISHERS.has(item.publisher) || INDIA_TERMS.test(item.title));
}
let copyUndo = null;
function showCopyUndo(item, previousStage) {
  copyUndo = {id:item.id, previousStage};
  $("copy-undo-message").textContent = "Copied to clipboard. Moved out of your main feed — not posted to X.";
  $("copy-undo").hidden = false;
}
function hideCopyUndo() {
  copyUndo = null;
  $("copy-undo").hidden = true;
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
function trendingPicks() {
  return records.filter(item => item.kind === "news" && !item.history_only)
    .sort((a,b) => b.trend_score - a.trend_score || byFreshness(a,b))
    .slice(0,5);
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
function indiaNewsForCurrentView() {
  // KPI numbers in India News must match its visible, uncopied article list,
  // including active topic and search filters. Exclude local copied history.
  return records.filter(item =>
    isIndiaNews(item) && !item.history_only &&
    !["copied","archived"].includes(workflowStage(item)) &&
    (selectedCategory === "all" || item.category === selectedCategory) &&
    (!query || [item.title,item.description,item.publisher,item.post]
      .some(value => clean(value).toLocaleLowerCase().includes(query)))
  );
}
function updateCounts() {
  const news = records.filter(r => r.kind === "news" && !r.history_only).length;
  const drafts = records.filter(r => r.kind === "draft" && !r.history_only).length;
  const indiaView = selectedView === "india";
  const indiaNews = indiaView ? indiaNewsForCurrentView() : [];
  $("count-news-label").textContent = indiaView ? "India news stories" : "News stories";
  $("count-trending-label").textContent = indiaView ? "India trending picks" : "Trending picks";
  $("count-ready-label").textContent = indiaView ? "India ready to copy" : "Ready to copy";
  $("count-news").textContent = indiaView ? indiaNews.length : news;
  $("count-trending").textContent = Math.min(5,indiaView ? indiaNews.length : news);
  $("count-ready").textContent = indiaView
    ? indiaNews.filter(item => workflowStage(item) === "ready").length
    : records.filter(r => workflowStage(r) === "ready").length;
  $("nav-all-count").textContent = records.filter(r => !r.history_only && !["copied","archived"].includes(workflowStage(r))).length;
  $("nav-trend-count").textContent = Math.min(5, news);
  $("nav-workflow-count").textContent = records.filter(r => workflowStage(r) !== "new").length;
  $("nav-copied-count").textContent = records.filter(r => workflowStage(r) === "copied").length;
  $("nav-india-count").textContent = records.filter(r => isIndiaNews(r) && !["copied","archived"].includes(workflowStage(r))).length;
  $("nav-draft-count").textContent = drafts;
  $("nav-saved-count").textContent = saved.size;
}
function setView(view) {
  selectedView = view;
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
  const titles = {all: "Explore the latest", trending: "Trending news", india: "India news", copied: "Copied articles", drafts: "Your X draft library", workflow: "Your content workflow", saved: "Saved for later"};
  const descriptions = {
    all: "Fresh stories and prepared drafts, all in one place.",
    trending: "The strongest headline signals from the current news feed, not social popularity.",
    workflow: "Organize your own reading and copying stages, stored only in this browser.",
    drafts: "Suggestions to verify, edit and copy when you choose.",
    saved: "Your bookmarked stories, stored only in this browser.",
    india: "Indian startups, AI, technology and markets — from India-focused reporting and relevant headlines.",
    copied: "Stories you copied to the clipboard. This does not mean they were posted on X."
  };
  $("feed-title").textContent = titles[view];
  $("feed-description").textContent = descriptions[view];
  render();
}
function setCategory(category) {
  selectedCategory = category;
  visibleCount = 12;
  document.querySelectorAll("[data-filter]").forEach(btn => {
    const active = btn.dataset.filter === category;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  render();
}
function persistSaved() {
  try { localStorage.setItem(savedKey, JSON.stringify(Array.from(saved).slice(0, 300))); }
  catch (_) { /* localStorage may be disabled */ }
  updateCounts();
}
function handleSaved(item, button) {
  if (saved.has(item.id)) saved.delete(item.id);
  else saved.add(item.id);
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
    setWorkflowStage(item, stage);
    if (stage === "copied") rememberCopied(item);
    else if (copiedLibrary.has(item.id)) {
      copiedLibrary.delete(item.id);
      try {localStorage.setItem(copiedLibraryKey, JSON.stringify([...copiedLibrary.values()]));}
      catch (_) { /* Optional browser storage. */ }
    }
    updateStageNote(stage);
    if (stage === "ready") showNotice("Ready is your personal mark. Check the source and claims before publishing manually.");
    if (selectedView === "workflow" && selectedStage !== "all" ||
        ["all","trending","india","drafts","saved"].includes(selectedView) && ["copied","archived"].includes(stage) ||
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
  const trendIds = new Set(trendingPicks().map(item => item.id));
  let list = records.filter(item => {
    if (selectedView === "trending" && !trendIds.has(item.id)) return false;
    if (selectedView === "india" && !isIndiaNews(item)) return false;
    if (selectedView === "copied" && workflowStage(item) !== "copied") return false;
    if (["all","trending","india","drafts","saved"].includes(selectedView) &&
        ["copied","archived"].includes(workflowStage(item))) return false;
    if (selectedView === "workflow" && selectedStage !== "all" && workflowStage(item) !== selectedStage) return false;
    if (selectedView === "all" && workflowStage(item) === "archived") return false;
    if (selectedView === "drafts" && item.kind !== "draft") return false;
    if (selectedView === "saved" && !saved.has(item.id)) return false;
    if (selectedCategory !== "all" && item.category !== selectedCategory) return false;
    if (query && ![item.title, item.description, item.publisher, item.post]
      .some(t => clean(t).toLocaleLowerCase().includes(query))) return false;
    return true;
  });
  // New stories should be visible first; AI drafts remain in their own tab.
  // Remove only repeated publisher URLs in All, retaining the newest item.
  list.sort(selectedView === "trending"
    ? (a,b) => b.trend_score - a.trend_score || byFreshness(a,b)
    : byFreshness);
  if (selectedView === "all") {
    const used = new Set();
    list = list.filter(item => {
      const url = canonicalStoryUrl(item.source_url);
      if (!url || used.has(url)) return !url;
      used.add(url);
      return true;
    });
  }
  $("result-count").textContent = list.length + (list.length === 1 ? " story" : " stories");
  const target = $("cards");
  target.replaceChildren(...list.slice(0, visibleCount).map(card));
  target.setAttribute("aria-busy", "false");
  const remaining = Math.max(0, list.length - visibleCount);
  $("more-container").hidden = remaining === 0;
  $("more-counter").textContent = Math.min(list.length, visibleCount) + " of " + list.length + " shown";
  $("load-more").textContent = "Show " + Math.min(12, remaining) + " more";
  $("empty").hidden = list.length > 0;
  $("empty-title").textContent = !records.length ? "Your workspace is ready" : selectedView === "india" ? "No India stories in this snapshot" : "No matching stories";
  $("empty-text").textContent = !records.length
    ? "Build the news dashboard data in GitHub Actions to display collected news and drafts here."
    : selectedView === "india" ? "India-focused reporting appears as the shared collector finds eligible stories. Check again after the next news update." : "Try another topic or search term.";
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
document.querySelectorAll("[data-category]").forEach(button =>
  button.addEventListener("click", () => { setView("all"); setCategory(button.dataset.category); }));
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
  render();
});
$("clear-filters").addEventListener("click", () => {
  $("search-input").value = "";
  query = "";
  setView("all");
});
$("undo-copy").addEventListener("click", () => {
  if (!copyUndo) return;
  const {id,previousStage} = copyUndo;
  const item = records.find(value => value.id === id);
  hideCopyUndo();
  if (!item) return;
  setWorkflowStage(item, previousStage);
  copiedLibrary.delete(item.id);
  try { localStorage.setItem(copiedLibraryKey, JSON.stringify([...copiedLibrary.values()])); }
  catch (_) { /* Workflow status remains the source of truth. */ }
  render();
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

