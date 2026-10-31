import test from "node:test";
import assert from "node:assert/strict";
import {handleRequest} from "../news-collector/worker.mjs";

const base="https://signaldesk-news-feed.littlekingchess.workers.dev";
const env={NEWS_CACHE:{get:async()=>null}};
const request=(path,origin,method="GET")=>new Request(base+path,{
  method,headers:origin?{Origin:origin}:{}
});
test("only exact approved production and preview origins receive access-control headers",async()=>{
  for(const origin of ["https://news.littlekingchess.com","https://signaldesk-preview.pages.dev"]){
    for(const path of ["/health","/feed","/archive"]){
      const response=await handleRequest(request(path,origin),env);
      assert.equal(response.headers.get("access-control-allow-origin"),origin);
      assert.equal(response.headers.get("vary"),"Origin");
      assert.equal(response.headers.get("access-control-allow-credentials"),null);
      assert.ok([200,503,400].includes(response.status));
    }
  }
});
test("unknown, malformed and spoofed origins never get wildcard CORS",async()=>{
  for(const origin of [
    "https://attacker.example",
    "https://signaldesk-preview.pages.dev.evil.example",
    "http://signaldesk-preview.pages.dev",
    "https://another.pages.dev",
    "null",
    undefined
  ]){
    const response=await handleRequest(request("/health",origin),env);
    assert.equal(response.status,200);
    assert.equal(response.headers.get("access-control-allow-origin"),null);
    assert.equal(response.headers.get("vary"),"Origin");
  }
});
test("no new methods, publishing, or collection on visitor GET",async()=>{
  let reads=0;
  const storage={NEWS_CACHE:{get:async()=>{reads++;return null;}}};
  const post=await handleRequest(request("/feed","https://signaldesk-preview.pages.dev","POST"),storage);
  assert.equal(post.status,405);
  assert.equal(reads,0);
  const get=await handleRequest(request("/feed","https://signaldesk-preview.pages.dev"),storage);
  assert.equal(get.status,503);
  assert.equal(reads,1);
  assert.equal(get.headers.get("access-control-allow-origin"),"https://signaldesk-preview.pages.dev");
});
test("HEAD responses have no body and retain allowed origin",async()=>{
  const r=await handleRequest(request("/health","https://signaldesk-preview.pages.dev","HEAD"),env);
  assert.equal(r.status,200);
  assert.equal(await r.text(),"");
  assert.equal(r.headers.get("access-control-allow-origin"),"https://signaldesk-preview.pages.dev");
});
