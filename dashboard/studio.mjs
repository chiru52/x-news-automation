/** SignalDesk: no-cost editorial writing starters and evidence-limited research.
 *
 * Not AI inference, no network calls, no factual conclusions derived from
 * unseen article bodies. All claims come from attributed publisher headlines
 * already in the public feed and require manual verification.
 */
const MAX_HEADLINE = 260;
const VALID_TONES = Object.freeze(["brief", "professional", "analytical", "discussion", "factual"]);
const QUESTIONS = Object.freeze({
  technology: [
    "What functionality is actually available, and to whom?",
    "What is new compared with the previous product or research?",
    "Does the original source cite a demo, documentation, or an official announcement?"
  ],
  saas: [
    "Which customers or use cases could be affected?",
    "Are pricing, availability, revenue or funding figures independently supported?",
    "What has changed for users compared with existing alternatives?"
  ],
  markets: [
    "Is this a confirmed event or a prediction about future prices?",
    "What is the date, jurisdiction and primary filing or data source?",
    "What assumptions or risks would change the interpretation?"
  ]
});
function cleanText(value, limit) {
  return typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, limit) : "";
}
export function safeArticleUrl(value) {
  if (typeof value !== "string") return "";
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || !url.hostname) return "";
    return url.href;
  } catch (_) { return ""; }
}
export function approximateXCharacters(value) {
  return cleanText(value, 1000).replace(/https?:\/\/[^\s]+/gi, "x".repeat(23)).length;
}
export function shortHeadline(value, max = MAX_HEADLINE) {
  const title = cleanText(value, MAX_HEADLINE);
  if (title.length <= max) return title;
  return title.slice(0, Math.max(1, max - 1)).trimEnd() + "…";
}
function prepareText(lines, url) {
  const link = safeArticleUrl(url);
  if (!link) return "";
  const body = lines.filter(Boolean).join("\n\n");
  // Never cut a URL or invent a fact; truncate just the headline text.
  // Reserve the two line separators as well as the t.co-weighted source link.
  const allowance = 280 - (2 + approximateXCharacters(link));
  if (allowance <= 0) return "";
  let shortened = body;
  if (approximateXCharacters(shortened) > allowance) {
    shortened = shortened.slice(0, Math.max(1, allowance - 1)).trimEnd() + "…";
  }
  return shortened + "\n\n" + link;
}
function conversationalHeadline(title, category) {
  // Only a narrow, verifiable funding headline is paraphrased. Everything
  // else remains an attributed headline, never a fabricated article summary.
  const raise = /^(.+?)\s+(?:raises?|secures?)\s+([$€£₹]\s?\d[\d,.]*(?:[KMB]|\s?(?:million|billion))?)(?:\s+(Pre[- ]?Series\s?[A-Z]|Series\s?[A-Z]|Pre[- ]?Seed|Seed))?\b/i.exec(title);
  if (category === "saas" && raise) {
    const stage = raise[3] ? " in a " + raise[3] + " round" : "";
    return raise[1].trim() + " reportedly raised " + raise[2] + stage + ".";
  }
  return title.replace(/^(?:Stock Market|Market Outlook)\s*:\s*/i, "").trim();
}
function conversationalAngles(item) {
  const title = cleanText(item.title, MAX_HEADLINE);
  if (item.category === "saas" && /\b(?:raises?|secures?)\b/i.test(title) && /[$€£₹]\s?\d/.test(title)) {
    return {
      brief: "I'm curious where the team takes the business from here.",
      professional: "The amount is one part of the story. What matters next is how it gets used.",
      analytical: "What will that capital actually help the company build?",
      discussion: "Funding is the headline, but execution is the real test. What do you think?"
    };
  }
  if (item.category === "markets" && (title.endsWith("?") || /\b(?:will|could|might|forecast)\b/i.test(title))) {
    return {
      brief: "I'd rather check the latest numbers than guess from a headline.",
      professional: "It's a question, not a confirmed market direction.",
      analytical: "Which data would you check before taking a view?",
      discussion: "Would you make a call from this headline, or wait for actual trading data?"
    };
  }
  if (item.category === "markets" && /earnings/i.test(title)) {
    return {
      brief: "I'd look at the actual results before drawing conclusions.",
      professional: "What's behind the earnings misses matters more than the initial reaction.",
      analytical: "What do the underlying earnings figures show compared with expectations?",
      discussion: "How much should one set of earnings change the bigger picture?"
    };
  }
  if (item.category === "saas") return {
    brief: "I'm curious how this affects the people who use the product.",
    professional: "I'd look beyond the announcement to see what customers can actually do.",
    analytical: "What changes for customers, and which details are still unconfirmed?",
    discussion: "Useful progress or just a good headline? What do you think?"
  };
  if (item.category === "markets") return {
    brief: "I'd check the actual numbers before deciding what this means.",
    professional: "The underlying figures and timing are more useful than the headline alone.",
    analytical: "What does the source data confirm, and what's still interpretation?",
    discussion: "Does this change your view, or is it too early to tell?"
  };
  return {
    brief: "I'm curious what this means for people using the technology.",
    professional: "The interesting part is what changes in practice, beyond the announcement.",
    analytical: "What changes in practice? I'd look for details or a real demonstration.",
    discussion: "Would this make a difference in your day-to-day work? What do you think?"
  };
}
export function postStarters(item) {
  const url = safeArticleUrl(item?.source_url);
  const title = cleanText(item?.title, MAX_HEADLINE);
  if (!title || !url) return [];
  const lead = conversationalHeadline(title, item?.category);
  const angles = conversationalAngles({...item, title});
  const starters = [
    {tone:"brief", label:"Conversational", description:"Easy, natural explanation",
     lines:[lead, angles.brief]},
    {tone:"professional", label:"Professional", description:"Clear, grounded perspective",
     lines:[lead, angles.professional]},
    {tone:"analytical", label:"Analytical", description:"A useful question without invented facts",
     lines:[lead, angles.analytical]},
    {tone:"discussion", label:"Discussion", description:"Invite a genuine conversation",
     lines:[lead, angles.discussion]},
    {tone:"factual", label:"Source-attributed", description:"Headline and publisher, no added claims",
     lines:["Publisher: "+(cleanText(item?.publisher,65)||"Original source"),lead]}
  ];
  return starters.map(draft => ({
    tone: draft.tone,
    label: draft.label,
    description: draft.description,
    text: prepareText(draft.lines, url)
  }));
}
/**
 * A three-part EDITABLE discussion outline, not three reported facts.
 * Only the first part repeats the publisher's headline; the others contain
 * generic verification prompts and a source link. No article body is read.
 */
