import test from "node:test";
import assert from "node:assert/strict";
import {sameNewsEvent,editorialSignals,canonicalArticleUrl} from "../news-collector/intelligence.mjs";
import {nearIdenticalHeadlines,eligibleNews,newsInSection,topNews} from "../dashboard/news-sections.mjs";
const now=Date.parse("2026-10-30T12:00:00Z");
const title="OpenAI launches enterprise AI coding assistant for software developer teams";
const story=(t=title,publisher="BBC Technology",url="https://one.example/story",minutes=20)=>({
  title:t,publisher,source_url:url,category:"technology",published_at:new Date(now-minutes*60000).toISOString()
});
const candidate=story();
const echo=story("OpenAI launches enterprise AI coding assistant for software developer teams today",
  "The Verge Tech","https://two.example/another");
test("cross-publisher matching is strict and removes tracking duplicates",()=>{
  assert.equal(sameNewsEvent(candidate,echo),true);
  assert.equal(nearIdenticalHeadlines(candidate.title,echo.title),true);
  assert.equal(canonicalArticleUrl("https://one.example/story/?utm_source=rss#top"),candidate.source_url);
  assert.equal(sameNewsEvent(candidate,story(title,"BBC Technology",candidate.source_url+"?utm_campaign=a")),true);
});
test("different companies, numbers, and short generic headlines remain separate",()=>{
  const a=story("OpenAI raises $15 million for developer software product expansion");
  const b=story("OpenAI raises $20 million for developer software product expansion","The Verge Tech","https://two.example/20");
  assert.equal(sameNewsEvent(a,b),false);
  assert.equal(nearIdenticalHeadlines(a.title,b.title),false);
  assert.equal(sameNewsEvent(a,story("Anthropic raises $15 million for developer software product expansion","The Verge Tech","https://two.example/a")),false);
  assert.equal(sameNewsEvent(story("AI launch"),story("AI launch","Other","https://two.example/a")),false);
});
test("reordered numbers are distinct factual events, even if title vocabulary is identical",()=>{
  const original=story("OpenAI announces 10 percent and 20 percent software revenue figures");
  const changed=story("OpenAI announces 20 percent and 10 percent software revenue figures",
    "The Verge Tech","https://two.example/reordered");
  assert.equal(sameNewsEvent(original,changed),false);
  assert.equal(nearIdenticalHeadlines(original.title,changed.title),false);
});
test("publisher groups reflect owners, not number of RSS feeds",()=>{
  const a=story(title,"CNBC Markets","https://cnbc.com/a");
  const b=story(title,"CNBC Investing","https://cnbc.com/b");
  const c=story(title,"BBC Technology","https://bbc.co.uk/a");
  const signals=editorialSignals(a,[a,b,c],now);
  assert.equal(signals.coverage_feeds,2);
  assert.ok(signals.score>editorialSignals(a,[a,b],now).score);
  assert.match(signals.reason,/2 publisher groups/);
});
test("coverage never counts stale or future stories",()=>{
  const old=story(title,"The Verge Tech","https://verge.example/a",60*80);
  const future=story(title,"Ars Technica","https://ars.example/a",-120);
  assert.equal(editorialSignals(candidate,[candidate,old,future],now).coverage_feeds,1);
});
test("current concrete development outranks speculative headlines of same age",()=>{
  const real=story("OpenAI launches enterprise AI coding assistant for developers");
  const conjecture=story("OpenAI might launch enterprise AI coding assistant for developers");
  assert.ok(editorialSignals(real,[real],now).score>editorialSignals(conjecture,[conjecture],now).score);
});
test("global, India and trending share de-duplicated pool without mixing regions",()=>{
  const news=(o,i,region)=>({...o,id:"news:"+i,kind:"news",region,trend_score:80,index:0});
  const pool=[news(candidate,"a","global"),news(echo,"b","global"),
    news(story("RBI updates Nifty and Sensex settlement norms in India","ET Tech India","https://et.example/story"),"c","india")];
  const available=eligibleNews(pool,()=> "new",url=>new URL(url).href);
  assert.equal(available.length,2);
  assert.equal(newsInSection(available,"global").length,1);
  assert.equal(newsInSection(available,"india").length,1);
  assert.equal(newsInSection(available,"trending",topNews(available,2)).length,2);
});
