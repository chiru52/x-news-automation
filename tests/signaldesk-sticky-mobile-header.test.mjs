import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync(new URL("../dashboard/index.html",import.meta.url),"utf8");
const css=readFileSync(new URL("../dashboard/styles.css",import.meta.url),"utf8");
const js=readFileSync(new URL("../dashboard/app.js",import.meta.url),"utf8");
const header=html.split('<header class="topbar">',2)[1]?.split("</header>",1)[0]||"";
const sidebar=html.split('<aside class="sidebar"',2)[1]?.split("</aside>",1)[0]||"";

test("one mobile toolbar keeps navigation after the profile icon",()=>{
  assert.equal((html.match(/id="mobile-menu-toggle"/g)||[]).length,1);
  assert.ok(header.indexOf('id="profile-toggle"')>=0);
  assert.ok(header.indexOf('id="mobile-menu-toggle"')>header.indexOf('id="profile-toggle"'));
  assert.ok(!sidebar.includes('id="mobile-menu-toggle"'));
  assert.match(header,/aria-controls="sidebar-menu" aria-expanded="false" aria-label="Open navigation menu"/);
  assert.match(html,/id="mobile-current-view"/);
});
test("navigation stays in the sidebar for desktop and dropdown for mobile",()=>{
  assert.match(sidebar,/id="sidebar-menu"/);
  for(const view of ["all","trending","global","india","workflow","copied","saved","archive"]){
    assert.ok(sidebar.includes('data-view="'+view+'"'),view);
  }
  assert.match(css,/\.topbar\s*\{[^}]*position:sticky;top:0;z-index:70;/);
  assert.match(css,/\.sidebar,\.sidebar\.mobile-nav-open\s*\{[^}]*height:0;min-height:0;/);
  assert.match(css,/\.sidebar \.nav-items\s*\{[^}]*position:fixed;z-index:80;/);
  assert.match(css,/\.mobile-menu-backdrop:not\(\[hidden\]\)\s*\{[^}]*z-index:60;/);
  assert.match(css,/\.topbar \.mobile-menu-caption,\.topbar \.mobile-menu-caret\{display:none;\}/);
});
test("existing navigation behavior and keyboard close remain intact",()=>{
  assert.match(js,/mobileMenuToggle.addEventListener\("click"/);
  assert.match(js,/mobileMenuBackdrop.addEventListener\("click"/);
  assert.match(js,/event.key==="Escape"/);
  assert.match(js,/setMobileMenuOpen\(false,true\)/);
  assert.match(js,/mobileMenuMedia.addEventListener\("change"/);
  assert.match(js,/if\(visible\)setProfileOpen\(false\)/);
  assert.match(js,/if\(mobileMenuToggle.getAttribute\("aria-expanded"\)==="true"\)setMobileMenuOpen\(false\)/);
});
test("no new network, posting or auth integrations",()=>{
  assert.doesNotMatch(html,/api\.openai\.com|api\.x\.com/);
  assert.doesNotMatch(css,/api\.openai\.com|api\.x\.com/);
});
