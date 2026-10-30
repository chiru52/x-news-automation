/**
 * SignalDesk personal cloud backups. Browser data is uploaded only after the
 * signed-in user explicitly clicks Back up. No background writes, X posting,
 * credentials, local auth tokens, or cross-account guest data collection.
 */
export const BACKUP_FIELDS=Object.freeze({
  saved:"signaldesk:saved:v1",
  workflow:"signaldesk:workflow:v1",
  edits:"signaldesk:edits:v1",
  notes:"signaldesk:research-notes:v1",
  copied:"signaldesk:copied-library:v1",
  history:"signaldesk:saved-history:v1"
});
const MAX_BACKUP_BYTES=480000;
const LIST_LIMITS={saved:300,copied:100,history:100};
const OBJECT_LIMITS={workflow:300,edits:100,notes:100};
const WORKFLOW_STAGES=new Set(["new","reviewing","ready","copied","archived"]);
const isRecord=value=>value!==null && typeof value==="object" && !Array.isArray(value);
const validId=id=>typeof id==="string" && id.length<=140 && /^(news|draft):[a-z0-9]{16,120}$/i.test(id);
function readStored(storage,key){
  const value=storage.getItem(key);
  if(value===null)return null;
  return JSON.parse(value);
}
function normalized(field,value){
  if(field in LIST_LIMITS){
    if(!Array.isArray(value))throw Error("Unexpected "+field+" format");
    const filtered=value.filter(item=>{
      if(field==="saved")return validId(item);
      return isRecord(item)&&validId(item.id)&&typeof item.title==="string" &&
        typeof item.source_url==="string" && /^https:\/\//.test(item.source_url);
    });
    return filtered.slice(-LIST_LIMITS[field]);
  }
  if(!isRecord(value))throw Error("Unexpected "+field+" format");
  const entries=Object.entries(value).filter(([id,item])=>{
    if(!validId(id))return false;
    if(field==="workflow")return WORKFLOW_STAGES.has(item);
    return typeof item==="string" && item.length <= (field==="notes"?1200:1000);
  });
  return Object.fromEntries(entries.slice(-OBJECT_LIMITS[field]));
}
function assertSize(snapshot){
  if(new TextEncoder().encode(JSON.stringify(snapshot)).length>MAX_BACKUP_BYTES)
    throw Error("Browser data is too large for one cloud backup. No changes were made.");
}
export function collectBrowserBackup(storage){
  const payload={schema_version:1};
  for(const [field,key] of Object.entries(BACKUP_FIELDS)){
    let value;
    try{value=readStored(storage,key)}catch(_){throw Error("Cannot read "+field+" browser data. No backup was uploaded.");}
    payload[field]=normalized(field,value===null?(field in LIST_LIMITS?[]:{}):value);
  }
  assertSize(payload);
  return payload;
}
export function validateBackup(payload){
  if(!isRecord(payload)||payload.schema_version!==1)
    throw Error("Incompatible cloud backup format.");
  const result={schema_version:1};
  for(const field of Object.keys(BACKUP_FIELDS)){
    if(!(field in payload))throw Error("Cloud backup is missing "+field+".");
    result[field]=normalized(field,payload[field]);
  }
  assertSize(result);
  return result;
}
export function restoreBrowserBackup(storage,payload){
  const safe=validateBackup(payload);
  const originals=new Map();
  const writes=[];
  for(const [field,key] of Object.entries(BACKUP_FIELDS)){
    originals.set(key,storage.getItem(key));
    writes.push([key,JSON.stringify(safe[field])]);
  }
  try{for(const [key,value] of writes)storage.setItem(key,value);}
  catch(_error){
    // Best-effort rollback if storage is unavailable or quota is exhausted.
    for(const [key,value] of originals){
      try{if(value===null)storage.removeItem(key);else storage.setItem(key,value);}catch(_){}
    }
    throw Error("Could not restore backup on this device. Check browser storage.");
  }
  return Object.keys(BACKUP_FIELDS).length;
}
