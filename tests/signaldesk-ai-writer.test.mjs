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
  const env={OPENAI_API_KEY:"test",AI_WRITER_MODEL:"test",SUPABASE_URL:"https://example.supabase.co",SUPABASE_PUBLISHABLE_KEY:"public",AI_WRITER_KV:{}};
  assert.equal((await onRequestPost({...make({origin:"https://evil.example"}),env})).status,403);
  assert.equal((await onRequestPost({...make(),env})).status,401);
  assert.equal((await onRequestPost({...make({"content-type":"text/plain"}),env})).status,415);
});
