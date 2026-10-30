import test from "node:test";
import assert from "node:assert/strict";
import {BACKUP_FIELDS,collectBrowserBackup,validateBackup,restoreBrowserBackup} from "../dashboard/cloud-sync.mjs";
function storage(seed={}){
  const map=new Map(Object.entries(seed));
  return {getItem:key=>map.has(key)?map.get(key):null,
    setItem:(key,value)=>map.set(key,String(value)),removeItem:key=>map.delete(key)};
}
const newsId="news:"+("a".repeat(24));
const draftId="draft:"+("b".repeat(24));
test("empty guest browser has a safe, bounded snapshot",()=>{
  const snapshot=collectBrowserBackup(storage());
  assert.equal(snapshot.schema_version,1);
  assert.deepEqual(snapshot.saved,[]);
  assert.deepEqual(snapshot.workflow,{});
  assert.equal(Object.keys(BACKUP_FIELDS).length,6);
});
test("saved articles, stage, notes, copied items and edits survive a full round trip",()=>{
  const source=storage({
    [BACKUP_FIELDS.saved]:JSON.stringify([newsId]),
    [BACKUP_FIELDS.workflow]:JSON.stringify({[newsId]:"ready"}),
    [BACKUP_FIELDS.edits]:JSON.stringify({[draftId]:"New draft"}),
    [BACKUP_FIELDS.notes]:JSON.stringify({[newsId]:"Check original publisher"}),
    [BACKUP_FIELDS.copied]:JSON.stringify([{id:newsId,title:"Sample",source_url:"https://example.com/article"}]),
    [BACKUP_FIELDS.history]:JSON.stringify([{id:newsId,title:"Saved",source_url:"https://example.com/story"}])
  });
  const payload=collectBrowserBackup(source),destination=storage();
  assert.equal(restoreBrowserBackup(destination,payload),6);
  assert.deepEqual(collectBrowserBackup(destination),payload);
});
test("unknown schema, malformed fields, non-HTTPS sources and unrelated keys are rejected or filtered",()=>{
  const original=collectBrowserBackup(storage());
  assert.throws(()=>restoreBrowserBackup(storage(),{...original,schema_version:99}),/Incompatible/);
  assert.throws(()=>restoreBrowserBackup(storage(),{...original,saved:{}}),/Unexpected saved/);
  assert.deepEqual(validateBackup({...original,saved:["not-an-id",newsId],workflow:{[newsId]:"fake"}}).saved,[newsId]);
  assert.deepEqual(validateBackup({...original,copied:[{id:newsId,title:"bad",source_url:"http://invalid.test"}]}).copied,[]);
  const destination=storage({unrelated:"kept"});
  restoreBrowserBackup(destination,original);
  assert.equal(destination.getItem("unrelated"),"kept");
});
test("large backups are blocked rather than truncated silently",()=>{
  const bad=storage({[BACKUP_FIELDS.notes]:JSON.stringify({[newsId]:"X".repeat(1000000)})});
  assert.deepEqual(collectBrowserBackup(bad).notes,{}); // invalid note rejected
  const huge=storage({[BACKUP_FIELDS.copied]:JSON.stringify(Array.from({length:100},(_,i)=>({
    id:"news:"+String(i).padStart(24,"0"),title:"X".repeat(6000),source_url:"https://example.com"})))});
  assert.throws(()=>collectBrowserBackup(huge),/too large/);
});
