/**
 * SignalDesk reference-style news explorer.
 * One set of real news records, two projections: moving layered stack and
 * dense gallery. The detailed editor is supplied by the existing card()
 * function, so original tools, workflow state, safety and local edits remain.
 * No new endpoints, image assets, third-party packages or X publishing.
 */
import {safeNewsImage} from "./news-image.mjs";
export function relativePosition(index, active, length) {
  if (!Number.isInteger(index) || !Number.isInteger(active) || length < 1) return 99;
  let distance = (index - active + length) % length;
  if (distance > length / 2) distance -= length;
  return distance;
}
export function appearanceFor(category) {
  return ["technology", "markets", "saas", "world", "policy", "factcheck"].includes(category) ? category : "technology";
}
const COVER_LABELS=Object.freeze({technology:"TECHNOLOGY",markets:"MARKETS",saas:"BUSINESS",world:"WORLD",policy:"POLICY",factcheck:"FACT CHECK"});
export function canUseExplorer(view) {
  return ["all", "global", "india", "trending"].includes(view);
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function validPublisherLink(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password
      ? parsed.href : "";
  } catch { return ""; }
}
export function createNewsExplorer(root, { buildFullCard, dateLabel, onModeChange } = {}) {
  if (!root || typeof buildFullCard !== "function") throw Error("Explorer needs a card renderer");
  const canvas = root.querySelector(".explorer-canvas");
  const detail = root.querySelector(".explorer-detail");
  const editorial = root.querySelector(".explorer-editor");
  const summary = root.querySelector(".explorer-summary");
  const title = root.querySelector(".explorer-selected-title");
  const publisher = root.querySelector(".explorer-selected-publisher");
  const description = root.querySelector(".explorer-selected-description");
  const source = root.querySelector(".explorer-source");
  const count = root.querySelector(".explorer-count");
  const selectedCount = root.querySelector(".explorer-selected-count");
  const tools = root.querySelector(".explorer-tools");
  const reveal = root.querySelector(".explorer-show-tools");
  const close = root.querySelector(".explorer-close");
  const shade = root.querySelector(".explorer-shade");
  const prev = root.querySelector(".explorer-prev");
  const next = root.querySelector(".explorer-next");
  const modes = [...root.querySelectorAll("[data-explorer-mode]")];
  let mode = "layered", current = [], selectedId = null, drawerOpen = false, paused = false;
  let touchStart = null;
  const nodes = new Map();
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  const activeIndex = () => Math.max(0, current.findIndex(item => item.id === selectedId));

  function buildTile(item, index) {
    const tile = element("button", "explorer-tile");
    tile.type = "button";
    tile.dataset.itemId = item.id;
    tile.dataset.category = appearanceFor(item.category);
    tile.setAttribute("aria-label", "Explore story " + (index + 1) + ": " + item.title);
    const artwork = element("span", "explorer-artwork");
    artwork.setAttribute("aria-hidden", "true");
    // When the publisher RSS feed includes an article-specific image, use it;
    // do not invent photos for individual headlines or scrape article pages.
    const fallback=element("span", "explorer-art-label",
      COVER_LABELS[appearanceFor(item.category)]);
    artwork.append(fallback);
    const imageUrl=safeNewsImage(item.image_url);
    if(imageUrl) {
      const img=document.createElement("img");
      img.className="explorer-art-image";
      img.alt=""; // The story headline is already the accessible button label.
      img.loading="lazy";
      img.decoding="async";
      img.referrerPolicy="no-referrer";
      img.src=imageUrl;
      img.addEventListener("load",()=>{if(img.naturalWidth>=160 && img.naturalHeight>=90) artwork.classList.add("has-publisher-image"); else img.remove();});
      img.addEventListener("error",()=>{
        artwork.classList.remove("has-publisher-image");
        img.remove();
      });
      artwork.append(img,element("span","explorer-cover-credit","PUBLISHER IMAGE"));
    }
    const body = element("span", "explorer-tile-body");
    body.append(
      element("span", "explorer-tile-publisher", item.publisher || "Source"),
      element("span", "explorer-tile-title", item.title || "Untitled news"),
      element("span", "explorer-tile-category", item.region === "india" ? "INDIA / " + item.category : "GLOBAL / " + item.category)
    );
    tile.append(artwork, body);
    tile.addEventListener("click", () => {
      paused = true;
      select(item.id, true);
    });
    return tile;
  }
  function paintTiles() {
    const index = activeIndex();
    for (let i = 0; i < current.length; i++) {
      const item = current[i], tile = nodes.get(item.id);
      if (!tile) continue;
      const d = relativePosition(i, index, current.length);
      tile.dataset.position = d >= -2 && d <= 2 ? String(d) : "far";
      tile.setAttribute("aria-pressed", String(item.id === selectedId));
      tile.setAttribute("aria-current", item.id === selectedId ? "true" : "false");
      tile.tabIndex = mode === "gallery" || Math.abs(d) <= 2 ? 0 : -1;
      tile.style.zIndex = mode === "layered" ? String(12 - Math.abs(d)) : "";
    }
    const total = current.length;
    count.textContent = total + " " + (total === 1 ? "story" : "stories");
    selectedCount.textContent = total ? (index + 1) + " / " + total : "0 / 0";
    prev.disabled = next.disabled = total < 2;
  }
  function showDetails() {
    const item = current.find(x => x.id === selectedId);
    if (!item) { detail.hidden = true; shade.hidden = true; return; }
    const show = mode === "layered" || drawerOpen;
    detail.hidden = !show;
    shade.hidden = !(mode === "gallery" && drawerOpen);
    if (!show) return;
    title.textContent = item.title || "Untitled news";
    publisher.textContent = (item.publisher || "Publisher") +
      " · " + (typeof dateLabel === "function" ? dateLabel(item) : "") +
      " · " + (item.region === "india" ? "India" : "Global");
    description.textContent = item.source_preview ||
      "Publisher headline only. Read the original story to confirm the details.";
    const href = validPublisherLink(item.source_url);
    source.hidden = !href;
    if (href) source.href = href;
    editorial.replaceChildren(buildFullCard(item));
    tools.hidden = true;
    reveal.setAttribute("aria-expanded", "false");
    reveal.textContent = "Open all editorial tools";
    detail.dataset.open = String(mode === "layered" || drawerOpen);
    if (mode === "gallery" && drawerOpen) close.focus({preventScroll:true});
  }
  function select(id, user = false) {
    if (!current.some(x => x.id === id)) return;
    const changed = selectedId !== id;
    selectedId = id;
    if (mode === "gallery") drawerOpen = user;
    paintTiles();
    if (changed || user) showDetails();
  }
  function step(direction) {
    if (current.length < 2) return;
    const i = (activeIndex() + direction + current.length) % current.length;
    selectedId = current[i].id;
    paintTiles();
    showDetails();
  }
  function paintView() {
    root.dataset.mode = mode;
    modes.forEach(button => {
      const chosen = button.dataset.explorerMode === mode;
      button.classList.toggle("active",chosen);
      button.setAttribute("aria-pressed",String(chosen));
    });
    paintTiles();
    showDetails();
  }
  function setMode(nextMode) {
    if (!["layered", "gallery"].includes(nextMode) || nextMode === mode) return;
    drawerOpen = false;
    paused = false;
    const transition = document.startViewTransition;
    if (typeof transition === "function" && !(reduceMotion && reduceMotion.matches)) {
      document.startViewTransition(() => { mode = nextMode; paintView(); });
    } else { mode = nextMode; paintView(); }
    if (typeof onModeChange === "function") onModeChange(mode);
  }
  modes.forEach(button => button.addEventListener("click", () => setMode(button.dataset.explorerMode)));
  prev.addEventListener("click",() => { paused=true; step(-1); });
  next.addEventListener("click",() => { paused=true; step(1); });
  close.addEventListener("click",() => { drawerOpen=false; showDetails(); canvas.focus({preventScroll:true}); });
  shade.addEventListener("click",() => { drawerOpen=false; showDetails(); });
  reveal.addEventListener("click",() => {
    const next = tools.hidden;
    tools.hidden = !next;
    reveal.setAttribute("aria-expanded", String(next));
    reveal.textContent = next ? "Hide editorial tools" : "Open all editorial tools";
  });
  root.addEventListener("keydown", event => {
    if (event.key === "Escape" && drawerOpen) {
      drawerOpen = false; showDetails(); canvas.focus({preventScroll:true});
    } else if (mode === "layered" && (event.key === "ArrowLeft" || event.key === "ArrowRight") &&
        !(event.target instanceof HTMLInputElement) &&
        !(event.target instanceof HTMLTextAreaElement) &&
        !(event.target instanceof HTMLSelectElement)) {
      event.preventDefault(); paused = true;
      step(event.key === "ArrowRight" ? 1 : -1);
    }
  });
  canvas.addEventListener("mouseenter",()=> { paused = true; });
  canvas.addEventListener("mouseleave",()=> { paused = false; });
  detail.addEventListener("focusin",()=> { paused = true; });
  canvas.addEventListener("touchstart",event => {
    touchStart=event.changedTouches[0]?.clientX ?? null;
  },{passive:true});
  canvas.addEventListener("touchend",event => {
    const end=event.changedTouches[0]?.clientX ?? null;
    if(mode === "layered" && touchStart !== null && end !== null && Math.abs(end-touchStart)>55) {
      paused = true; step(end < touchStart ? 1 : -1);
    }
    touchStart=null;
  },{passive:true});
  // Single browser timer. News is fetched elsewhere; no network, storage or posting.
  const timer = window.setInterval(() => {
    if (mode !== "layered" || root.hidden || paused || drawerOpen ||
        (reduceMotion && reduceMotion.matches) || document.hidden ||
        root.contains(document.activeElement) && detail.contains(document.activeElement)) return;
    step(1);
  }, 5400);
  return {
    render(items) {
      current = Array.isArray(items) ? items.slice(0,100) : [];
      if (!current.some(x => x.id === selectedId)) selectedId = current[0]?.id ?? null;
      const ids = new Set(current.map(x => x.id));
      for (const [id, tile] of nodes) {
        if (!ids.has(id)) { tile.remove(); nodes.delete(id); }
      }
      current.forEach((item, index) => {
        if (!nodes.has(item.id)) nodes.set(item.id, buildTile(item,index));
      });
      canvas.replaceChildren(...current.map(x => nodes.get(x.id)));
      root.hidden = !current.length;
      drawerOpen=false;
      paintView();
    },
    setMode,
    hide() {
      root.hidden=true;
      drawerOpen=false;
      paused=true;
      shade.hidden=true;
      detail.hidden=true;
    },
    destroy() { window.clearInterval(timer); }
  };
}
