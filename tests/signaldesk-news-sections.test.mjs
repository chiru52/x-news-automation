import test from "node:test";
import assert from "node:assert/strict";
import {NEWS_VIEWS,isIndiaArticle,eligibleNews,topNews,newsInSection} from "../dashboard/news-sections.mjs";

const news=(id,title,region,score,source="publisher.example")=>({
  id:"news:"+id,kind:"news",title,region,
  publisher:"Public Publisher",source_url:"https://"+source+"/"+id,
  category:"technology",trend_score:score,published_at:"2026-10-30T09:30:00Z"
});
const stage=new Map();
const stageOf=item=>stage.get(item.id)||"new";
const key=url=>new URL(url).pathname;

test("the seven-menu model partitions a shared Global + India news pool",()=>{
  assert.deepEqual(NEWS_VIEWS,["all","trending","global","india"]);
  const globalA=news("a","Worldwide software release","global",95);
  const indiaB=news("b","RBI updates lending rules in India","india",96);
  const globalC=news("c","AI launch in Europe","global",85);
  const indiaD=news("d","Indian startup launches AI toolkit","india",91);
  const draft={...globalA,kind:"draft",id:"draft:a",title:"AI draft"};
  const duplicated={...indiaB, id:"news:other",region:"global",title:"Duplicate syndicated headline"};
  const copied=news("e","SEBI discusses financial technology","india",99);
  const archived=news("f","International enterprise acquisition","global",90);
  const history={...news("old","Indian historical headline","india",100),history_only:true};
  stage.set(copied.id,"copied");stage.set(archived.id,"archived");
  const pool=eligibleNews([globalA,indiaB,globalC,indiaD,draft,duplicated,copied,archived,history],stageOf,key);
  assert.equal(pool.length,4);
  assert.equal(newsInSection(pool,"all").length,4);
  assert.equal(newsInSection(pool,"global").length,2);
  assert.equal(newsInSection(pool,"india").length,2);
  const trending=topNews(pool,3);
  assert.equal(trending.length,3);
  assert.deepEqual(trending.map(x=>x.id),["news:b","news:a","news:d"]);
  assert.deepEqual(newsInSection(pool,"trending",trending).map(x=>x.id),["news:a","news:b","news:d"]);
  assert.equal(newsInSection(pool,"global").length+newsInSection(pool,"india").length,pool.length);
});

test("Trending selects high-signal India and global stories, not only a region",()=>{
  const data=[
    news("india","Indian AI startup raises funding","india",100),
    news("global","Global enterprise market news","global",99),
    news("third","Worldwide technology launch","global",98),
    news("fourth","RBI releases banking updates","india",97),
    news("fifth","Global earnings report","global",96),
    news("sixth","India stock markets update","india",30)
  ];
  const pool=eligibleNews(data,()=> "new",key);
  const picks=newsInSection(pool,"trending",topNews(pool,5));
  assert.equal(picks.length,5);
  assert.equal(picks.filter(isIndiaArticle).length,2);
  assert.equal(picks.filter(x=>!isIndiaArticle(x)).length,3);
  assert.equal(pool.length,6);
});

test("India labeling is about relevance, not nationality of generic publishers",()=>{
  assert.equal(isIndiaArticle(news("i","Nifty jumps after RBI policy","global",80)),true);
  assert.equal(isIndiaArticle(news("g","Global AI platform announces updates","global",80)),false);
  assert.equal(isIndiaArticle({...news("s","Startup company raises funding","global",80),publisher:"Inc42 India Startups"}),true);
  assert.equal(isIndiaArticle({...news("generic","Global SaaS firm expands in Europe","global",70),publisher:"YourStory India"}),false);
  assert.equal(isIndiaArticle({...news("foreign","US markets fall","india",50)}),true);
  assert.equal(isIndiaArticle({...news("d","Indian technology funding","india",50),kind:"draft"}),false);
});

test("Copied stories vanish from discovery while prepared drafts remain separate",()=>{
  const sample=[news("one","Indian markets update","india",83),news("two","Worldwide AI update","global",81),
    {...news("template","Prepared X draft","global",90),kind:"draft",id:"draft:template"}];
  const stages=new Map([["news:one","copied"]]);
  const available=eligibleNews(sample,x=>stages.get(x.id)||"new",key);
  assert.deepEqual(available.map(x=>x.id),["news:two"]);
  assert.equal(newsInSection(available,"global").length,1);
  assert.equal(newsInSection(available,"india").length,0);
  assert.equal(sample.filter(x=>x.kind==="draft").length,1);
});
