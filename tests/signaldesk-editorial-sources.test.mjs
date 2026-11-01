import test from "node:test";
import assert from "node:assert/strict";
import requested from "../config/editorial-sources.json" with {type:"json"};
import feeds from "../config/sources.json" with {type:"json"};
import extra from "../config/extra-news-sources.json" with {type:"json"};
import {selectStories,selectIndiaStories,parseFeed} from "../news-collector/worker.mjs";
import {renderSourceCatalogue} from "../dashboard/editorial-sources.mjs";
import {readFileSync} from "node:fs";
const NOW=Date.parse("2026-10-30T12:00:00Z");
const article=(i,region,category="markets",publisher="Pub")=>({
  title:"Publisher reports business policy update number "+i+" in region",
  source_url:"https://publisher.example/story/"+region+"/"+i,
  publisher,region,category,
  published_at:new Date(NOW-i*30000).toISOString(),
  source_preview:"Original article preview"
});
test("all 8 Global and 11 India requested publishers appear exactly once, with working links",()=>{
  assert.equal(requested.length,19);
  assert.equal(requested.filter(x=>x.group==="global").length,8);
  assert.equal(requested.filter(x=>x.group==="india").length,11);
  const sites=new Set();
  for(const item of requested){
    assert.equal(typeof item.name,"string");
    assert.equal(new URL(item.site).protocol,"https:");
    assert.ok(["attributed_cc_by_3","permission_required","rights_review",
      "feed_not_confirmed","no_official_rss"].includes(item.status),item.name);
    assert.ok(!sites.has(item.group+":"+item.name));
    sites.add(item.group+":"+item.name);
  }
  assert.equal(typeof renderSourceCatalogue,"function");
});
test("public collector does not silently fetch denied sources",()=>{
  assert.equal(feeds.length,18);
  assert.equal(extra.length,3);
  assert.equal(extra.filter(x=>x.source_type==="official_primary").length,2);
  assert.ok(extra.some(x=>x.name==="Alt News Fact Checks"&&x.region==="india"&&
    x.category==="factcheck"&&x.disable_images===true));
  const official=extra.filter(x=>x.source_type==="official_primary");
  assert.deepEqual(official.map(x=>x.region).sort(),["global","india"]);
  for(const source of official){
    assert.equal(source.disable_images,true);
    assert.match(source.policy_url,/^https:\/\//);
    assert.match(source.attribution,/official|Official/);
  }
  for(const restricted of requested.filter(x=>x.status==="permission_required"&&x.feed)){
    assert.ok(![...feeds,...extra].some(f=>f.url===restricted.feed),restricted.name);
  }
});
test("global and India selection are separate and max out at 50 articles each",()=>{
  const global=Array.from({length:90},(_,i)=>article(i,"global","markets","G"+i%13));
  const india=Array.from({length:90},(_,i)=>article(i+100,"india","policy","I"+i%13));
  const mixed=[...global,...india];
  const g=selectStories(mixed),n=selectIndiaStories(mixed);
  assert.equal(g.length,50);
  assert.equal(n.length,50);
  assert.ok(g.every(s=>s.region==="global"));
  assert.ok(n.every(s=>s.region==="india"));
  assert.equal(new Set([...g,...n].map(s=>s.source_url)).size,100);
});
test("fact check is labelled separately and never carries uncontrolled RSS images",()=>{
  const xml='<rss><channel><item>'+
    '<title>Fact check: India policy misinformation about finance reform</title>'+
    '<link>https://www.altnews.in/article/</link>'+
    '<pubDate>Fri, 30 Oct 2026 11:45:00 GMT</pubDate>'+
    '<media:thumbnail url="https://third-party.example/photo.jpg" />'+
    '</item></channel></rss>';
  const actual=parseFeed(xml,extra.find(x=>x.name==="Alt News Fact Checks"),NOW);
  assert.equal(actual.length,1);
  assert.equal(actual[0].category,"factcheck");
  assert.equal(actual[0].region,"india");
  assert.equal(actual[0].image_url,"");
});
test("source catalogue is bundled locally and never calls third-party feed URLs from browser",()=>{
  const app=readFileSync(new URL("../dashboard/app.js",import.meta.url),"utf8");
  const source=readFileSync(new URL("../dashboard/editorial-sources.mjs",import.meta.url),"utf8");
  const exportPy=readFileSync(new URL("../newsbot/dashboard_export.py",import.meta.url),"utf8");
  assert.match(app,/initializeSourceCatalogue/);
  assert.match(source,/editorial-sources.json/);
  assert.doesNotMatch(source,/news\.google\.com|\/rss\/search|cloudflare\.workers\.dev/);
  assert.match(exportPy,/config" \/ "editorial-sources.json"/);
});
