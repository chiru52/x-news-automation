import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {relativePosition, appearanceFor, canUseExplorer, detailPresentation} from "../dashboard/news-explorer.mjs";

const html=readFileSync(new URL("../dashboard/index.html",import.meta.url),"utf8");
const app=readFileSync(new URL("../dashboard/app.js",import.meta.url),"utf8");
const css=readFileSync(new URL("../dashboard/styles.css",import.meta.url),"utf8");

test("layer position cycles through news without duplicating or dropping an item",()=>{
  assert.deepEqual(Array.from({length:5},(_,i)=>relativePosition(i,0,5)),[0,1,2,-2,-1]);
  assert.deepEqual(Array.from({length:5},(_,i)=>relativePosition(i,2,5)),[-2,-1,0,1,2]);
  assert.equal(relativePosition(0,0,1),0);
  assert.equal(relativePosition(0,0,0),99);
});
test("India view shows rolling freshness window without changing Global",()=>{
  const ui=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  assert.match(ui,/root\.dataset\.scope === "india" \? " · PAST 72 HOURS"/);
  assert.match(app,/dataset\.scope=selectedView/);
  assert.match(app,/past 72 hours/);
});
test("news explorer only replaces the public news views, never workflow, saved or archive",()=>{
  for(const view of ["all","global","india","trending"])assert.equal(canUseExplorer(view),true);
  for(const view of ["workflow","copied","saved","archive","account"])assert.equal(canUseExplorer(view),false);
});
test("untrusted category values cannot form arbitrary CSS or HTML classes",()=>{
  assert.equal(appearanceFor("markets"),"markets");
  assert.equal(appearanceFor("technology"),"technology");
  assert.equal(appearanceFor("saas"),"saas");
  assert.equal(appearanceFor("x<script>"),"technology");
});
test("identical news stream supports layered and gallery modes plus original cards",()=>{
  assert.match(html,/id="news-explorer"/);
  assert.match(html,/class="explorer-canvas"/);
  assert.match(html,/class="explorer-detail"/);
  assert.match(html,/data-explorer-mode="layered"/);
  assert.match(html,/data-explorer-mode="gallery"/);
  assert.match(html,/class="explorer-editor"/);
  assert.match(app,/buildFullCard:\s*card/);
  assert.match(app,/newsExplorer\.render\(list\)/);
  assert.match(app,/safeNewsImage\(item.image_url\)/);
  assert.match(app,/newsExplorer\.hide\(\)/);
  assert.match(css,/news-explorer\[data-mode="gallery"\]/);
  assert.match(css,/prefers-reduced-motion:reduce/);
  assert.match(html,/id="story-card"/);
  assert.match(html,/class="save-button"/);
  assert.match(html,/class="review-add"/);
  assert.match(html,/class="copy-button"/);
});
test("no automated X publishing, remote fonts, or image API used by explorer",()=>{
  const module=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  assert.doesNotMatch(module,/\bfetch\s*\(|XMLHttpRequest|sendBeacon|api\.x\.com|twitter\.com\/intent|import\s*\(/i);
  assert.doesNotMatch(module,/innerHTML\s*=|insertAdjacentHTML|eval\s*\(/i);
  assert.doesNotMatch(css,/url\(['"]?https?:\/\//i);
});

test("selecting a story opens editorial immediately in gallery and layered views",()=>{
  assert.deepEqual(detailPresentation("gallery",false,true),{open:false,shade:false,tools:false});
  assert.deepEqual(detailPresentation("gallery",true,true),{open:true,shade:true,tools:true});
  assert.deepEqual(detailPresentation("layered",false,true),{open:true,shade:false,tools:true});
  assert.deepEqual(detailPresentation("layered",true,true),{open:true,shade:false,tools:true});
  assert.deepEqual(detailPresentation("layered",false,false),{open:false,shade:false,tools:false});
});
test("focused story is one click with an accessible editorial section and no second reveal",()=>{
  const module=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  assert.match(module,/tile\.addEventListener\("click",\s*\(\)\s*=>\s*\{[\s\S]*?select\(item\.id, true\)/);
  assert.match(module,/tools\.hidden = !presentation\.tools/);
  assert.doesNotMatch(module,/explorer-show-tools|Open all editorial tools/);
  assert.doesNotMatch(html,/explorer-show-tools|Open all editorial tools/);
  assert.match(html,/class="explorer-detail-body"/);
  assert.match(html,/class="explorer-tools" id="explorer-tools" aria-label="Editorial tools for selected story"/);
  assert.match(html,/class="explorer-tools-heading"/);
  assert.match(css,/\.news-explorer\[data-mode="gallery"\] \.explorer-detail-body\s*\{/);
  assert.match(css,/\.explorer-editor \.story-card>\.card-title/);
  assert.match(css,/\.news-explorer \[hidden\]/);
});
test("draft editor is preserved on same story and user interactions stop automatic advancement",()=>{
  const module=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  assert.match(module,/if \(renderedId !== item\.id\) \{\s*editorial\.replaceChildren\(buildFullCard\(item\)\)/);
  assert.match(module,/detail\.addEventListener\("pointerdown",\s*\(\)\s*=>\s*\{\s*manualPause = paused = true/);
  assert.match(module,/if \(!manualPause\) paused = false/);
  assert.match(app,/editor\.addEventListener\("input",\s*\(\)\s*=>\s*\{\s*rememberEdit\(item\.id,/);
  assert.match(app,/const currentDraft = \(\) => edits\.has\(item\.id\) \? edits\.get\(item\.id\) : suggestion/);
  assert.doesNotMatch(module,/publishToX|sendPost|twitter\.com\/intent/);
});