const THREAD_CHECKS=Object.freeze({
  technology:"What is actually available, and how would you test it against existing alternatives?",
  saas:"What changes for customers, and what do pricing, usage or official documents confirm?",
  markets:"What do the primary figures, filings and dates confirm before drawing conclusions?"
});
export function threadOutline(item) {
  const url=safeArticleUrl(item?.source_url);
  const title=cleanText(item?.title,MAX_HEADLINE);
  if(!url||!title)return [];
  const publisher=cleanText(item?.publisher,55)||"the publisher";
  const lead="1/3 "+publisher+" reports: ";
  // Leave the entire first part within the ordinary 280 character limit.
  const available=Math.max(20,275-approximateXCharacters(lead));
  const first=lead+shortHeadline(title,available);
  const second="2/3 What I'd verify next:\n"+(THREAD_CHECKS[item?.category]||THREAD_CHECKS.technology);
  const third="3/3 The headline is a starting point, not the complete story. What would you want confirmed before forming an opinion?\n\nSource: "+url;
  const result=[first,second,third];
  return result.every(part=>approximateXCharacters(part)<=280)?result:[];
}
/** Check all three posts before copying. Returns only safe, bounded issues. */
export function reviewThread(parts,sourceUrl) {
  const url=safeArticleUrl(sourceUrl);
  if(!url||!Array.isArray(parts)||parts.length!==3)return {valid:false,reason:"Thread source or structure is unavailable."};
  if(parts.some(part=>typeof part!=="string"||!part.trim()))
    return {valid:false,reason:"Write all three posts before copying."};
  if(parts.some(part=>part.length>1000||approximateXCharacters(part)>280))
    return {valid:false,reason:"One or more posts exceed the approximate 280-character limit."};
  if(!parts.some(part=>part.includes(url)))
    return {valid:false,reason:"Keep the original source link in at least one post."};
  return {valid:true,reason:"Ready to copy manually after reviewing the source."};
}

export function draftFromNotes(notes, url) {
  const content = cleanText(notes, 1200);
  if (!content || !safeArticleUrl(url)) return "";
  // This is entirely USER-WRITTEN prose. No model or fact verification.
  return prepareText([content], url);
}
export function researchGuide(item) {
  const url = safeArticleUrl(item?.source_url);
  const title = cleanText(item?.title, MAX_HEADLINE);
  const publisher = cleanText(item?.publisher, 90) || "Original publisher";
  const category = ["technology","saas","markets","world","policy","factcheck"].includes(item?.category)
    ? item.category : "technology";
  // This came only from RSS description metadata; it must never be described
  // as independently checked, a full article reading or an AI summary.
  const hasPreview = item?.kind === "news" &&
    item?.context_status === "rss_preview" &&
    typeof item?.source_preview === "string" &&
    item.source_preview.length > 0 && item.source_preview.length <= 170;
  const sourcePreview = hasPreview ? cleanText(item.source_preview, 170) : "";
  const questions = [...QUESTIONS[category]];
  const factsToCheck = title + " " + sourcePreview;
  const amounts = [...new Set(factsToCheck.match(/(?:[$€£₹]\s?\d[\d,.]*\s?(?:million|billion|[KMB])?|\b\d[\d,.]*\s?%)/gi) || [])].slice(0,3);
  if (amounts.length) {
    questions.unshift("Can you verify " + amounts.join(", ") + " from the original publisher or a primary source?");
  }
  if (/\b(?:may|might|could|will|rumou?r|forecast|expect(?:s|ed)?)\b/i.test(factsToCheck)) {
    questions.unshift("Is this a forecast, possibility or rumor rather than an established outcome?");
  }
  return {
    heading: title,
    publisher,
    source_url: url,
    evidence: sourcePreview
      ? "Short RSS-feed preview only; not checked against full article."
      : "Headline and original link only; RSS description not available.",
    preview: sourcePreview,
    preview_label: sourcePreview ? "From the RSS preview (unverified)" : "No additional RSS preview available",
    caution: "A feed description can omit qualifications or contain errors. Read the source before sharing.",
    questions: questions.slice(0,5),
    next: "Open the original article and verify its date, primary sources and material claims."
  };
}
export {VALID_TONES};
