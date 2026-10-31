import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync(new URL("../dashboard/account.html",import.meta.url),"utf8");
const css=readFileSync(new URL("../dashboard/account-visual.css",import.meta.url),"utf8");
const auth=readFileSync(new URL("../dashboard/account.mjs",import.meta.url),"utf8");

test("account entry points and form wiring remain intact",()=>{
  for(const id of ["account-heading","account-intro","account-sign-in","account-sign-up",
    "account-recover","auth-status","auth-form","auth-name","auth-email","auth-password",
    "auth-submit","account-signed-in","profile-form","account-password-form","account-sign-out"])
    assert.equal((html.match(new RegExp('id="'+id+'"',"g"))||[]).length,1,"Missing or duplicate "+id);
  for(const route of ["#sign-in","#sign-up","#forgot"])
    assert.ok(html.includes('href="'+route+'"'),"Missing auth route "+route);
  assert.ok(html.includes('src="./account.mjs?v=96"'),"Keep original auth module wired");
  assert.ok(html.includes('href="./account-visual.css"'),"Load presentation-only stylesheet");
  assert.ok(auth.includes('const cleanMode=()=>["sign-in","sign-up","forgot","update-password"]'),
    "Preserve all authentication modes");
});
test("original right-side storytelling shows three illustrative product concepts",()=>{
  assert.equal((html.match(/class="visual-scene visual-scene--/g)||[]).length,3);
  assert.ok(html.includes('visual-scene--one'));
  assert.ok(html.includes('visual-scene--two'));
  assert.ok(html.includes('visual-scene--three'));
  assert.ok(html.includes('aria-hidden="true"'),"Decorative mock screens are hidden from assistive tech");
  assert.ok(html.includes("ILLUSTRATIVE PRODUCT PREVIEW"));
  assert.ok(html.includes("NO AUTO-POSTING"));
  assert.ok(html.includes("Find the signal."));
  assert.ok(html.includes("Find your angle."));
  assert.ok(html.includes("Your decision."));
  assert.ok(!/<(?:video|iframe|canvas)\b/i.test(html));
});
test("motion has CSS-only loops and reduced motion fallback",()=>{
  assert.ok(css.includes('@keyframes signaldesk-scene'));
  assert.ok(css.includes('@keyframes signaldesk-progress-one'));
  assert.ok(css.includes('@keyframes signaldesk-progress-two'));
  assert.ok(css.includes('@keyframes signaldesk-progress-three'));
  assert.ok(css.includes('@media(prefers-reduced-motion:reduce)'));
  assert.ok(css.includes('.visual-scene--one{opacity:1!important;visibility:visible!important}'));
  assert.ok(css.includes('@media(max-width:570px)'));
  assert.ok(!html.includes("api.openai.com"));
  assert.ok(!html.includes("api.x.com"));
  assert.ok(!html.includes("onclick="));
});
