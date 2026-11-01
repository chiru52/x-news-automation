import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync(new URL("../dashboard/index.html",import.meta.url),"utf8");
const css=readFileSync(new URL("../dashboard/styles.css",import.meta.url),"utf8");
const js=readFileSync(new URL("../dashboard/app.js",import.meta.url),"utf8");
const header=html.split('<header class="topbar">',2)[1]?.split("</header>",1)[0]||"";
const sidebar=html.split('<aside class="sidebar"',2)[1]?.split("</aside>",1)[0]||"";

test("mobile header places navigation before SignalDesk brand, with theme and profile on right",()=>{
  assert.equal((html.match(/id="mobile-menu-toggle"/g)||[]).length,1);
  const menu=header.indexOf('id="mobile-menu-toggle"');
  const brand=header.indexOf('class="mobile-brand"');
  const theme=header.indexOf('id="theme-toggle"');
  const profile=header.indexOf('id="profile-toggle"');
  assert.ok(menu>=0 && brand>menu && theme>brand && profile>theme);
  assert.match(header,/class="mobile-header-start"/);
  assert.ok(!sidebar.includes('id="mobile-menu-toggle"'));
  assert.match(header,/aria-controls="sidebar-menu" aria-expanded="false" aria-label="Open navigation menu"/);
  assert.match(html,/id="mobile-current-view"/);
  assert.match(header,/class="mobile-menu-hamburger"/);
  assert.match(header,/class="mobile-menu-close"/);
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
test("open menu switches hamburger to close icon without altering desktop header",()=>{
  assert.match(css,/\.mobile-header-start\{display:none\}/);
  assert.match(css,/@media\(max-width:850px\)\{\s*\.topbar \.mobile-header-start\{\s*display:flex/);
  assert.match(css,/\.topbar \.mobile-menu-toggle\[aria-expanded="true"\] \.mobile-menu-hamburger\{display:none\}/);
  assert.match(css,/\.topbar \.mobile-menu-toggle\[aria-expanded="true"\] \.mobile-menu-close\{display:block\}/);
  assert.match(css,/\.topbar \.mobile-menu-icon \.mobile-menu-close\{display:none\}/);
  assert.match(css,/\.sidebar \.nav-items\s*\{[^}]*left:0;right:auto;bottom:0;/);
  assert.match(css,/\.sidebar\.mobile-nav-open \.nav-items\{transform:translateX\(0\)/);
  assert.match(css,/\.topbar \.top-right\{margin-left:auto;flex-shrink:0\}/);
  assert.equal((header.match(/id="theme-toggle"/g)||[]).length,1);
  assert.equal((header.match(/id="profile-toggle"/g)||[]).length,1);
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
