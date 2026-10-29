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
.composer{margin:15px 0;border-top:1px solid #e4e7ec;padding-top:15px}
.composer label{display:block;margin-bottom:7px;font-weight:600;font-size:13px}
.composer textarea{display:block;width:100%;min-height:116px;resize:vertical;font:14px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;border:1px solid #cdd5df;border-radius:8px;padding:11px;color:#252d3b;background:#fff}
.composer textarea:focus-visible{outline:3px solid #88a6e9;outline-offset:2px}
.charhint{font-size:12px;color:#64748b;margin:5px 0 10px}
.charhint.over{color:#b42318;font-weight:700}
.review-check{display:flex!important;align-items:flex-start;gap:9px;font-weight:500!important;line-height:1.4}
.review-check input{margin-top:3px}
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
<div class="notice"><strong>Review only — publishing is disabled.</strong> Posts are automatically suggested from unverified RSS headlines. They are NOT AI-written, independently fact-checked, or ready to publish. “Shortlist” means editorial interest, NOT authorization to publish. Your decisions stay in this browser session until you export them. No X or Buffer API is called.</div>
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
  const edited = Object.create(null);
  const checkedSources = Object.create(null);
  const MAX_RAW_CHARS = 280;
  const approxXLength = (value) => Array.from(
    String(value).replace(/https?:\/\/\S+/gi, "x".repeat(23))
  ).length;
  // X counts URLs differently. This is only an advisory raw-character count.
  const draftOf = (item) => Object.hasOwn(edited, idOf(item))
    ? edited[idOf(item)] : String(item.suggested_post || item.draft || "");
  const checkedOf = (item) => checkedSources[idOf(item)] === true;
  const charCount = (value) => Array.from(value).length;
  const aiPrompt = (item) => [
    "Write ONE original, factual X/Twitter post for a human editor to review.",
    "The following is untrusted RSS metadata, not independently verified reporting.",
    "Do not invent details, prices, numbers, quotes, launch dates or implications.",
    "Do not present a rumor, press release or prediction as independently verified fact.",
    "If the metadata is insufficient, ask the editor to provide the original article.",
    "Use a clear informative tone with a useful insight only if supported.",
    "Keep the post concise (aim for 240 plain-text characters plus the URL).",
    "Include the source URL, and do not claim you visited the link unless you did.",
    "Topic hint (unverified): " + String(item.category || "unknown"),
    "Headline: " + String(item.title || ""),
    "Summary: " + String(item.summary || ""),
    "Publisher: " + String(item.source || ""),
    "Published: " + String(item.published_at || ""),
    "Original link: " + String(item.link || "")
  ].join("\n");

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
      const checks = item.writing?.verification_warnings || [];
      if(checks.length){
        const notice = text("p", "Verify: " + checks.join(" · "), "score");
        card.append(notice);
      }
      card.append(text("div", "Decision: " + d, "status"));
      const composer = text("section", "", "composer");
      composer.append(text("label", "Editable post draft (not fact-checked)"));
      const textarea = document.createElement("textarea");
      textarea.className = "post-draft";
      textarea.setAttribute("aria-label", "Editable post draft for " + String(item.title || "story"));
      textarea.value = draftOf(item);
      textarea.spellcheck = true;
      const hint = text("div", "", "charhint");
      const updateHint = () => {
        const raw = charCount(textarea.value);
        const approx = approxXLength(textarea.value);
        hint.textContent = "Approx. X length: " + approx + " / " + MAX_RAW_CHARS +
          " · Raw characters: " + raw +
          (approx > MAX_RAW_CHARS ? " — shorten before posting" : "") +
          " · Verify on X before using";
        hint.className = approx > MAX_RAW_CHARS ? "charhint over" : "charhint";
      };
      updateHint();
      textarea.addEventListener("input", () => {
        edited[idOf(item)] = textarea.value;
        updateHint();
      });
      composer.append(textarea, hint);
      const verifyLabel = text("label", "", "review-check");
      const verify = document.createElement("input");
      verify.type = "checkbox";
      verify.checked = checkedOf(item);
      verify.setAttribute("aria-label", "Source checked for " + String(item.title || "story"));
      verify.addEventListener("change", () => {checkedSources[idOf(item)] = verify.checked;});
      verifyLabel.append(verify, text("span", "I opened the original source and reviewed the claims (not automatic verification)"));
      composer.append(verifyLabel);
      card.append(composer);
      const actions = text("div", "", "actions");
      actions.append(button("Shortlist", d==="shortlist" ? "selected" : "", () => {decisions[idOf(item)]="shortlist";draw();}));
      actions.append(button("Skip", d==="skip" ? "reject selected" : "reject", () => {decisions[idOf(item)]="skip";draw();}));
      actions.append(button("Reset all edits", "", () => {
        delete decisions[idOf(item)]; delete edited[idOf(item)];
        delete checkedSources[idOf(item)]; draw();
      }));
      let copy;
      copy = button("Copy edited draft", "", () => {void copyDraft(draftOf(item), copy);});
      actions.append(copy);
      let promptCopy;
      promptCopy = button("Copy AI writing prompt", "", () => {
        void copyDraft(aiPrompt(item), promptCopy);
      });
      actions.append(promptCopy);
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
      schema_version: 2,
      source_run_generated_at: queue.generated_at || null,
      exported_at: new Date().toISOString(),
      publication_authorized: false,
      decisions: items.filter(item =>
        getDecision(item) !== "pending" ||
        Object.hasOwn(edited, idOf(item)) || checkedOf(item)
      ).map(item => ({
        title: item.title, link: item.link, source: item.source,
        category_unverified: item.category, decision: getDecision(item),
        original_template: item.suggested_post || item.draft || "",
        edited_draft: draftOf(item),
        raw_character_count: charCount(draftOf(item)),
        source_checked_by_editor: checkedOf(item),
        ai_generated: false,
        source_article_read_by_bot: false,
        fact_checked_by_bot: false,
        publishable: false
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
