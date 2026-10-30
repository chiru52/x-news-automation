import test from "node:test";
import assert from "node:assert/strict";
import {onRequestPost} from "../functions/api/ai-writer.js";
const make=(headers={},body={topic:"Oil prices",angle:"observation",observation:"Fuel affects costs"})=>({
  request:new Request("https://signaldesk-preview.pages.dev/api/ai-writer",{
    method:"POST",headers:{"content-type":"application/json","origin":"https://signaldesk-preview.pages.dev",...headers},
    body:JSON.stringify(body)
  })
});
test("AI Writer refuses missing server secrets and KV",async()=>{
  const response=await onRequestPost({...make(),env:{}});
  assert.equal(response.status,503);
  assert.equal(response.headers.get("cache-control"),"no-store");
});
test("AI Writer checks request origin and signed-in authorization before provider call",async()=>{
  const env={AI_WRITER_ENABLED:"true",AI_WRITER_ALLOWED_USER_ID:"allowed-user",OPENAI_API_KEY:"test",AI_WRITER_MODEL:"test",SUPABASE_URL:"https://example.supabase.co",SUPABASE_PUBLISHABLE_KEY:"public",AI_WRITER_KV:{}};
  assert.equal((await onRequestPost({...make({origin:"https://evil.example"}),env})).status,403);
  assert.equal((await onRequestPost({...make(),env})).status,401);
  assert.equal((await onRequestPost({...make({"content-type":"text/plain"}),env})).status,415);
});

test("AI Writer never calls provider with an unauthorized signed-in user",async()=>{
  const original=globalThis.fetch;
  const calls=[];
  globalThis.fetch=async url=>{
    calls.push(String(url));
    return new Response(JSON.stringify({id:"someone-else"}),{status:200,headers:{"content-type":"application/json"}});
  };
  try{
    const env={AI_WRITER_ENABLED:"true",AI_WRITER_ALLOWED_USER_ID:"allowed-user",OPENAI_API_KEY:"test",
      AI_WRITER_MODEL:"test",SUPABASE_URL:"https://example.supabase.co",SUPABASE_PUBLISHABLE_KEY:"public",
      AI_WRITER_KV:{get:async()=>0,put:async()=>{}}};
    const reply=await onRequestPost({...make({authorization:"Bearer test-token"}),env});
    assert.equal(reply.status,403);
    assert.deepEqual(calls,["https://example.supabase.co/auth/v1/user"]);
  } finally {globalThis.fetch=original;}
});
test("AI Writer restricts itself to preview hostname",async()=>{
  const env={AI_WRITER_ENABLED:"true",AI_WRITER_ALLOWED_USER_ID:"allowed-user",OPENAI_API_KEY:"test",
    AI_WRITER_MODEL:"test",SUPABASE_URL:"https://example.supabase.co",SUPABASE_PUBLISHABLE_KEY:"public",AI_WRITER_KV:{}};
  const request=new Request("https://news.littlekingchess.com/api/ai-writer",{
    method:"POST",headers:{"content-type":"application/json","origin":"https://news.littlekingchess.com"},
    body:JSON.stringify({topic:"Oil prices",angle:"short"})});
  assert.equal((await onRequestPost({request,env})).status,403);
});
