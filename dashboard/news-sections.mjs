/**
 * Shared, pure menu taxonomy. Trending is a ranking of news (not a separate
 * region), and global/India partition the same deduplicated public news pool.
 * No requests, storage access, cookies, personal data, AI or X posting.
 */
const INDIA_MARKERS = /\b(?:india|indian|bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pune|gurugram|noida|rbi|sebi|nifty|sensex|nse|bse|rupee|rupees|lakh|crore|isro|aadhaar|upi)\b/i;
const INDIA_FOCUSED_SOURCES = new Set(["Inc42 India Startups","ET Entrepreneur India Startups"]);
export const NEWS_VIEWS = Object.freeze(["all","trending","global","india"]);

export function isIndiaArticle(item) {
  return item?.kind === "news" && (item.region === "india" ||
    INDIA_FOCUSED_SOURCES.has(item.publisher) ||
    INDIA_MARKERS.test(item.title || ""));
}
export function eligibleNews(items, stageOf, storyKey) {
  const seen = new Set();
  return items.filter(item => {
    if (item.kind !== "news" || item.history_only ||
        ["copied","archived"].includes(stageOf(item))) return false;
    const key = storyKey(item.source_url) || item.id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function dateValue(item) {
  const value = new Date(item.published_at || item.updated_at).getTime();
  return Number.isFinite(value) ? value : 0;
}
export function topNews(items, limit=5) {
  return [...items].sort((a,b) =>
    (b.trend_score||0)-(a.trend_score||0) ||
    dateValue(b)-dateValue(a) || (a.index||0)-(b.index||0)).slice(0,limit);
}
export function newsInSection(items, view, trending=topNews(items)) {
  const trendingIds = new Set(trending.map(item=>item.id));
  return items.filter(item =>
    (view !== "india" || isIndiaArticle(item)) &&
    (view !== "global" || !isIndiaArticle(item)) &&
    (view !== "trending" || trendingIds.has(item.id))
  );
}
