import test from "node:test";
import assert from "node:assert/strict";
import {supplementLiveNews} from "../dashboard/news-snapshot.mjs";
const NOW=Date.parse("2026-11-01T12:00:00Z");
const story=(id,region="india",hours=4,publisher="India News")=>({
  id,title:`Original published event ${id} changes new banking policy measures`,
  publisher,region,source_url:`https://news.example.org/story/${id}`,
  published_at:new Date(NOW-hours*3600_000).toISOString(),
  image_url:"",category:"markets",status:"unverified"
});
const snap=(news=[],india_news=[])=>({schema_version:1,news,india_news,drafts:[],
  generated_at:new Date(NOW-60_000).toISOString(),warnings:[]});
test("live cannot erase dated daily India and Global previews",()=>{
  const live=snap([story("global-live","global")],[story("india-live")]);
  const daily=snap([story("global-daily","global")],[story("india-daily","india",69)]);
  const {data,dailyAdditions}=supplementLiveNews(daily,live,NOW);
  assert.deepEqual(data.news.map(x=>x.id),["global-live","global-daily"]);
  assert.deepEqual(data.india_news.map(x=>x.id),["india-live","india-daily"]);
  assert.deepEqual(dailyAdditions,{global:1,india:1});
  assert.equal(data.generated_at,live.generated_at);
  assert.equal(live.india_news.length,1);
});
test("stale, future, cross-region and insecure daily stories never slip in",()=>{
  const daily=snap([],[story("allowed","india",71),story("stale","india",73),
    story("world","global"),{...story("bad"),source_url:"http://example.org"},
    story("future","india",-1)]);
  const {data}=supplementLiveNews(daily,snap(),NOW);
  assert.deepEqual(data.india_news.map(x=>x.id),["allowed"]);
});
test("removes repeated URLs and near duplicate titles, keeping distinct reporting",()=>{
  const main=story("live");
  const tracked={...story("copy"),source_url:main.source_url+"?utm_source=rss#content"};
  const duplicate={...story("duplicate"),title:main.title};
  const {data,dailyAdditions}=supplementLiveNews(snap([],[tracked,duplicate,story("new-27")]),snap([],[main]),NOW);
  assert.deepEqual(data.india_news.map(x=>x.id),["live","new-27"]);
  assert.equal(dailyAdditions.india,1);
});
test("respects region caps: Global seven, India eight per publisher, fifty overall",()=>{
  const daily=snap(Array.from({length:60},(_,i)=>story("G"+i,"global",4,"One publisher")),
    Array.from({length:60},(_,i)=>story("I"+i,"india",4,"One publisher")));
  const r=supplementLiveNews(daily,snap(),NOW);
  assert.equal(r.data.news.length,7);
  assert.equal(r.data.india_news.length,8);
  const diverse=Array.from({length:60},(_,i)=>story("M"+i,"india",4,"Publisher "+i));
  assert.equal(supplementLiveNews(snap([],diverse),snap(),NOW).data.india_news.length,50);
});
test("leaves expired supplemental headlines out without changing live draft fields",()=>{
  const live=snap([story("G","global")],[story("I")]);
  const result=supplementLiveNews(snap([story("old","global",40)],[story("stale","india",80)]),live,NOW);
  assert.deepEqual(result.data.news.map(x=>x.id),["G"]);
  assert.deepEqual(result.data.india_news.map(x=>x.id),["I"]);
  assert.deepEqual(result.dailyAdditions,{global:0,india:0});
  assert.equal(result.data.drafts,live.drafts);
});
