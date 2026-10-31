/** Only article-specific publisher-supplied RSS/Atom image URLs.
 * No page scraping, proxy, third-party image APIs or guessed photos.
 * This pure helper is shared by the news Worker and the static dashboard.
 */
export function safeNewsImage(value) {
  if (typeof value !== "string" || value.length > 1400 ||
      /[\s\\<>"'\x00-\x1f\x7f]/.test(value)) return "";
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password ||
        url.port || !url.hostname || url.hostname.length > 250 ||
        url.hostname === "localhost" || url.hostname.endsWith(".localhost") ||
        /^\d+(?:\.\d+){3}$/.test(url.hostname) || url.hostname.includes(":") ||
        /(?:^|\.)(?:local|internal|test)$/.test(url.hostname)) return "";
    // Never load executable/animated/vector or article page formats as cover images.
    if (/\.(?:svgz?|gif|ico|html?|js|xml|pdf)(?:$|[?#])/i.test(url.pathname)) return "";
    if (!/^[\x21-\x7e]+$/.test(value)) return "";
    return url.href;
  } catch { return ""; }
}
const asArray = value => Array.isArray(value) ? value : value ? [value] : [];
function imageType(entry) {
  return /^(?:image\/(?:jpeg|png|webp|avif))(?:;|$)/i.test(String(entry?.["@_type"] || ""));
}
function plausibleSize(entry) {
  const width = Number(entry?.["@_width"]), height = Number(entry?.["@_height"]);
  return !(Number.isFinite(width) && width > 0 && width < 160) &&
    !(Number.isFinite(height) && height > 0 && height < 90);
}
function imageCandidate(entry, forced=false) {
  if (!entry || typeof entry !== "object" || !plausibleSize(entry)) return "";
  const value = safeNewsImage(entry["@_url"] || entry["@_href"]);
  if (!value) return "";
  const imagePath = /\.(?:jpe?g|png|webp|avif)(?:$|[?#])/i.test(new URL(value).pathname);
  return forced || imageType(entry) || entry["@_medium"] === "image" || imagePath ? value : "";
}
export function imageFromRssEntry(entry) {
  if (!entry || typeof entry !== "object") return "";
  // media:thumbnail -> "thumbnail", media:content -> "content" with
  // fast-xml-parser removeNSPrefix:true. Prefer explicitly tagged media.
  for (const candidate of asArray(entry.thumbnail)) {
    const image = imageCandidate(candidate, true);
    if (image) return image;
  }
  for (const candidate of asArray(entry.content)) {
    const image = imageCandidate(candidate);
    if (image) return image;
  }
  for (const candidate of asArray(entry.enclosure)) {
    if (!imageType(candidate)) continue;
    const image = imageCandidate(candidate);
    if (image) return image;
  }
  for (const candidate of asArray(entry.link)) {
    if (candidate?.["@_rel"] !== "enclosure" || !imageType(candidate)) continue;
    const image = imageCandidate(candidate);
    if (image) return image;
  }
  return "";
}
