import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
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

test("Layered uses the empty header-side space for a full editorial panel",()=>{
  const section=(css.split("/* Layered editorial layout:",2)[1]||"").split("/* Discovery toolbar:",1)[0];
  assert.ok(section,"Layered-only layout override is present");
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-stage\s*\{\s*display:contents;/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-detail\s*\{\s*grid-column:2;\s*grid-row:1 \/ span 2;/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-heading\s*\{\s*grid-column:1;\s*grid-row:1;/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-canvas\s*\{\s*grid-column:1;\s*grid-row:2;/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-bottom\s*\{\s*grid-column:1 \/ -1;\s*grid-row:3;/);
});
test("Layered removes the small internal scroller, compacts heading and preserves responsive layout",()=>{
  const section=(css.split("/* Layered editorial layout:",2)[1]||"").split("/* Discovery toolbar:",1)[0];
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-detail\s*\{\s*max-height:none;\s*overflow:visible;/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-heading h2\s*\{\s*font-size:clamp\(35px,3\.65vw,50px\)/);
  assert.match(section,/@media\(min-width:960px\)/);
  assert.match(section,/@media\(max-width:959px\)/);
  assert.match(section,/\.news-explorer\[data-mode="layered"\] \.explorer-stage\s*\{\s*display:flex;\s*flex-direction:column;/);
  assert.doesNotMatch(section,/\.news-explorer\[data-mode="gallery"\]/);
  assert.match(css,/\.news-explorer\[data-mode="gallery"\] \.explorer-detail:not\(\[hidden\]\)/);
  // Preserve existing editor and workflow controls; no duplicate click required.
  assert.match(html,/class="explorer-tools" id="explorer-tools"/);
  assert.doesNotMatch(html,/Open all editorial tools/);
  assert.doesNotMatch(section,/url\(['"]?https?:\/\//);
});

test("News Explorer is the default studio instead of a separate back-to-workspace mode",()=>{
  assert.doesNotMatch(html,/id="explorer-focus"|Back to workspace/);
  assert.doesNotMatch(html,/data-explorer-section=/);
  assert.match(app,/function applyExplorerFocus\(show\)\s*\{\s*document\.body\.classList\.toggle\("news-focus-mode",Boolean\(show\)\)/);
  assert.doesNotMatch(app,/explorerFocusEnabled|signaldesk:explorer-focus:v1/);
  assert.match(app,/let records = \[\], selectedView = "all"/);
  assert.match(app,/const useExplorer=canUseExplorer\(selectedView\) && list\.length>0/);
  assert.match(app,/newsExplorer\.render\(list\)/);
});
test("sidebar reuses every existing destination and keeps Overview optional",()=>{
  for(const view of ["all","trending","global","india","overview","workflow","copied","saved","archive"]){
    assert.equal((html.match(new RegExp('data-view="'+view+'"',"g"))||[]).length,1,view);
  }
  assert.match(html,/id="sidebar-toggle"[^>]+aria-expanded="false"[^>]+aria-label="Expand sidebar"/);
  assert.match(html,/id="sidebar-settings"/);
  assert.match(html,/class="sidebar-section-label sidebar-section-work">MY WORKSPACE/);
  assert.match(app,/SIDEBAR_KEY="signaldesk:sidebar-collapsed:v1"/);
  assert.match(app,/function setSidebarCollapsed\(collapsed\)/);
  assert.match(app,/localStorage\.setItem\(SIDEBAR_KEY,String\(sidebarCollapsed\)\)/);
  assert.match(app,/document\.body\.classList\.toggle\("sidebar-collapsed",sidebarCollapsed\)/);
  assert.match(app,/document\.querySelector\("\.feed-section"\)\.hidden = overview/);
  assert.match(app,/if \(overview\) \{\s*applyExplorerFocus\(false\);\s*newsExplorer\.hide\(\);\s*return;/);
  assert.match(app,/\$\("dashboard-metrics"\)\.hidden = selectedView !== "overview"/);
  assert.match(app,/\$\("dashboard-intro"\)\.hidden = selectedView !== "overview"/);
});
test("studio rail remains available in focus, with accessible mobile slideout and dark mode",()=>{
  const section=css.split("/* SignalDesk Studio shell:",2)[1]||"";
  assert.ok(section);
  assert.match(section,/body\.news-focus-mode \.sidebar\{\s*display:flex/);
  assert.match(section,/body\.sidebar-collapsed\.news-focus-mode \.shell\{\s*grid-template-columns:72px/);
  assert.match(section,/grid-template-columns:242px minmax\(0,1fr\)/);
  assert.match(section,/\.sidebar-top\{display:none\}/);
  assert.match(section,/\.sidebar \.nav-items\{\s*position:fixed;z-index:80/);
  assert.match(section,/transform:translateX\(-105%\)/);
  assert.match(section,/\.sidebar\.mobile-nav-open \.nav-items\{transform:translateX\(0\)/);
  assert.match(section,/\[data-theme="dark"\] \.sidebar-toggle/);
  assert.match(section,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(app,/setMobileMenuOpen\(false\)/);
  assert.match(app,/\$\("sidebar-settings"\)\.addEventListener\("click"/);
  assert.doesNotMatch(section,/api\.x\.com|cloudflare\/workers|@import|url\(['"]?https?:\/\//);
});

test("one top toolbar retains search, every topic and accessible layout icon switches",()=>{
  const bar=html.split('<div class="toolbar">',2)[1]?.split('</div>\n          </div>',1)[0]||"";
  assert.match(bar,/id="search-input"/);
  for(const topic of ["all","technology","world","policy","factcheck","saas","markets"])
    assert.match(bar,new RegExp('data-filter="'+topic+'"'));
  assert.equal((html.match(/data-explorer-mode="layered"/g)||[]).length,1);
  assert.equal((html.match(/data-explorer-mode="gallery"/g)||[]).length,1);
  assert.match(html,/aria-label="Layered view" title="Layered view"/);
  assert.match(html,/aria-label="Gallery view" title="Gallery view"/);
  assert.match(html,/class="studio-view-switch explorer-switch"/);
  assert.match(app,/document\.querySelector\("\.studio-view-switch"\)\.hidden = !canUseExplorer\(selectedView\)/);
  const explorer=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  assert.match(explorer,/document\.querySelectorAll\("\[data-explorer-mode\]"\)/);
  assert.match(explorer,/document\.body\.dataset\.newsLayout = mode/);
  assert.match(explorer,/modes\.forEach\(button => button\.addEventListener\("click"/);
});
test("source directory follows the story explorer, and gallery gets container-responsive five columns",()=>{
  assert.ok(html.indexOf('id="source-directory"')>html.indexOf('id="news-explorer"'));
  assert.ok(html.indexOf('id="source-directory"')>html.indexOf('id="empty"'));
  assert.match(html,/News sources &amp; coverage/);
  const section=css.split("/* Discovery toolbar:",2)[1]||"";
  assert.match(section,/grid-template-columns:minmax\(190px,340px\) minmax\(0,1fr\) auto/);
  assert.match(section,/body\.news-focus-mode\[data-news-layout="gallery"\] \.feed-section>\.toolbar/);
  assert.match(section,/position:sticky;top:6px/);
  assert.match(section,/container:story-gallery \/ inline-size/);
  assert.match(section,/@container story-gallery \(min-width:1420px\)/);
  assert.match(section,/grid-template-columns:repeat\(5,minmax\(0,1fr\)\)/);
  assert.match(section,/@media\(max-width:980px\)/);
  assert.match(section,/top:calc\(var\(--signaldesk-header-height,64px\) \+ 3px\)/);
});
test("topic chips show true availability and cannot lead to a dead-end empty state",()=>{
  assert.match(app,/const counts=rows \? topicAvailability\(rows\) : null/);
  assert.match(app,/button\.dataset\.topicCount=String\(count\)/);
  assert.match(app,/button\.disabled=category!=="all" && count===0 && category!==selectedCategory/);
  assert.match(app,/updateTopicAvailability\(list\)/);
  assert.match(app,/const totalBeforeTopic=list\.length/);
  assert.match(app,/if\(selectedCategory!=="all"\)list=list\.filter\(item=>item\.category===selectedCategory\)/);
  assert.match(app,/dataset\.topicTotal=String\(totalBeforeTopic\)/);
  assert.match(css,/\.toolbar \.filter:disabled/);
  assert.match(css,/\.toolbar \.filter\[data-topic-count\]::after/);
  assert.match(app,/updateTopicAvailability\(\)/); // archive/overview retain usable controls
});

test("regression: toolbar class selector cannot crash the 75-story feed render",()=>{
  // Exercise the exact statement executed at the top of render(), not merely
  // the presence of the toolbar in HTML. The former $(class) lookup uses
  // getElementById and caused a TypeError after records were already loaded.
  const statement=app.match(/^  document\.querySelector\("\.studio-view-switch"\)\.hidden = !canUseExplorer\(selectedView\);$/m)?.[0];
  assert.ok(statement,"View switch is queried by CSS class, not ID");
  assert.doesNotMatch(app,/\$\(["']\.[^"']+["']\)/);
  const toggle={hidden:null};
  const document={
    getElementById:()=>{throw Error("A class name must not be passed as an ID");},
    querySelector:(selector)=>{
      assert.equal(selector,".studio-view-switch");
      return toggle;
    }
  };
  runInNewContext(statement,{document,canUseExplorer:(view)=>view==="all",selectedView:"all"});
  assert.equal(toggle.hidden,false,"Explorer switch stays visible in All stories");
  runInNewContext(statement,{document,canUseExplorer:(view)=>view==="all",selectedView:"workflow"});
  assert.equal(toggle.hidden,true,"Explorer switch hides in personal workflow");
});
test("UI render exceptions are not falsely reported as live feed failures",()=>{
  assert.match(app,/let displayStarted=false;/);
  assert.match(app,/displayStarted=true;\s*render\(\);\s*displayStarted=false;/);
  assert.match(app,/if \(displayStarted\) \{[\s\S]*?SignalDesk news rendering failed/);
  assert.match(app,/News loaded, but the display encountered an error/);
  assert.match(app,/The latest feed check failed\. Existing news remains available/);
});
