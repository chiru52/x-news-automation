import test from "node:test";
import assert from "node:assert/strict";
import {requestAiDrafts} from "../dashboard/ai-writer-client.mjs";

test("browser AI client makes exactly one explicitly authorized same-origin POST",async()=>{
  const original=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async (url,options)=>{
    calls.push({url,options});
    return new Response(JSON.stringify({drafts:["Draft one","Draft two","Draft three"],verified:false,publication_authorized:false}),
      {status:200,headers:{"content-type":"application/json"}});
  };
  try {
    const drafts=await requestAiDrafts({accessToken:"token",topic:"Oil prices",observation:"Fuel costs may rise",angle:"short",sourceUrl:""});
    assert.deepEqual(drafts,["Draft one","Draft two","Draft three"]);
    assert.equal(calls.length,1);
    assert.equal(calls[0].url,"/api/ai-writer");
    assert.equal(calls[0].options.method,"POST");
    assert.equal(calls[0].options.credentials,"same-origin");
    assert.equal(JSON.parse(calls[0].options.body).topic,"Oil prices");
  } finally {globalThis.fetch=original;}
});
test("browser AI client denies missing session without any network request",async()=>{
  const original=globalThis.fetch;let requests=0;globalThis.fetch=async()=>{requests++;throw Error("unexpected network call");};
  try {
    await assert.rejects(requestAiDrafts({accessToken:"",topic:"Oil prices"}),/sign in/i);
    assert.equal(requests,0);
  } finally {globalThis.fetch=original;}
});
