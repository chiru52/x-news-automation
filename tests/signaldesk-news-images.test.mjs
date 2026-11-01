import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {safeNewsImage,imageFromRssEntry,imageFromEmbeddedHtml} from "../dashboard/news-image.mjs";
import {parseFeed,publicItem} from "../news-collector/worker.mjs";

const NOW=Date.parse("2026-10-30T12:00:00Z");
const feed={name:"Source",category:"technology",url:"https://publisher.example/rss"};
const wrap=body=>'<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item>'+
  '<title>Enterprise AI technology company launches a new service</title>'+
  '<link>https://publisher.example/story</link>'+
  '<pubDate>Fri, 30 Oct 2026 11:40:00 GMT</pubDate>'+body+
  '</item></channel></rss>';

test("only public HTTPS images with non-executable formats are allowed",()=>{
  assert.equal(safeNewsImage("https://cdn.publisher.example/images/story.jpg"),
    "https://cdn.publisher.example/images/story.jpg");
  assert.equal(safeNewsImage("https://ichef.bbci.co.uk/news/image?id=5"),
    "https://ichef.bbci.co.uk/news/image?id=5");
  for(const url of [
    "http://publisher.example/image.jpg","javascript:alert(1)",
    "data:image/svg+xml;base64,PHN2Zz4=","https://user:pass@site.example/photo.png",
    "https://localhost/x.jpg","https://127.0.0.1/photo.jpg",
    "https://cdn.example/photo.svg","https://cdn.example/animated.gif",
    "https://cdn.example/page.html","https://cdn.example/a.jpg\nx",
    "https://cdn.example:8443/photo.jpg"
  ])assert.equal(safeNewsImage(url),"",url);
});
test("use only story-associated RSS/Atom media, never whole-feed logo",()=>{
  const good=wrap('<media:thumbnail url="https://cdn.publisher.example/image.webp" width="640" height="360"/>');
  const parsed=parseFeed(good,feed,NOW);
  assert.equal(parsed.length,1);
  assert.equal(parsed[0].image_url,"https://cdn.publisher.example/image.webp");
  const atom=wrap('<media:content medium="image" url="https://cdn.publisher.example/cover.jpg" />');
  assert.equal(parseFeed(atom,feed,NOW)[0].image_url,"https://cdn.publisher.example/cover.jpg");
  const enclosure=wrap('<enclosure url="https://cdn.publisher.example/photo.png" type="image/png" />');
  assert.equal(parseFeed(enclosure,feed,NOW)[0].image_url,"https://cdn.publisher.example/photo.png");
  const bad=wrap('<media:thumbnail url="javascript:alert(1)" /><image><url>https://publisher.example/logo.jpg</url></image>');
  assert.equal(parseFeed(bad,feed,NOW)[0].image_url,"");
  const tiny=wrap('<media:thumbnail url="https://cdn.publisher.example/tracker.png" width="1" height="1"/>');
  assert.equal(parseFeed(tiny,feed,NOW)[0].image_url,"");
  assert.equal(imageFromRssEntry({enclosure:{"@_url":"https://publisher.example/image.svg","@_type":"image/svg+xml"}}),"");
});
test("public snapshot preserves an approved RSS thumbnail and keeps untrusted metadata out",async()=>{
  const parsed=parseFeed(wrap('<media:thumbnail url="https://publisher.example/story-photo.jpg"/>'),feed,NOW)[0];
  const item=await publicItem(parsed,[parsed],NOW);
  assert.equal(item.image_url,"https://publisher.example/story-photo.jpg");
  const absent=await publicItem({...parsed,image_url:"javascript:alert(1)"},[parsed],NOW);
  assert.equal(absent.image_url,"");
});
test("news explorer no longer generates music bars or fictional images",()=>{
  const js=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  const css=readFileSync(new URL("../dashboard/styles.css",import.meta.url),"utf8");
  const headers=readFileSync(new URL("../dashboard/_headers",import.meta.url),"utf8");
  assert.doesNotMatch(js,/explorer-art-strokes|explorer-art-orbit/);
  assert.doesNotMatch(css,/explorer-art-strokes/);
  assert.match(js,/safeNewsImage\(item.image_url\)/);
  assert.match(js,/referrerPolicy="no-referrer"/);
  assert.match(js,/img.loading="lazy"/);
  assert.match(headers,/img-src https:;/);
  assert.doesNotMatch(js,/fetch\s*\(|XMLHttpRequest|api\.unsplash|source\.unsplash/);
});

test("RSS item embedded HTML thumbnails work with no webpage scraping",()=>{
  const embed='<description><![CDATA[<p>Article summary</p><figure><img src="https://cdn.publisher.example/report.webp" width="960" height="540"/></figure>]]></description>';
  assert.equal(parseFeed(wrap(embed),feed,NOW)[0].image_url,"https://cdn.publisher.example/report.webp");
  const encoded='<content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/"><![CDATA[<img data-lazy-src="https://cdn.publisher.example/image.png" src="https://cdn.publisher.example/placeholder.png" />]]></content:encoded>';
  assert.equal(parseFeed(wrap(encoded),feed,NOW)[0].image_url,"https://cdn.publisher.example/image.png");
});
test("a real publisher media photo wins over embedded HTML",()=>{
  const media='<media:group><media:content url="https://cdn.publisher.example/photo.jpg" type="image/jpeg" /></media:group>';
  const html='<description><![CDATA[<img src="https://cdn.publisher.example/secondary.jpg" />]]></description>';
  assert.equal(parseFeed(wrap(media+html),feed,NOW)[0].image_url,"https://cdn.publisher.example/photo.jpg");
});
test("relevant srcset images are accepted but logos, trackers and tiny images are not",()=>{
  const srcset='<img srcset="https://cdn.publisher.example/tiny.jpg 120w, https://cdn.publisher.example/large.jpg 900w">';
  assert.equal(imageFromEmbeddedHtml(srcset),"https://cdn.publisher.example/large.jpg");
  assert.equal(imageFromEmbeddedHtml('<img src="https://cdn.publisher.example/logo.jpg"/>'),"");
  assert.equal(imageFromEmbeddedHtml('<img src="https://cdn.publisher.example/track.png" width="1" height="1"/>'),"");
  assert.equal(imageFromEmbeddedHtml('<img src="http://cdn.publisher.example/photo.jpg" />'),"");
  assert.equal(imageFromEmbeddedHtml('<img src="https://cdn.publisher.example/photo.svg"/>'),"");
  assert.equal(imageFromEmbeddedHtml('<img src="https://cdn.publisher.example/large.webp" width="640" height="350"/>'),
    "https://cdn.publisher.example/large.webp");
  assert.equal(imageFromEmbeddedHtml("x".repeat(100_001)),"");
});
test("gallery category fallback labels match source classification",()=>{
  const explorer=readFileSync(new URL("../dashboard/news-explorer.mjs",import.meta.url),"utf8");
  for(const name of ["WORLD","POLICY","FACT CHECK","MARKETS","BUSINESS","TECHNOLOGY"])
    assert.ok(explorer.includes('"'+name+'"'),name);
  assert.match(explorer,/naturalWidth>=160/);
});
