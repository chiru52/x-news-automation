import test from "node:test";
import assert from "node:assert/strict";
import {
  nextFeedCheckAt, shouldCheckAfterReturn,
  FEED_CHECK_INTERVAL_MS, FEED_CHECK_LAG_MS, MAX_JITTER_MS
} from "../dashboard/refresh-clock.mjs";

const at = (time) => Date.parse("2026-10-30T" + time + ":00Z");
test("collector schedule and browser checks align to quarter-hour plus grace", () => {
  assert.equal(FEED_CHECK_INTERVAL_MS,15*60*1000);
  assert.equal(FEED_CHECK_LAG_MS,2*60*1000);
  assert.equal(nextFeedCheckAt(at("09:13")),at("09:17"));
  assert.equal(nextFeedCheckAt(at("09:28")),at("09:32"));
  assert.equal(nextFeedCheckAt(at("09:17")),at("09:32"));
  assert.equal(nextFeedCheckAt(at("09:59")),at("10:02"));
});
test("browser checks don't wait 15 more minutes after arrival just before cron",()=>{
  assert.equal(nextFeedCheckAt(at("09:14")),at("09:17"));
  assert.equal(nextFeedCheckAt(at("09:29")),at("09:32"));
  assert.ok(nextFeedCheckAt(at("09:13"))-at("09:13")<15*60*1000);
});
test("bounded jitter spreads clients without adding extra fetches per cycle",()=>{
  assert.equal(nextFeedCheckAt(at("09:13"),30000),at("09:17")+30000);
  assert.equal(nextFeedCheckAt(at("09:13"),1e6),at("09:17")+MAX_JITTER_MS);
  assert.equal(nextFeedCheckAt(at("09:13"),-900),at("09:17"));
  assert.equal(nextFeedCheckAt(at("09:13"),Number.NaN),at("09:17"));
  assert.equal(nextFeedCheckAt(at("09:28"),45000),at("09:32")+45000);
});
test("visible-tab resume is throttled and returns after a pause are checked",()=>{
  const now=at("10:29");
  assert.equal(shouldCheckAfterReturn(now,at("10:28")),false);
  assert.equal(shouldCheckAfterReturn(now,at("10:15")),true);
  assert.equal(shouldCheckAfterReturn(now,0),true);
  assert.equal(shouldCheckAfterReturn(now,now),false);
  assert.equal(shouldCheckAfterReturn(Number.NaN,0),false);
});
test("bad wall-clock input fails closed",()=>{
  assert.throws(()=>nextFeedCheckAt(Number.NaN),RangeError);
  assert.throws(()=>nextFeedCheckAt(-1),RangeError);
});
