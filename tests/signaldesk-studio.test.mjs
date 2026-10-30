import test from "node:test";
import assert from "node:assert/strict";
import {postStarters, researchGuide, safeArticleUrl, approximateXCharacters, VALID_TONES} from "../dashboard/studio.mjs";

const base = {
  title: "OpenAI launches a new developer tool",
  source_url: "https://example.com/news/tool?utm_source=rss",
  publisher: "Example Publisher",
  category: "technology"
};

test("four distinct headline-attributed writing starters, no network or API", () => {
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
  assert.equal(variants.length, 4);
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
  assert.match(guide.evidence, /No full-text article analysis/);
  assert.match(guide.caution, /not an independently verified fact/);
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

test("source attribution is escaped through DOM textContent, not HTML injection", () => {
  const malicious = {...base,title:'<script>alert("oops")</script>'};
  const variants = postStarters(malicious);
  assert.ok(variants[0].text.includes('<script>'));
  // The client must use textContent to display this literal source string.
});
