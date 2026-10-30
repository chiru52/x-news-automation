import test from "node:test";
import assert from "node:assert/strict";
import {
  archiveDates, validHistoryDate, historyKey, mergeDailyArchive,
  historyParams, queryArchive, ARCHIVE_TTL_SECONDS
} from "../news-collector/archive.mjs";
import {archiveEndpoint,archiveQuery,archiveResponse} from "../dashboard/archive-client.mjs";
import {handleRequest} from "../news-collector/worker.mjs";

const NOW=Date.parse("2026-10-30T12:00:00Z");
const item=(id,region="global",publisher="Example Publisher",category="technology",timestamp=NOW)=>({
  id:id.toString(16).padStart(24,"0"),title:"New AI product launch "+id,
  source_url:"https://publisher.example/articles/"+id,
  publisher,region,category,published_at:new Date(timestamp).toISOString(),
  description:"Publisher report. Verify all claims before sharing.",
  source_preview:"This public RSS description mentions product and business context.",
  context_status:"rss_preview",status:"unverified",
  trend_score:80,coverage_feeds:1,trend_reason:"Relevant public headline",
  post:"Read this public announcement https://publisher.example/articles/"+id
});
test("30-day UTC date ranges are strict; no future or outside-retention data",()=>{
  assert.deepEqual(archiveDates(NOW,7).slice(0,2),["2026-10-30","2026-10-29"]);
  assert.equal(archiveDates(NOW,30).length,30);
  assert.equal(archiveDates(NOW,30).at(-1),"2026-10-01");
  for(const d of ["2026-09-30","2026-10-31","2026-02-30","bad", "2026-10-1"]){
    assert.equal(validHistoryDate(d,NOW),false,d);
  }
  assert.equal(validHistoryDate("2026-10-01",NOW),true);
  assert.equal(historyKey("2026-10-30"),"signaldesk:news:archive:v1:2026-10-30");
  assert.ok(ARCHIVE_TTL_SECONDS>=31*86400);
});
test("daily bucket merges new snapshots, deduplicates, respects 120-item cap",()=>{
  const old=mergeDailyArchive(null,[item(1),item(2)],NOW);
  const next=mergeDailyArchive(old,[item(2),item(3)],NOW+1000);
  assert.equal(next.items.length,3);
  assert.deepEqual(new Set(next.items.map(x=>x.source_url)).size,3);
  assert.deepEqual(next.items.map(x=>x.id),[item(2).id,item(3).id,item(1).id]);
  assert.equal(next.date,"2026-10-30");
  assert.equal(mergeDailyArchive(old,[item(10)],NOW+86400000).items.length,1);
  const many=mergeDailyArchive(null,Array.from({length:200},(_,i)=>item(100+i)),NOW);
  assert.equal(many.items.length,120);
  assert.ok(many.items.every(x=>x.status==="unverified"));
});
test("public RSS only, malformed/private-looking article entries rejected",()=>{
  const valid=item(1),bad={...valid,id:"owner@secret"},paid={...valid,status:"private"};
  const data=mergeDailyArchive(null,[bad,paid,{...valid,source_url:"http://unsafe"},valid],NOW);
  assert.equal(data.items.length,1);
  assert.equal(data.items[0].source_url,valid.source_url);
});
test("query validates exact date, filters, pagination and unknown params",()=>{
  const valid=new URL("https://worker.example/archive?days=30&region=india&q=AI&page=2");
  const p=historyParams(valid,NOW);
  assert.equal(p.dates.length,30);
  assert.equal(p.region,"india");
  assert.equal(p.page,2);
  assert.equal(p.q,"ai");
  for (const query of ["?days=31","?page=-1","?page=60","?region=us","?date=2026-10-31","?date=2026-09-29","?secret=token","?category=all&category=saas"]) {
    assert.equal(historyParams(new URL("https://worker.example/archive"+query),NOW),null,query);
  }
});
test("archive search is across buckets with region, keyword, publisher and paging",()=>{
  const buckets=[
    mergeDailyArchive(null,[item(1,"india","India Publisher"),item(2,"global","Global Publisher")],NOW),
    mergeDailyArchive(null,[item(3,"india","India Publisher","markets",NOW-86400000),item(2)],NOW-86400000)
  ];
  const params=historyParams(new URL("https://worker.example/archive?days=7&region=india&publisher=India%20Publisher&q=launch"),NOW);
  const out=queryArchive(buckets,params);
  assert.equal(out.total,2);
  assert.deepEqual(out.news.map(x=>x.id),[item(1).id,item(3).id]);
  assert.equal(out.available_days,2);
  assert.deepEqual(out.publishers,["Example Publisher","Global Publisher","India Publisher"]);
  assert.equal(out.archive,true);
  const none=queryArchive(buckets,{...params,q:"not present"});
  assert.equal(none.total,0);
  const large=mergeDailyArchive(null,Array.from({length:120},(_,i)=>item(200+i)),NOW);
  const pages=historyParams(new URL("https://worker.example/archive?days=7&page=1"),NOW);
  const paged=queryArchive([large],pages);
  assert.equal(paged.news.length,60);
  assert.equal(paged.total,120);
  assert.equal(paged.has_more,false);
});
test("read-only Worker /archive uses KV-only reads and rejects POST",async()=>{
  const data=mergeDailyArchive(null,[item(1,"india"),item(2)],Date.now());
  const store=new Map([[historyKey(data.date),JSON.stringify(data)]]);
  const operations=[];
  const env={NEWS_CACHE:{
    get:async(key,type)=>{operations.push(["get",key,type]);return JSON.parse(store.get(key)||"null");},
    put:async()=>{throw Error("archive GET must never write");}
  }};
  const nowDate=data.date;
  const resp=await handleRequest(new Request("https://feed.example/archive?date="+nowDate+"&region=india"),env);
  assert.equal(resp.status,200);
  const out=await resp.json();
  assert.equal(out.total,1);
  assert.equal(out.news[0].region,"india");
  assert.equal(operations.length,1);
  assert.equal(operations[0][1],historyKey(nowDate));
  assert.equal((await handleRequest(new Request("https://feed.example/archive",{method:"POST"}),env)).status,405);
  assert.equal((await handleRequest(new Request("https://feed.example/archive?days=31"),env)).status,400);
});
test("empty archive is honest about history starting now, not fabricated backfill",async()=>{
  const env={NEWS_CACHE:{get:async()=>null}};
  const out=await handleRequest(new Request("https://feed.example/archive?days=7"),env);
  assert.equal(out.status,200);
  const doc=await out.json();
  assert.equal(doc.available_days,0);
  assert.equal(doc.total,0);
  assert.deepEqual(doc.news,[]);
});
test("browser history endpoint is pinned and queries are GET-only",()=>{
  const feed="https://signaldesk-news-feed.littlekingchess.workers.dev/feed";
  const url=archiveEndpoint(feed);
  assert.equal(url,feed.replace("/feed","/archive"));
  assert.equal(archiveEndpoint("http://signaldesk-news-feed.foo.workers.dev/feed"),"");
  assert.equal(archiveEndpoint("https://attacker.example/feed"),"");
  const query=archiveQuery(url,{days:30,date:null,region:"india",publisher:"India Publisher",
    category:"saas",q:"startup funding",page:1});
  const parsed=new URL(query);
  assert.equal(parsed.searchParams.get("days"),"30");
  assert.equal(parsed.searchParams.get("q"),"startup funding");
  assert.equal(parsed.searchParams.get("region"),"india");
  assert.equal(parsed.searchParams.get("page"),"1");
  assert.equal(archiveQuery(url,{days:100,date:null,region:"all",publisher:"",category:"all",q:"",page:0}),"");
  assert.equal(archiveResponse({schema_version:1,archive:true,news:[],publishers:[],total:0,page:0,has_more:false}),true);
  assert.equal(archiveResponse({schema_version:1,archive:true,news:Array(61).fill({}),publishers:[],total:61,page:0,has_more:true}),false);
});
