import test from "node:test";
import assert from "node:assert/strict";
import {TOPIC_ANGLES,composeTopicDraft,reviewTopicDraft,needsSourceForClaims} from "../dashboard/perspective.mjs";
import {approximateXCharacters} from "../dashboard/studio.mjs";

test("five topic angles produce different natural writing starters without inventing current news",()=>{
  assert.deepEqual(TOPIC_ANGLES,["observation","implications","connecting","question","short"]);
  const written=TOPIC_ANGLES.map(angle=>composeTopicDraft({
    topic:"The future of AI tools",
    observation:"I'd like to see tools save time on real tasks, not just demos.",
    angle
  }));
  assert.equal(new Set(written.map(x=>x.text)).size,5);
  for(const variant of written){
    assert.equal(variant.valid,true,variant.message);
    assert.ok(variant.text.includes("I'd like to see tools save time on real tasks"));
    assert.ok(approximateXCharacters(variant.text)<=280);
    assert.doesNotMatch(variant.text,/guaranteed|confirmed|will replace all/i);
    assert.doesNotMatch(variant.text,/https:\/\/(?:api\.x\.com|api\.openai\.com)/i);
  }
});
test("personal opinions require no invented article link or fake citations",()=>{
  const r=composeTopicDraft({topic:"Why saving matters",angle:"short",
    observation:"I prefer small consistent habits over flashy promises."});
  assert.equal(r.valid,true);
  assert.equal(r.text.includes("https://"),false);
  assert.equal(reviewTopicDraft(r.text).valid,true);
});
test("specific financial figures need supporting source and manual review",()=>{
  const unsourced=composeTopicDraft({topic:"Oil prices",observation:"Brent crude is $116 per barrel"});
  assert.equal(unsourced.valid,false);
  assert.match(unsourced.message,/Add a supporting HTTPS source/);
  assert.equal(needsSourceForClaims("Nearly ₹1 crore over 30 years"),true);
  assert.equal(needsSourceForClaims("The market fell 2% yesterday"),true);
  assert.equal(needsSourceForClaims("Inflation reached 2.5%"),true);
  assert.equal(needsSourceForClaims("Rates are at 3 percent"),true);
  assert.equal(needsSourceForClaims("An unsourced opinion without numbers"),false);
  const sourced=composeTopicDraft({topic:"Oil prices",angle:"short",
    observation:"Brent crude is $116 per barrel",
    sourceUrl:"https://publisher.example/market/oil"});
  assert.equal(sourced.valid,true,sourced.message);
  assert.ok(sourced.text.endsWith("https://publisher.example/market/oil"));
  assert.equal(reviewTopicDraft(sourced.text.replace("https://publisher.example/market/oil",""),
    {sourceUrl:"https://publisher.example/market/oil"}).valid,false);
});
test("unsafe sources and very long edits do not become copy-ready",()=>{
  assert.equal(composeTopicDraft({topic:"Tech",sourceUrl:"javascript:alert(1)"}).valid,false);
  assert.equal(composeTopicDraft({topic:"Tech",sourceUrl:"http://unsafe.example"}).valid,false);
  assert.equal(composeTopicDraft({topic:"Tech",sourceUrl:"https://user:pass@example.com/story"}).valid,false);
  assert.equal(composeTopicDraft({topic:""}).valid,false);
  const long=composeTopicDraft({topic:"Market mood",observation:"a".repeat(500)});
  assert.equal(long.valid,false);
  assert.match(long.message,/280-character/);
  assert.equal(reviewTopicDraft("X".repeat(1001)).valid,false);
});
