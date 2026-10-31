import test from "node:test";
import assert from "node:assert/strict";
import {describeIndiaCoverage} from "../dashboard/coverage-note.mjs";
const news=(publisher)=>({kind:"news",publisher});
test("India coverage describes eligible source diversity without claiming complete India news",()=>{
  const s=describeIndiaCoverage({items:[news("Publisher A"),news("Publisher A"),news("Publisher B")],fromLive:true,coverage:{india_sources_failed:1}});
  assert.match(s,/3 India stories from 2 publishers/);
  assert.match(s,/Latest live collector snapshot/);
  assert.match(s,/1 India-focused feed reported unavailable/);
  assert.match(s,/News Archive/);
  assert.doesNotMatch(s,/all Indian news|verified|guaranteed/i);
});
test("India coverage notes fallback, copied records and active filters honestly",()=>{
  const s=describeIndiaCoverage({items:[],copiedItems:[news("Publisher A")],filtered:true});
  assert.match(s,/No currently available India stories/);
  assert.match(s,/Daily fallback snapshot/);
  assert.match(s,/1 India article is in Copied Articles/);
  assert.match(s,/filters may reduce/);
});
test("India coverage avoids invented source outage diagnostics when unavailable",()=>{
  const s=describeIndiaCoverage({items:[news("A")],fromLive:false,coverage:{india_sources_failed:4}});
  assert.match(s,/1 India story from 1 publisher/);
  assert.doesNotMatch(s,/4 India-focused feeds/);
});

test("India source health counts are labelled as dedicated feeds, not all India coverage",()=>{
  const text=describeIndiaCoverage({
    items:[news("India Publisher")],fromLive:true,
    coverage:{india_sources_checked:2,india_sources_with_recent_stories:1,india_sources_failed:1}
  });
  assert.match(text,/1\/2 dedicated India feeds supplied recent eligible stories/);
  assert.match(text,/1 India-focused feed reported unavailable/);
  assert.doesNotMatch(text,/all sources|complete coverage/i);
});
