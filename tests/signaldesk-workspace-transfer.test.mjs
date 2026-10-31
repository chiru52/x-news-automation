import test from "node:test";
import assert from "node:assert/strict";
import {createWorkspaceTransfer,restoreWorkspaceTransfer,validateWorkspaceTransfer,TOPIC_WRITER_KEY,TRANSFER_KIND} from "../dashboard/workspace-transfer.mjs";

function memoryStorage(initial={}){
  const data=new Map(Object.entries(initial));
  return {
    data,getItem:key=>data.has(key)?data.get(key):null,
    setItem:(key,value)=>data.set(key,String(value)),
    removeItem:key=>data.delete(key)
  };
}
const id="news:1234567890abcdef";
const seed={
  "signaldesk:saved:v1":JSON.stringify([id]),
  "signaldesk:workflow:v1":JSON.stringify({[id]:"reviewing"}),
  "signaldesk:edits:v1":JSON.stringify({[id]:"My carefully checked draft"}),
  "signaldesk:research-notes:v1":JSON.stringify({[id]:"Source checked manually"}),
  "signaldesk:copied-library:v1":JSON.stringify([{id,kind:"news",title:"Sample story",source_url:"https://publisher.example/story"}]),
  "signaldesk:saved-history:v1":JSON.stringify([]),
  [TOPIC_WRITER_KEY]:JSON.stringify({topic:"Markets",angle:"short",observation:"My observation",source:"",text:"Edited personal draft"}),
  "supabase.auth.token":"PRIVATE-DO-NOT-EXPORT",
  "unrelated-storage":"not-for-backup"
};
test("exports only allowlisted editorial data, including the local Topic Writer draft",()=>{
  const payload=createWorkspaceTransfer(memoryStorage(seed),new Date("2026-10-31T00:00:00Z"));
  assert.equal(payload.kind,TRANSFER_KIND);
  assert.equal(payload.exported_at,"2026-10-31T00:00:00.000Z");
  assert.deepEqual(payload.workspace.saved,[id]);
  assert.equal(payload.topic.text,"Edited personal draft");
  const serialized=JSON.stringify(payload);
  assert.ok(!serialized.includes("PRIVATE-DO-NOT-EXPORT"));
  assert.ok(!serialized.includes("not-for-backup"));
});
test("imports the backup on another browser origin without any network calls",()=>{
  const exported=createWorkspaceTransfer(memoryStorage(seed),new Date("2026-10-31T00:00:00Z"));
  const destination=memoryStorage({"signaldesk:saved:v1":"[]"});
  const result=restoreWorkspaceTransfer(destination,exported);
  assert.deepEqual(result,{saved:1,copied:1,notes:1,edits:1});
  assert.deepEqual(JSON.parse(destination.getItem("signaldesk:saved:v1")),[id]);
  assert.equal(JSON.parse(destination.getItem(TOPIC_WRITER_KEY)).text,"Edited personal draft");
});
test("invalid backup formats and unsafe Topic Writer source do not overwrite storage",()=>{
  const exported=createWorkspaceTransfer(memoryStorage(seed));
  const bad={...exported,topic:{...exported.topic,source:"javascript:alert(1)"}};
  const destination=memoryStorage(seed);
  const before=JSON.stringify([...destination.data]);
  assert.throws(()=>restoreWorkspaceTransfer(destination,bad),/Invalid Topic Writer/);
  assert.equal(JSON.stringify([...destination.data]),before);
  assert.throws(()=>validateWorkspaceTransfer({kind:"other"}),/supported SignalDesk/);
});
test("failed local storage writes roll back previously imported fields",()=>{
  const exported=createWorkspaceTransfer(memoryStorage(seed));
  const destination=memoryStorage({
    "signaldesk:saved:v1":"[]",
    "signaldesk:workflow:v1":"{}"
  });
  const original=destination.setItem;
  destination.setItem=(key,value)=>{
    if(key===TOPIC_WRITER_KEY)throw Error("blocked by quota");
    return original(key,value);
  };
  assert.throws(()=>restoreWorkspaceTransfer(destination,exported),/Could not import workspace/);
  assert.equal(destination.getItem("signaldesk:saved:v1"),"[]");
  assert.equal(destination.getItem("signaldesk:workflow:v1"),"{}");
});
