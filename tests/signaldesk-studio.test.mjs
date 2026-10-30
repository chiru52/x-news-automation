import test from "node:test";
import assert from "node:assert/strict";
import {postStarters, researchGuide, draftFromNotes, threadOutline, reviewThread, safeArticleUrl, approximateXCharacters, VALID_TONES} from "../dashboard/studio.mjs";

const base = {
  title: "OpenAI launches a new developer tool",
  source_url: "https://example.com/news/tool?utm_source=rss",
  publisher: "Example Publisher",
  category: "technology"
};

test("five distinct headline-attributed writing starters, no network or API", () => {
  const variants = postStarters(base);
  assert.deepEqual(variants.map(x => x.tone), [...VALID_TONES]);
  for (const variant of variants) {
    assert.ok(variant.text.includes(base.source_url));
    assert.ok(variant.text.includes(base.title));
    assert.ok(approximateXCharacters(variant.text) <= 280);
    assert.ok(variant.label.length > 0);
  }
  assert.ok(variants.find(x => x.tone === "analytical").text.includes("What changes"));
  assert.ok(variants.find(x => x.tone === "discussion").text.includes("What do you think"));
  assert.ok(variants.find(x=>x.tone==="factual").text.includes("Publisher: Example Publisher"));
});

test("human funding drafts paraphrase only the stated amount and round", () => {
  const story = {
    title:"ALPHA10X Raises $5M Pre-Series A",
    category:"saas", publisher:"The SaaS News",
    source_url:"https://www.thesaasnews.com/news/alpha10x-raises-5m"
  };
  const variants = postStarters(story);
  for (const variant of variants) {
    assert.match(variant.text, /ALPHA10X reportedly raised \$5M in a Pre-Series A round/);
    assert.ok(variant.text.endsWith(story.source_url));
    assert.doesNotMatch(variant.text, /Read at |In the news:|Reported by /);
    assert.ok(approximateXCharacters(variant.text) <= 280);
  }
  assert.match(variants[0].text, /curious where the team/);
  assert.match(variants[2].text, /capital/);
});

test("market predictions stay questions instead of guaranteed results", () => {
  const story = {...base, category:"markets",
    title:"Stock Market: Will S&P 500 Open Up or Down Today?"};
  const variants = postStarters(story);
  for (const variant of variants) {
    assert.ok(variant.text.includes("Will S&P 500 Open Up or Down Today?"));
    assert.doesNotMatch(variant.text, /definitely rises|will open higher|buy now/i);
  }
  assert.match(variants[0].text, /latest numbers/);
});

test("earnings context is observational, not invented financial figures", () => {
  const variants = postStarters({...base, category:"markets",
    title:"Tech firms take fresh hit as earnings misses fan AI fears"});
  assert.ok(variants[0].text.includes("actual results"));
  assert.ok(variants[2].text.includes("underlying earnings figures"));
  assert.ok(!variants[0].text.includes("$10 billion"));
});

test("newly written starters never claim unverified outcomes or fake AI generation", () => {
  const variants = postStarters(base);
  const text = variants.map(v=>v.text).join("\n");
  assert.doesNotMatch(text, /\b(proves|guaranteed|will revolutionize|fact.checked|AI generated)\b/i);
  assert.doesNotMatch(text, /api\.x\.com|api\.openai\.com/i);
});

test("conservative X length preserves source URL even with long headline", () => {
  const long = {...base,title:"New enterprise AI platform update ".repeat(25)};
  const variants = postStarters(long);
  assert.equal(variants.length, 5);
  for (const item of variants) {
    assert.ok(item.text.endsWith(base.source_url));
    assert.ok(approximateXCharacters(item.text) <= 280);
  }
});

test("unsafe URLs are rejected; no usable source means no new claim", () => {
  for (const url of ["javascript:alert(1)", "http://news.example/article",
    "https://user:pass@example.com", "//example.com", "not a url"]) {
    assert.equal(safeArticleUrl(url), "");
    assert.deepEqual(postStarters({...base,source_url:url}), []);
  }
});

test("research guide is limited to existing public publisher headline", () => {
  const guide = researchGuide(base);
  assert.equal(guide.heading, base.title);
  assert.equal(guide.publisher, base.publisher);
  assert.equal(guide.source_url, base.source_url);
  assert.equal(guide.questions.length, 3);
  assert.match(guide.evidence, /Headline and original link only/);
  assert.match(guide.caution, /can omit qualifications/);
  assert.ok(guide.questions.every(question => question.includes("?")));
  assert.ok(guide.next.includes("Open the original article"));
});

