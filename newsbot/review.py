"""Standalone, client-only editorial review page for GitHub Actions artifacts.

The page never sends drafts or decisions to any API. All user-entered decisions
stay in memory until manually exported as a JSON file.
"""
from __future__ import annotations

import json


def create_review_page(payload: dict) -> str:
    # JSON appears in an inert script element. Escape HTML-sensitive and JS
    # line-separator characters, including malicious text from external RSS feeds.
    safe_json = (json.dumps(payload, ensure_ascii=False)
                 .replace("&", "\\u0026").replace("<", "\\u003c")
                 .replace(">", "\\u003e").replace("\u2028", "\\u2028")
                 .replace("\u2029", "\\u2029"))
    return HTML.replace("__QUEUE_DATA__", safe_json)


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X News — Editorial Review</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:#f5f6f8;color:#202633}
*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit}
header{background:#fff;border-bottom:1px solid #e4e6eb;padding:24px max(20px,calc((100vw - 1050px)/2))}
header h1{font-size:26px;letter-spacing:-.6px;margin:0 0 8px}header p{color:#66717f;margin:0}
main{max-width:1050px;margin:auto;padding:20px}
.notice{padding:13px 16px;background:#fff8e7;border:1px solid #eed39a;border-radius:12px;color:#624b18;margin-bottom:16px;line-height:1.5}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.tile,.card,.toolbar{background:#fff;border:1px solid #e4e7ec;border-radius:12px}
.tile{padding:16px}.tile strong{display:block;font-size:27px}.tile span,.muted{color:#697586;font-size:13px}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;padding:12px;margin-bottom:14px;align-items:center}
.toolbar input{flex:1;min-width:175px}.toolbar input,.toolbar select{border:1px solid #d7dae1;border-radius:8px;padding:10px;background:#fff}
button{border:1px solid #ced3de;border-radius:8px;padding:9px 12px;background:#fff;color:#202633;cursor:pointer}
button:hover{background:#f1f3f7}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #88a6e9;outline-offset:2px}
button.primary{background:#1b45a7;border-color:#1b45a7;color:#fff}button.primary:hover{background:#173c91}
button.selected{border-color:#1b45a7;background:#eaf1ff;color:#173f9f}
button.reject.selected{border-color:#af253f;background:#fff0f2;color:#9b1a35}
.card{padding:18px;margin-bottom:13px}
.card h2{font-size:18px;line-height:1.35;margin:10px 0}
.meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;color:#687385;font-size:13px}
.pill{border-radius:20px;padding:4px 9px;background:#edf0f5;color:#38465c;font-weight:600;font-size:12px}
.status{font-weight:600;color:#46536a}
.score{font-size:13px;color:#52647b;margin:8px 0}
.card a{color:#1746a6;text-decoration:underline;text-underline-offset:3px}
.card pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f8fb;padding:12px;border-radius:9px;line-height:1.5;font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.actions{display:flex;gap:8px;flex-wrap:wrap}
footer{max-width:1050px;margin:10px auto;padding:0 20px 25px;color:#697586;font-size:12px}
@media(max-width:620px){.summary{grid-template-columns:1fr 1fr}.toolbar{align-items:stretch}.toolbar input{flex-basis:100%}header{padding:20px}}
</style>
</head>
<body>
<header>
<h1>X News · Editorial review</h1>
<p>Technology & AI · Markets · SaaS & startups</p>
</header>
<main>
<div class="notice"><strong>Review only — publishing is disabled.</strong> These are RSS-based templates, not AI-written or fact-checked posts. “Shortlist” means editorial interest, NOT authorization to publish. Your decisions stay in this browser session until you export them. No X or Buffer API is called.</div>
<div class="summary">
<div class="tile"><strong id="total">0</strong><span>Draft candidates</span></div>
<div class="tile"><strong id="shortlisted">0</strong><span>Shortlisted</span></div>
<div class="tile"><strong id="skipped">0</strong><span>Skipped</span></div>
</div>
<div class="toolbar">
<input id="search" aria-label="Search articles" placeholder="Search headlines or sources">
<select id="category" aria-label="Filter category">
<option value="all">All categories</option>
<option value="technology">Technology & AI</option>
<option value="markets">Markets</option>
<option value="saas">SaaS & startups</option>
</select>
<select id="decisionFilter" aria-label="Filter review status">
<option value="all">All decisions</option>
<option value="pending">Pending</option>
<option value="shortlist">Shortlisted</option>
<option value="skip">Skipped</option>
</select>
<button id="export" class="primary">Export decisions JSON</button>
</div>
<p id="empty" class="muted"></p>
<div id="cards"></div>
</main>
<footer>Standalone offline review page. Nothing is uploaded, scheduled or sent. Open source links to verify facts and follow the publishers' terms.</footer>
<script id="queue-data" type="application/json">__QUEUE_DATA__</script>
<script>
"use strict";
(function(){
  const queue = JSON.parse(document.getElementById("queue-data").textContent);
  const items = Array.isArray(queue.articles) ? queue.articles : [];
  const decisions = Object.create(null);
  const cards = document.getElementById("cards");
  const search = document.getElementById("search");
  const category = document.getElementById("category");
  const decisionFilter = document.getElementById("decisionFilter");
  const empty = document.getElementById("empty");
  const text = (tag, value, className) => {
    const element = document.createElement(tag);
    element.textContent = String(value == null ? "" : value);
    if (className) element.className = className;
    return element;
  };
  const safeSourceUrl = (url) => {
    try {
      const parsed = new URL(url);
      return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null;
    } catch (_) { return null; }
  };
  const button = (label, className, onClick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (className) b.className = className;
    b.addEventListener("click", onClick);
    return b;
  };
  const idOf = (item) => String(item.link || "");
  const getDecision = (item) => decisions[idOf(item)] || "pending";
  async function copyDraft(value, control){
    try {
      await navigator.clipboard.writeText(value);
      control.textContent = "Copied";
    } catch (_) {
      const field = document.createElement("textarea");
      field.value = value;
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      const worked = document.execCommand("copy");
      field.remove();
      control.textContent = worked ? "Copied" : "Copy unavailable";
    }
  }
  function draw(){
    cards.replaceChildren();
    const term = search.value.trim().toLowerCase();
    let visible = 0;
    let short = 0, skip = 0;
    items.forEach(item => {
      const d = getDecision(item);
      if(d === "shortlist") short++;
      if(d === "skip") skip++;
      if(category.value !== "all" && item.category !== category.value) return;
      if(decisionFilter.value !== "all" && d !== decisionFilter.value) return;
      if(term && ![item.title,item.source,item.summary].join(" ").toLowerCase().includes(term)) return;
      visible++;
      const card = text("article", "", "card");
      const meta = text("div", "", "meta");
      meta.append(text("span", item.category || "unknown", "pill"));
      meta.append(text("span", item.source || "Unknown source"));
      meta.append(text("span", item.published_at || ""));
      card.append(meta);
      card.append(text("h2", item.title));
      if(item.summary) card.append(text("p", item.summary));
      const link = safeSourceUrl(item.link);
      if(link){
        const a = text("a", "Open original source ↗");
        a.href = link; a.target = "_blank"; a.rel = "noopener noreferrer";
        card.append(a);
      }
      const info = item.relevance || {};
      card.append(text("p", "Heuristic score: " + String(info.score ?? "n/a") +
        " · Matched terms: " + ((info.headline_terms || []).join(", ") || "none") +
        " · Category not verified", "score"));
      card.append(text("div", "Decision: " + d, "status"));
      card.append(text("pre", item.draft || "(No draft provided)"));
      const actions = text("div", "", "actions");
      actions.append(button("Shortlist", d==="shortlist" ? "selected" : "", () => {decisions[idOf(item)]="shortlist";draw();}));
      actions.append(button("Skip", d==="skip" ? "reject selected" : "reject", () => {decisions[idOf(item)]="skip";draw();}));
      actions.append(button("Reset", "", () => {delete decisions[idOf(item)];draw();}));
      let copy;
      copy = button("Copy template", "", () => {void copyDraft(item.draft || "", copy);});
      actions.append(copy);
      card.append(actions);
      cards.append(card);
    });
    document.getElementById("total").textContent = String(items.length);
    document.getElementById("shortlisted").textContent = String(short);
    document.getElementById("skipped").textContent = String(skip);
    empty.textContent = visible ? "" : "No review candidates match your filters.";
  }
  document.getElementById("export").addEventListener("click", () => {
    const result = {
      schema_version: 1,
      source_run_generated_at: queue.generated_at || null,
      exported_at: new Date().toISOString(),
      publication_authorized: false,
      decisions: items.filter(item => getDecision(item)!=="pending").map(item => ({
        title: item.title, link: item.link, source: item.source,
        category_unverified: item.category, decision: getDecision(item),
        draft_template: item.draft || ""
      }))
    };
    const blob = new Blob([JSON.stringify(result, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "editorial-decisions.json";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  search.addEventListener("input",draw);
  category.addEventListener("change",draw);
  decisionFilter.addEventListener("change",draw);
  draw();
})();
</script>
</body>
</html>"""
