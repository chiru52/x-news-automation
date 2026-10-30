// The only authenticated POST from the public dashboard. Same-origin AI drafting only.
// No X publishing, no collector writes, no third-party provider calls in the browser.
export async function requestAiDrafts({accessToken,topic,observation,angle,sourceUrl}){
  if(typeof accessToken!=="string"||!accessToken.trim())throw Error("Please sign in before using AI Writer.");
  const response=await fetch("/api/ai-writer",{
    method:"POST",
    credentials:"same-origin",
    headers:{"content-type":"application/json","authorization":"Bearer "+accessToken},
    body:JSON.stringify({topic,observation,angle,sourceUrl})
  });
  const result=await response.json();
  if(!response.ok)throw Error(typeof result.error==="string"?result.error:"AI generation unavailable.");
  if(!Array.isArray(result.drafts)||result.drafts.length!==3)throw Error("Invalid AI result.");
  return result.drafts;
}
