/** SignalDesk: no-cost editorial writing starters and evidence-limited research.
 *
 * Not AI inference, no network calls, no factual conclusions derived from
 * unseen article bodies. All claims come from attributed publisher headlines
 * already in the public feed and require manual verification.
 */
const MAX_HEADLINE = 260;
const VALID_TONES = Object.freeze(["brief", "professional", "analytical", "discussion"]);
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
export function postStarters(item) {
  const url = safeArticleUrl(item?.source_url);
  const title = cleanText(item?.title, MAX_HEADLINE);
  const publisher = cleanText(item?.publisher, 90);
  if (!title || !url) return [];
  const attribution = publisher ? "Reported by " + publisher + ":" : "Reported headline:";
  const starters = [
    {tone:"brief", label:"News brief", description:"Simple, attributed update",
     lines:[attribution + " " + title]},
    {tone:"professional", label:"Professional", description:"Factual style with no added claims",
     lines:["In the news: " + title, publisher ? "Source: " + publisher : "Review the reporting."]},
    {tone:"analytical", label:"Analytical", description:"Adds a question, not an unsupported conclusion",
     lines:["Worth examining: " + title, "What changes in practice?"]},
    {tone:"discussion", label:"Discussion", description:"Invite opinions without asserting new facts",
     lines:[title, "What do you think?"]}
  ];
  return starters.map(draft => ({
    tone: draft.tone,
    label: draft.label,
    description: draft.description,
    text: prepareText(draft.lines, url)
  }));
}
export function researchGuide(item) {
  const url = safeArticleUrl(item?.source_url);
  const title = cleanText(item?.title, MAX_HEADLINE);
  const publisher = cleanText(item?.publisher, 90) || "Original publisher";
  const category = ["technology","saas","markets"].includes(item?.category)
    ? item.category : "technology";
  return {
    heading: title,
    publisher,
    source_url: url,
    evidence: "Publisher headline and linked article only. No full-text article analysis has been performed.",
    caution: "The headline is an attributed report, not an independently verified fact.",
    questions: [...QUESTIONS[category]],
    next: "Open the original article and verify its date, primary sources and material claims."
  };
}
export {VALID_TONES};
