import test from "node:test";
import assert from "node:assert/strict";
import {parseFeed,selectStories,publicItem,collect,handleRequest,CRON} from "../news-collector/worker.mjs";

const NOW=new Date("2026-10-30T12:00:00Z").getTime();
const source={name:"Example Technology",category:"technology",url:"https://publisher.example/feed"};
const item=(n,category="technology",publisher="Publisher")=>({
  title:"New AI technology software company launch "+n,
  source_url:"https://publisher.example/story/"+n,
  published_at:new Date(NOW-15*60*1000).toISOString(),
  source_preview:"Publisher RSS feed preview about a new company announcement with additional background.",
  publisher,category
});
function rss(name, date=new Date(NOW-20*60000).toUTCString()) {
  return '<?xml version="1.0"?><rss><channel><item>'+
    '<title>'+name+'</title><link>https://publisher.example/story?utm_source=feed</link>'+
    '<pubDate>'+date+'</pubDate>'+
    '<description><![CDATA[<p>The publisher says the new product launch is expected this year.</p>]]></description>'+
    '</item></channel></rss>';
}
function atom(name){
  return '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>'+
    '<title>'+name+'</title><link rel="alternate" href="https://publisher.example/atom"/>'+
    '<updated>'+new Date(NOW).toISOString()+'</updated>'+
    '<summary>A software company has published a new enterprise product update.</summary>'+
    '</entry></feed>';
}
test("valid RSS and Atom parse without visiting individual article pages",()=>{
  const news=parseFeed(rss("AI company launches developer software"),source,NOW);
  assert.equal(news.length,1);
  assert.equal(news[0].source_url,"https://publisher.example/story");
  assert.equal(news[0].publisher,source.name);
  assert.ok(news[0].source_preview.includes("new product launch"));
  const atomData=parseFeed(atom("AI technology company launches enterprise software"),source,NOW);
  assert.equal(atomData.length,1);
  assert.equal(atomData[0].source_url,"https://publisher.example/atom");
});
test("no old, future, spam, off-topic or unsafe article",()=>{
  assert.equal(parseFeed(rss("AI developer software launch",new Date(NOW-50*3600000).toUTCString()),source,NOW).length,0);
  assert.equal(parseFeed(rss("AI developer software launch",new Date(NOW+60*60000).toUTCString()),source,NOW).length,0);
  assert.equal(parseFeed(rss("Sponsored AI developer software launch"),source,NOW).length,0);
  assert.equal(parseFeed(rss("The weather is partly sunny"),source,NOW).length,0);
  const bad=rss("AI launch").replace("https://publisher.example/story?utm_source=feed","javascript:alert(1)");
  assert.equal(parseFeed(bad,source,NOW).length,0);
});
test("selection avoids duplicates, caps source and balances topics",()=>{
  const stories=[];
  for (const category of ["technology","saas","markets"]) {
    for (let feed=0;feed<5;feed++)
      for (let j=0;j<7;j++)
        stories.push(item(category+"-"+feed+"-"+j,category,"feed-"+category+"-"+feed));
  }
  const picks=selectStories(stories);
  assert.equal(picks.length,30);
  const tally=Object.fromEntries(["technology","saas","markets"].map(c=>[c,picks.filter(x=>x.category===c).length]));
  assert.deepEqual(tally,{technology:10,saas:10,markets:10});
  assert.ok(new Set(picks.map(x=>x.source_url)).size===30);
  assert.ok(Math.max(...Object.values(Object.groupBy(picks,x=>x.publisher)).map(x=>x.length))<=4);
});
test("public item schema matches original dashboard contract and X manual-only",async()=>{
  const card=await publicItem(item("good"));
  assert.match(card.id,/^[0-9a-f]{24}$/);
  assert.equal(card.status,"unverified");
  assert.equal(card.context_status,"rss_preview");
  assert.equal(card.coverage_feeds,1);
  assert.equal(card.category,"technology");
  assert.ok(card.post.includes(card.source_url));
  assert.ok(card.post.includes("I'm curious"));
  assert.ok(card.post.length<320);
  assert.equal(card.trend_reason,"Fresh headline about a reported development");
});
test("cron is the only thing fetching RSS; visitors only read cache",async()=>{
  assert.equal(CRON,"*/15 * * * *");
  const calls=[];
  const cache=new Map();
  const kv={put:async(k,v)=>{calls.push("write");cache.set(k,v);},get:async(k)=>{calls.push("read");return cache.get(k)||null;}};
  let network=0;
  const fetcher=async()=>{network++;return new Response(rss("AI technology company launches new developer product"),{status:200,headers:{"content-type":"application/rss+xml"}});};
  // Single identical RSS item from 14 configured feeds cannot pass minimum
  // threshold and never destroys the previous healthy shared snapshot.
  const first=await collect({NEWS_CACHE:kv},{fetcher,nowMs:NOW});
  assert.equal(first.ok,false);
  assert.equal(cache.size,0);
  assert.ok(network>0 && network<=20);
  const r=await handleRequest(new Request("https://feed.example/feed"),{NEWS_CACHE:kv});
  assert.equal(r.status,503);
  assert.equal(network,14);
});
test("collector stores one safe shared snapshot and reader never starts collection",async()=>{
  const cache=new Map();const calls=[];
  const kv={
    put:async(key,value)=>{calls.push("put");cache.set(key,value);},
    get:async key=>{calls.push("get");return cache.get(key)||null;}
  };
  let counter=0;
  const fetcher=async()=>{
    counter++;
    const stamp=new Date(Date.now()-60000).toUTCString();
    const multiple=Array.from({length:9},(_,i)=>'<item><title>AI technology software enterprise product launch '+counter+' '+i+'</title>'+
      '<link>https://publisher.example/'+counter+'/'+i+'</link><pubDate>'+stamp+'</pubDate>'+
      '<description>News about an enterprise software company product launch that needs checking.</description></item>').join("");
    return new Response("<rss><channel>"+multiple+"</channel></rss>",{status:200});
  };
  const out=await collect({NEWS_CACHE:kv},{fetcher,nowMs:Date.now()});
  assert.equal(out.ok,true);
  assert.ok(out.count>=5 && out.count<=30);
  assert.equal(calls.filter(x=>x==="put").length,1);
  const r=await handleRequest(new Request("https://feed.example/feed"),{NEWS_CACHE:kv});
  assert.equal(r.status,200);
  const data=await r.json();
  assert.equal(data.schema_version,1);
  assert.deepEqual(data.drafts,[]);
  assert.equal(data.news.length,out.count);
  assert.equal(calls.filter(x=>x==="get").length,1);
  assert.equal(counter,14); // Cron fetches once per publisher; visitor never does.
  assert.equal((await handleRequest(new Request("https://feed.example/health"),{NEWS_CACHE:kv})).status,200);
  assert.equal((await handleRequest(new Request("https://feed.example/feed",{method:"POST"}),{NEWS_CACHE:kv})).status,405);
});
test("stale cache and failed collection cannot overwrite usable last data",async()=>{
  let writes=0;
  const old={schema_version:1,generated_at:new Date(Date.now()-4*3600000).toISOString(),news:Array.from({length:6},(_,i)=>({id:String(i)})),drafts:[]};
  const kv={get:async()=>JSON.stringify(old),put:async()=>{writes++;}};
  const stale=await handleRequest(new Request("https://feed.example/feed"),{NEWS_CACHE:kv});
  assert.equal(stale.status,503);
  const result=await collect({NEWS_CACHE:kv},{fetcher:async()=>{throw Error("down");},nowMs:NOW});
  assert.equal(result.ok,false);
  assert.equal(writes,0);
});
