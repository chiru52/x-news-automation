/** Explicit, local-only SignalDesk workspace transfer between preview and production origins.
 * Export/import user-initiated only. No cloud writes, tokens, cookies, or X publishing.
 */
import {BACKUP_FIELDS, collectBrowserBackup, restoreBrowserBackup, validateBackup} from "./cloud-sync.mjs";

export const TRANSFER_KIND="signaldesk-local-workspace";
export const TOPIC_WRITER_KEY="signaldesk:topic-writer:v1";
const MAX_BYTES=500000;
const ANGLES=new Set(["observation","implications","connecting","question","short"]);
const isRecord=value=>value!==null&&typeof value==="object"&&!Array.isArray(value);
const validUrl=value=>{
  if(value==="")return true;
  try{
    const u=new URL(value);
    return u.protocol==="https:"&&!u.username&&!u.password&&!u.hash&&!u.port;
  }catch{return false;}
};
function normalizeTopic(value){
  if(value===null)return null;
  if(!isRecord(value))throw Error("Invalid Topic Writer draft in workspace backup.");
  const bounds={topic:90,angle:20,observation:500,source:900,text:1000};
  const clean={};
  for(const [field,length] of Object.entries(bounds)){
    if(typeof value[field]!=="string"||value[field].length>length)
      throw Error("Invalid Topic Writer field: "+field);
    clean[field]=value[field];
  }
  if(!ANGLES.has(clean.angle)||!validUrl(clean.source))
    throw Error("Invalid Topic Writer settings or source.");
  return clean;
}
function bytes(value){return new TextEncoder().encode(JSON.stringify(value)).length;}
function parsePackage(payload){
  if(!isRecord(payload)||payload.kind!==TRANSFER_KIND||payload.format_version!==1||
     typeof payload.exported_at!=="string"||!/^\d{4}-\d\d-\d\dT/.test(payload.exported_at))
    throw Error("This is not a supported SignalDesk workspace backup.");
  if(bytes(payload)>MAX_BYTES)throw Error("Workspace backup exceeds the 500 KB limit.");
  const workspace=validateBackup(payload.workspace);
  const topic=normalizeTopic(payload.topic??null);
  return {workspace,topic};
}
export function createWorkspaceTransfer(storage,now=new Date()){
  let topic=null;
  try{
    const raw=storage.getItem(TOPIC_WRITER_KEY);
    topic=raw===null?null:normalizeTopic(JSON.parse(raw));
  }catch{throw Error("Cannot safely export your Topic Writer draft. No file was created.");}
  const packageData={
    kind:TRANSFER_KIND,format_version:1,exported_at:now.toISOString(),
    workspace:collectBrowserBackup(storage),topic
  };
  if(bytes(packageData)>MAX_BYTES)throw Error("Workspace is too large to export.");
  return packageData;
}
export function validateWorkspaceTransfer(payload){return parsePackage(payload);}
export function restoreWorkspaceTransfer(storage,payload){
  const {workspace,topic}=parsePackage(payload);
  const originals=new Map();
  for(const key of [...Object.values(BACKUP_FIELDS),TOPIC_WRITER_KEY])
    originals.set(key,storage.getItem(key));
  try{
    restoreBrowserBackup(storage,workspace);
    if(topic===null)storage.removeItem(TOPIC_WRITER_KEY);
    else storage.setItem(TOPIC_WRITER_KEY,JSON.stringify(topic));
  }catch(error){
    for(const [key,value] of originals){
      try{if(value===null)storage.removeItem(key);else storage.setItem(key,value);}catch{}
    }
    throw Error("Could not import workspace; previous local data was restored where possible.");
  }
  return {saved:workspace.saved.length,copied:workspace.copied.length,
          notes:Object.keys(workspace.notes).length,
          edits:Object.keys(workspace.edits).length};
}