test("category-specific questions, no claims inferred from unseen body", () => {
  const market = researchGuide({...base,category:"markets"});
  const saas = researchGuide({...base,category:"saas"});
  assert.notDeepEqual(market.questions,saas.questions);
  assert.ok(market.questions.some(q=>q.includes("prediction")));
  assert.ok(saas.questions.some(q=>q.includes("pricing")));
});

test("RSS context is visibly attributed, not full article research or AI", () => {
  const guide = researchGuide({...base, kind:"news", context_status:"rss_preview",
    source_preview:"The publisher's feed says the launch is expected in November with a $5M budget."});
  assert.match(guide.preview_label,/RSS preview.*unverified/);
  assert.match(guide.evidence,/not checked against full article/);
  assert.match(guide.preview,/expected in November/);
  assert.ok(guide.questions.some(q=>q.includes("$5M")));
  assert.ok(guide.questions.some(q=>q.includes("forecast, possibility")));
  assert.equal(guide.source_url, base.source_url);
});

test("missing or malformed feed context fails back to headline-only", () => {
  for (const data of [
    {...base, kind:"draft",context_status:"rss_preview",source_preview:"This is not RSS"},
    {...base, kind:"news",context_status:"full_article_verified",source_preview:"Do not display"},
    {...base, kind:"news",context_status:"rss_preview",source_preview:"x".repeat(171)}
  ]) {
    const guide=researchGuide(data);
    assert.equal(guide.preview, "");
    assert.match(guide.preview_label, /No additional RSS preview available/);
  }
});

test("research notes become a sourced, bounded, user-authored draft", () => {
  const draft=draftFromNotes("My reading: I'd check the original figures.",base.source_url);
  assert.match(draft,/My reading/);
  assert.ok(draft.endsWith(base.source_url));
  assert.ok(approximateXCharacters(draft) <= 280);
  assert.equal(draftFromNotes("",base.source_url),"");
  assert.equal(draftFromNotes("Claims","http://unsafe.example/a"),"");
  assert.ok(approximateXCharacters(draftFromNotes("A very long observation ".repeat(50),base.source_url)) <= 280);
});

test("source attribution is escaped through DOM textContent, not HTML injection", () => {
  const malicious = {...base,title:'<script>alert("oops")</script>'};
  const variants = postStarters(malicious);
  assert.ok(variants[0].text.includes('<script>'));
  // The client must use textContent to display this literal source string.
});


test("thread outline is three individually bounded source-grounded posts, not an auto-published thread",()=>{
  const parts=threadOutline(base);
  assert.equal(parts.length,3);
  assert.match(parts[0],/^1\/3/);
  assert.match(parts[1],/^2\/3/);
  assert.match(parts[2],/^3\/3/);
  assert.ok(parts[0].includes(base.title));
  assert.ok(parts[0].includes(base.publisher));
  assert.ok(parts[2].includes(base.source_url));
  for(const part of parts)assert.ok(approximateXCharacters(part)<=280);
  assert.deepEqual(reviewThread(parts,base.source_url),{
    valid:true,reason:"Ready to copy manually after reviewing the source."
  });
  assert.doesNotMatch(parts.join(" "),/\b(?:is confirmed|independently verified|guaranteed)\b/i);
});
test("thread questions adapt to markets, SaaS, and technology without invented article facts",()=>{
  const tech=threadOutline(base);
  const saas=threadOutline({...base,category:"saas"});
  const markets=threadOutline({...base,category:"markets"});
  assert.notEqual(tech[1],saas[1]);
  assert.notEqual(saas[1],markets[1]);
  assert.match(markets[1],/filings/);
  assert.match(saas[1],/customers/);
});
test("thread review rejects blank posts, overlong edits, missing source and unsafe link",()=>{
  const parts=threadOutline(base);
  assert.equal(reviewThread([],base.source_url).valid,false);
  assert.equal(reviewThread([parts[0],"",parts[2]],base.source_url).valid,false);
  assert.equal(reviewThread([parts[0],"X".repeat(300),parts[2]],base.source_url).valid,false);
  assert.equal(reviewThread([parts[0],parts[1],"3/3 My thoughts without any link"],base.source_url).valid,false);
  assert.equal(reviewThread(parts,"javascript:alert(1)").valid,false);
  assert.deepEqual(threadOutline({...base,source_url:"http://unsafe.example/article"}),[]);
});
test("long headlines are shortened without breaking source link or individual length checks",()=>{
  const long={...base,title:"AI software product announcement for enterprise developer teams ".repeat(24)};
  const parts=threadOutline(long);
  assert.equal(parts.length,3);
  assert.ok(parts[0].endsWith("…"));
  assert.ok(parts[2].includes(base.source_url));
  assert.ok(parts.every(part=>approximateXCharacters(part)<=280));
});
