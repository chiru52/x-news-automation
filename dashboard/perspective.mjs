/** Human-guided topic writing; no AI, no invented facts, no publishing.
 * Text contains only framing language, user input and optional HTTPS source.
 */
import {approximateXCharacters,safeArticleUrl} from "./studio.mjs";

export const TOPIC_ANGLES=Object.freeze(["observation","implications","connecting","question","short"]);
const clean=(value,max)=>typeof value==="string"
  ?value.replace(/[\u0000-\u001f\u007f]/g," ").replace(/\s+/g," ").trim().slice(0,max):"";
const cap=text=>text?text[0].toUpperCase()+text.slice(1):"";
const factNumbers=/(?:[$€£₹]\s*\d[\d,.]*|\b\d[\d,.]*\s?(?:%|percent\b|billion\b|million\b|trillion\b|crore\b|lakh\b))/i;
export function needsSourceForClaims(text){return factNumbers.test(text);}
export function composeTopicDraft({topic="",angle="observation",observation="",sourceUrl=""}={}) {
  const subject=clean(topic,90),insight=clean(observation,500);
  if(!subject)return {text:"",valid:false,message:"Enter a topic first."};
  if(!TOPIC_ANGLES.includes(angle))return {text:"",valid:false,message:"Choose a writing angle."};
  const raw=typeof sourceUrl==="string"?sourceUrl.trim():"";
  const source=raw?safeArticleUrl(raw):"";
  if(raw&&!source)return {text:"",valid:false,message:"Use a valid HTTPS source link, or leave it blank for opinion-only writing."};
  // Prefer the author's actual observation over repetitive canned closers.
  // This is a deterministic writing aid, not AI-authored analysis.
  const sentence=cap(subject).replace(/[.?!]+$/,"");
  const framing={
    observation:insight ? sentence+": " : "One thought on "+subject+":",
    implications:subject+" — here's why it matters to me:",
    connecting:"I keep coming back to "+subject+" when thinking about the bigger picture.",
    question:"What are we overlooking about "+subject+"?",
    short:sentence+".",
  }[angle];
  const text=angle==="observation"&&insight
    ?[framing+insight,source].filter(Boolean).join("\n\n")
    :[framing,insight,source].filter(Boolean).join("\n\n");
  const review=reviewTopicDraft(text,{sourceUrl:source});
  return {...review,text};
}
export function reviewTopicDraft(text,{sourceUrl=""}={}) {
  if(typeof text!=="string"||!text.trim())return {valid:false,message:"Write a draft first.",count:0};
  if(text.length>1000)return {valid:false,message:"Draft exceeds the editor's 1,000-character limit.",count:approximateXCharacters(text)};
  const count=approximateXCharacters(text);
  if(count>280)return {valid:false,message:"Over the approximate 280-character X limit. Shorten or turn it into a thread.",count};
  if(sourceUrl&&(!safeArticleUrl(sourceUrl)||!text.includes(sourceUrl)))
    return {valid:false,message:"Keep your supporting source link in the post.",count};
  if(needsSourceForClaims(text)&&!sourceUrl)
    return {valid:false,message:"This draft contains numerical claims. Add a supporting HTTPS source and check the figures.",count};
  return {valid:true,message:"Length checked. Read and verify all factual claims before copying.",count};
}
