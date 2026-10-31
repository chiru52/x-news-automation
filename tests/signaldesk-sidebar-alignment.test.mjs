import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const html=readFileSync(new URL("../dashboard/index.html",import.meta.url),"utf8");
const css=readFileSync(new URL("../dashboard/styles.css",import.meta.url),"utf8");

test("desktop sidebar and mobile header use one centered brand glyph",()=>{
  assert.equal((html.match(/class="brand-mark" aria-hidden="true">S<\/span>/g)||[]).length,2);
  assert.doesNotMatch(html,/brand-dot/);
  assert.match(css,/\.brand-mark\{[^}]*display:flex;align-items:center;justify-content:center;line-height:1;/);
  assert.match(css,/\.brand-mark::after\{[^}]*position:absolute;/);
  assert.match(css,/\.mobile-brand \.brand-mark\{width:31px;height:31px;/);
  assert.match(html,/class="brand" aria-label="SignalDesk home/);
  assert.match(html,/class="mobile-brand" href="\.\/" aria-label="SignalDesk home/);
});

test("safety icon has its own explicit centered layout, separate from text rules",()=>{
  assert.match(html,/class="safety-mini"><span class="safety-symbol">✓<\/span><div><strong>You stay in control<\/strong><span>Nothing is posted automatically\.<\/span>/);
  assert.match(css,/\.safety-mini\{[^}]*align-items:center;/);
  assert.match(css,/\.safety-mini>\.safety-symbol\{[^}]*display:grid;place-items:center;align-self:center;/);
  assert.match(css,/\.safety-mini>div>strong\{display:block;/);
  assert.match(css,/\.safety-mini>div>span\{display:block;/);
  assert.doesNotMatch(css,/\.safety-mini span\{/);
  assert.doesNotMatch(css,/\.safety-mini strong,\.safety-mini span/);
});

test("presentation fix does not introduce external services or X publishing",()=>{
  assert.doesNotMatch(html,/api\.openai\.com|api\.x\.com/);
  assert.doesNotMatch(css,/api\.openai\.com|api\.x\.com/);
});
