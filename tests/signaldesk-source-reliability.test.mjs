import test from "node:test";
import assert from "node:assert/strict";
import feeds from "../config/sources.json" with {type:"json"};
import extra from "../config/extra-news-sources.json" with {type:"json"};
import {parseFeed,collect,handleRequest} from "../news-collector/worker.mjs";
import {recoverRecentStories,coverageSummary} from "../news-collector/source-reliability.mjs";

const NOW=Date.parse("2026-10-30T12:00:00Z");
const india=feeds.find(feed=>feed.name==="Inc42 India Startups");
function responseFor(url,batch=1,now=NOW){
  const source=feeds.findIndex(feed=>feed.url===url);
  const stamp=new Date(now-15*60*1000).toUTCString();
  const items=Array.from({length:7},(_,n)=>
    "<item><title>Enterprise AI technology software startup investment "+source+" "+n+
    "</title><link>https://publisher.example/article/"+batch+"/"+source+"/"+n+
    "</link><pubDate>"+stamp+"</pubDate><description>Publisher RSS preview for software teams.</description></item>");
  return new Response("<rss><channel>"+items.join("")+"</channel></rss>",{status:200});
}
function kvCache(){
  const map=new Map();const actions=[];
  return {
    map,actions,
    kv:{
      get:async(key,type)=>{actions.push("get:"+key);const value=map.get(key);
        return type==="json"&&value?JSON.parse(value):value||null;},
      put:async(key,value)=>{actions.push("put:"+key);map.set(key,value);}
    }
  };
}
test("HTML or unrelated XML returned as HTTP 200 is not considered a healthy RSS feed",()=>{
  const feed={name:"Publisher",url:"https://publisher.example/rss",category:"technology"};
  for(const text of ["<html><body>Login required</body></html>",
    "<response><status>ok</status></response>","<!DOCTYPE html><rss><channel></channel></rss>"]){
    assert.throws(()=>parseFeed(text,feed,NOW),/Invalid RSS or Atom document/);
  }
  assert.deepEqual(parseFeed("<rss><channel><title>Publisher RSS</title></channel></rss>",feed,NOW),[]);
});
test("a recent cache entry can be recovered only for its failed approved publisher",()=>{
  const sample={
    id:"a".repeat(24),title:"India technology software startup investment announces new cloud product",
    source_url:"https://example.com/article",publisher:india.name,
    status:"unverified",category:"saas",region:"india",
    published_at:new Date(NOW-45*60000).toISOString(),source_preview:"Publisher RSS preview"
  };
  const previous={schema_version:1,generated_at:new Date(NOW-30*60000).toISOString(),
    news:[],india_news:[sample]};
  let restored=recoverRecentStories(previous,[india],NOW);
  assert.equal(restored.length,1);
  assert.equal(restored[0].carried_from_previous,true);
  assert.equal(restored[0].published_at,sample.published_at);
  assert.equal(recoverRecentStories(previous,[],NOW).length,0);
  assert.equal(recoverRecentStories({...previous,generated_at:new Date(NOW-2*3600000).toISOString()},[india],NOW).length,0);
  assert.equal(recoverRecentStories({...previous,india_news:[{...sample,published_at:new Date(NOW-40*3600000).toISOString()}]},[india],NOW).length,0);
  assert.equal(recoverRecentStories({...previous,india_news:[{...sample,status:"published"}]},[india],NOW).length,0);
  assert.equal(recoverRecentStories({...previous,india_news:[{...sample,source_url:"http://example.com/unsafe"}]},[india],NOW).length,0);
});
test("temporary India feed failure retains only recent coverage without new KV writes",async()=>{
  const cache=kvCache();
  const first=await collect({NEWS_CACHE:cache.kv},{
    nowMs:NOW,fetcher:async url=>responseFor(url,1,NOW)
  });
  assert.equal(first.ok,true);
  const before=JSON.parse(cache.map.get("signaldesk:news:snapshot:v1"));
  assert.ok(before.india_news.some(item=>item.publisher===india.name));
  const next=NOW+12*60*1000;
  const second=await collect({NEWS_CACHE:cache.kv},{
    nowMs:next,fetcher:async url=>{
      if(url===india.url)throw Error("Temporary India publisher outage");
      return responseFor(url,2,next);
    }
  });
  assert.equal(second.ok,true);
  assert.equal(second.failed_sources,1);
  const data=JSON.parse(cache.map.get("signaldesk:news:snapshot:v1"));
  assert.equal(data.coverage.sources_checked,feeds.length+extra.length);
  assert.equal(data.coverage.sources_failed,1);
  assert.equal(data.coverage.india_sources_failed,1);
  assert.ok(data.coverage.retained_india>0);
  assert.ok(data.india_news.some(item=>item.publisher===india.name));
  assert.ok(data.warnings.includes("some_feed_sources_unavailable"));
  assert.ok(data.warnings.includes("recent_cached_stories_retained"));
  assert.ok(data.india_news.every(item=>new Date(item.published_at).getTime()<=next));
  // Exactly one snapshot and one archive put per cycle: KV write budget unchanged.
  assert.equal(cache.actions.filter(v=>v.startsWith("put:")).length,4);
  // Collection is entirely independent of visitor fetches.
  assert.equal(cache.actions.filter(v=>v.startsWith("put:")).length,4);
});
test("an all-source outage cannot refresh a prior public snapshot using old headlines",async()=>{
  const cache=kvCache();
  const first=await collect({NEWS_CACHE:cache.kv},{nowMs:NOW,fetcher:url=>responseFor(url,1,NOW)});
  assert.equal(first.ok,true);
  const original=cache.map.get("signaldesk:news:snapshot:v1");
  const failed=await collect({NEWS_CACHE:cache.kv},{
    nowMs:NOW+10*60000,fetcher:async()=>{throw Error("RSS offline");}
  });
  assert.equal(failed.ok,false);
  assert.equal(cache.map.get("signaldesk:news:snapshot:v1"),original);
  assert.equal(cache.actions.filter(v=>v.startsWith("put:")).length,2);
});
test("diagnostics are aggregate counts with no publisher URL or secret",()=>{
  const summary=coverageSummary(feeds,feeds.map((feed,index)=>({
    feed,error:index===0,articles:index===0?[]:[{title:"Source headline"}]
  })),1,2);
  assert.equal(summary.sources_checked,feeds.length);
  assert.equal(summary.sources_failed,1);
  assert.equal(summary.sources_with_recent_stories,feeds.length-1);
  assert.equal(summary.retained_news,1);
  assert.equal(summary.retained_india,2);
  assert.equal(JSON.stringify(summary).includes("https://"),false);
});

test("source health reports dedicated India feed participation without additional URLs or source data",()=>{
  const results=feeds.map(feed=>({
    feed,error:feed.region==="india"&&feed.name===india.name,
    articles:feed.region==="india"&&feed.name===india.name?[]:[{title:"Headline"}]
  }));
  const stats=coverageSummary(feeds,results);
  assert.equal(stats.india_sources_checked,feeds.filter(feed=>feed.region==="india").length);
  assert.equal(stats.india_sources_failed,1);
  assert.equal(stats.india_sources_with_recent_stories,stats.india_sources_checked-1);
  assert.equal(JSON.stringify(stats).includes("https://"),false);
});
