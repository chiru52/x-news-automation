import test from "node:test";
import assert from "node:assert/strict";
import {parseFeed,selectStories,selectIndiaStories,publicItem,collect,handleRequest,CRON} from "../news-collector/worker.mjs";
import configuredFeeds from "../config/sources.json" with {type:"json"};
import additionalFeeds from "../config/extra-news-sources.json" with {type:"json"};
const SOURCE_COUNT=configuredFeeds.length+additionalFeeds.length;

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
  for (const [categoryIndex,category] of ["technology","saas","markets"].entries()) {
    for (let feed=0;feed<5;feed++)
      for (let j=0;j<7;j++)
        stories.push(item(category+"-"+(categoryIndex*100+feed*7+j),category,"feed-"+category+"-"+feed));
  }
  const picks=selectStories(stories);
  assert.equal(picks.length,50);
  const tally=Object.fromEntries(["technology","saas","markets"].map(c=>[c,picks.filter(x=>x.category===c).length]));
  assert.deepEqual(tally,{technology:17,saas:17,markets:16});
  assert.ok(new Set(picks.map(x=>x.source_url)).size===50);
  assert.ok(Math.max(...Object.values(Object.groupBy(picks,x=>x.publisher)).map(x=>x.length))<=7);
});
test("India headlines can be classified by strong RSS preview context but not generic Indian publisher names",()=>{
  const indiaContext=rss("AI technology startup raises new software funding")
    .replace("The publisher says the new product launch is expected this year.",
             "An India-based startup plans enterprise software investments in local markets.");
  assert.equal(parseFeed(indiaContext,source,NOW)[0].region,"india");
  const unrelated=parseFeed(rss("Microsoft unveils developer software for global cloud customers"),
    {name:"YourStory India",category:"technology",url:"https://yourstory.com/feed"},NOW);
  assert.equal(unrelated[0].region,"global");
});
test("collector conservatively removes cross-publisher duplicates without hiding different facts",()=>{
  const headline="OpenAI launches enterprise AI coding assistant for developer teams";
  const basic={...item("base"),title:headline};
  const matched={...item("other"),title:headline+" today",publisher:"Other Publisher"};
  const numbers={...item("different"),title:"OpenAI raises $20 million for developer tools software expansion"};
  const numbers2={...item("amount"),title:"OpenAI raises $25 million for developer tools software expansion",publisher:"Other Publisher"};
  const picks=selectStories([basic,matched,numbers,numbers2]);
  assert.equal(picks.length,3);
});
test("India-specific finance headline terms qualify without generic market words",()=>{
  const india=parseFeed(rss("RBI updates Nifty and Sensex index rules"),source,NOW);
  assert.equal(india.length,1);
  assert.equal(india[0].region,"india");
});
test("India feed is distinct and conservative about regional relevance",()=>{
  const india=[
    {...item("bengaluru-1","saas","Inc42 India Startups"),region:"india",
      title:"AI startup announces enterprise funding in Bengaluru"},
    {...item("mumbai-2","markets","Market Publisher"),region:"global",
      title:"RBI updates technology guidelines for Indian banks"},
    {...item("international","saas","YourStory India"),region:"global",
      title:"Global software company discusses international launch"},
    {...item("india-3","saas","ET Entrepreneur India Startups"),region:"india",
      title:"Startup receives new enterprise investment"},
  ];
  const picked=selectIndiaStories(india);
  assert.equal(picked.length,3);
  assert.ok(picked.every(x=>x.region==="india" || /India|Indian|Bengaluru|RBI/i.test(x.title)));
  assert.ok(picked.every(x=>x.title!=="Global software company discusses international launch"));
});
test("India-specific source flag and headline classification are reflected in public cards",async()=>{
  const regional=await publicItem({...item("funding","saas","Inc42 India Startups"),region:"india",
    title:"Startup raises seed funding for fintech product"});
  const global=await publicItem({...item("global","technology","BBC Technology"),region:"global",
    title:"International AI technology company launches new software"});
  assert.equal(regional.region,"india");
  assert.equal(global.region,"global");
  assert.equal(regional.status,"unverified");
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
  assert.equal(card.trend_reason,"Recent headline about a reported development");
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
  assert.ok(network>0 && network<=24);
  const r=await handleRequest(new Request("https://feed.example/feed"),{NEWS_CACHE:kv});
  assert.equal(r.status,503);
  assert.equal(network,SOURCE_COUNT);
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
  assert.equal(out.ok,true,JSON.stringify(out));
  assert.ok(out.count>=5 && out.count<=50);
  assert.equal(calls.filter(x=>x==="put").length,2); // one live snapshot and one daily archive bucket
  const r=await handleRequest(new Request("https://feed.example/feed"),{NEWS_CACHE:kv});
  assert.equal(r.status,200);
  const data=await r.json();
  assert.equal(data.schema_version,1);
  assert.deepEqual(data.drafts,[]);
  assert.ok(Array.isArray(data.india_news));
  assert.ok(data.india_news.length<=50);
  assert.equal(data.news.length,out.count);
  assert.equal(calls.filter(x=>x==="get").length,2); // archive merge read and visitor live feed read
  assert.equal(counter,SOURCE_COUNT); // One Cron fetch per configured publisher; visitors never do.
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

test("India-specific RBI regulatory context in RSS summary qualifies but generic tech does not",()=>{
  const india=rss("AI software company updates enterprise product")
    .replace("The publisher says the new product launch is expected this year.",
      "RBI updates are expected to influence software developers and banking technology.");
  assert.equal(parseFeed(india,source,NOW)[0].region,"india");
  const generic=rss("AI software company updates enterprise product");
  assert.equal(parseFeed(generic,source,NOW)[0].region,"global");
});

test("headline-only official RBI source never redistributes RSS summaries or photos",()=>{
  const xml='<?xml version="1.0"?><rss><channel><item>'+
    '<title>Reserve Bank announces new banking policy in India</title>'+
    '<link>https://www.rbi.org.in/test-official-announcement</link>'+
    '<pubDate>'+new Date(NOW-3*60*60000).toUTCString()+'</pubDate>'+
    '<description>Publisher summary content that must not be redistributed</description>'+
    '</item></channel></rss>';
  const feed={name:"Reserve Bank of India (official press releases)",
    url:"https://www.rbi.org.in/pressreleases_rss.xml",
    category:"markets",region:"india",disable_images:true,headline_only:true};
  const data=parseFeed(xml,feed,NOW);
  assert.equal(data.length,1);
  assert.equal(data[0].source_preview,"");
  assert.equal(data[0].image_url,"");
  assert.equal(data[0].region,"india");
});

test("India live RSS accepts 36–72h dated stories without loosening Global recency",()=>{
  const fiftyHours=new Date(NOW-50*3600000).toUTCString();
  const seventyThreeHours=new Date(NOW-73*3600000).toUTCString();
  const pib=additionalFeeds.find(feed=>feed.name.startsWith("Press Information Bureau"));
  assert.ok(pib && pib.region==="india" && pib.headline_only===true && pib.disable_images===true);
  const official=parseFeed(rss("India government announces new banking technology policy",fiftyHours),pib,NOW);
  assert.equal(official.length,1);
  assert.equal(official[0].region,"india");
  assert.equal(official[0].source_preview,"");
  assert.equal(official[0].image_url,"");
  assert.equal(parseFeed(rss("India government announces new banking technology policy",seventyThreeHours),pib,NOW).length,0);
  assert.equal(parseFeed(rss("Global software firm announces major technology launch",fiftyHours),source,NOW).length,0);
  const crossBorder=parseFeed(rss("India startup launches new AI enterprise technology",fiftyHours),source,NOW);
  assert.equal(crossBorder.length,1);
  assert.equal(crossBorder[0].region,"india");
});
