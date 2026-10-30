const $ = (id) => document.getElementById(id);
const CATEGORIES = {
  technology: {label: "AI & technology", cls: "technology"},
  saas: {label: "Startups & SaaS", cls: "saas"},
  markets: {label: "Markets & finance", cls: "markets"}
};
let records = [], selectedView = "all", selectedCategory = "all", query = "";
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
function updateCounts() {
  const news = records.filter(r => r.kind === "news").length;
  const drafts = records.filter(r => r.kind === "draft").length;
  $("count-news").textContent = news;
  $("count-drafts").textContent = drafts;
  $("count-reviewed").textContent = records.filter(r => r.kind === "draft" && r.status === "reviewed").length;
  $("nav-all-count").textContent = records.length;
  $("nav-draft-count").textContent = drafts;
  $("nav-saved-count").textContent = saved.size;
}
function setView(view) {
  selectedView = view;
  selectedCategory = "all";
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
  const titles = {all: "Explore the latest", drafts: "Your X draft library", saved: "Saved for later"};
  const descriptions = {
    all: "Fresh stories and prepared drafts, all in one place.",
    drafts: "Suggestions to verify, edit and copy when you choose.",
    saved: "Your bookmarked stories, stored only in this browser."
  };
  $("feed-title").textContent = titles[view];
  $("feed-description").textContent = descriptions[view];
  render();
}
function setCategory(category) {
  selectedCategory = category;
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
async function handleCopy(post, button) {
  if (!post) return;
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(post);
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
    chars.textContent = text.length + " characters" +
      (text.length > 280 ? " · Over 280; X may shorten URLs" : " · Verify before sharing");
    chars.classList.toggle("over", text.length > 280);
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
  copy.addEventListener("click", () => handleCopy(currentDraft().trim(), copy));
  refreshDraft();
  const status = node.querySelector(".status-info");
  if (item.kind === "draft") {
    status.textContent = item.status === "reviewed" ? "Editorial review completed" : "Not fact-checked";
    if (item.status === "reviewed") status.classList.add("reviewed");
  } else status.textContent = "News suggestion · Unverified";
  const save = node.querySelector(".save-button");
  save.setAttribute("aria-pressed", String(saved.has(item.id)));
  save.querySelector("span").textContent = saved.has(item.id) ? "♥" : "♡";
  save.lastChild.textContent = saved.has(item.id) ? " Saved" : " Save";
  save.addEventListener("click", () => handleSaved(item, save));
  return node;
}
function render() {
  const list = records.filter(item => {
    if (selectedView === "drafts" && item.kind !== "draft") return false;
    if (selectedView === "saved" && !saved.has(item.id)) return false;
    if (selectedCategory !== "all" && item.category !== selectedCategory) return false;
    if (query && ![item.title, item.description, item.publisher, item.post]
      .some(t => clean(t).toLocaleLowerCase().includes(query))) return false;
    return true;
  });
  $("result-count").textContent = list.length + (list.length === 1 ? " story" : " stories");
  const target = $("cards");
  target.replaceChildren(...list.map(card));
  target.setAttribute("aria-busy", "false");
  $("empty").hidden = list.length > 0;
  $("empty-title").textContent = !records.length ? "Your workspace is ready" : "No matching stories";
  $("empty-text").textContent = !records.length
    ? "Build the news dashboard data in GitHub Actions to display collected news and drafts here."
    : "Try another topic or search term.";
}
function parseItem(item, kind, index) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const id = clean(item.id, 120);
  if (!id || !["technology", "saas", "markets"].includes(item.category)) return null;
  return {
    id: kind + ":" + id,
    kind,
    title: clean(item.title, 300),
    description: clean(item.description, 500),
    publisher: clean(item.publisher, 100),
    source_url: clean(item.source_url, 2000),
    post: clean(item.post, 1000),
    category: item.category,
    status: clean(item.status, 24),
    published_at: clean(item.published_at, 50),
    updated_at: clean(item.updated_at, 50),
    index
  };
}
async function initialize() {
  try {
    const response = await fetch("./data.json", {cache: "no-store"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    if (data.schema_version !== 1 || !Array.isArray(data.news) || !Array.isArray(data.drafts))
      throw new Error("Unsupported feed format");
    records = [...data.drafts.map((x,i) => parseItem(x,"draft",i)),
               ...data.news.map((x,i) => parseItem(x,"news",i))]
      .filter(Boolean).slice(0,300);
    const unique = new Set();
    records = records.filter(x => {
      if (unique.has(x.id)) return false;
      unique.add(x.id);
      return true;
    });
    $("updated-display").textContent = formatDate(data.generated_at);
    $("sync-indicator").textContent = "✓ Latest available snapshot";
    if (data.warnings?.length) showNotice("Feed note: Some sources were unavailable in the latest refresh.");
    updateCounts();
    render();
  } catch (_) {
    $("sync-indicator").textContent = "Feed unavailable";
    showNotice("The news feed could not be loaded. Please check the most recent GitHub dashboard build.");
    updateCounts();
    render();
  }
}
document.querySelectorAll("[data-view]").forEach(button =>
  button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-category]").forEach(button =>
  button.addEventListener("click", () => { setView("all"); setCategory(button.dataset.category); }));
document.querySelectorAll("[data-filter]").forEach(button =>
  button.addEventListener("click", () => setCategory(button.dataset.filter)));
$("search-input").addEventListener("input", event => {
  query = event.target.value.trim().toLocaleLowerCase().slice(0,100);
  render();
});
$("clear-filters").addEventListener("click", () => {
  $("search-input").value = "";
  query = "";
  setView("all");
});
initialize();
