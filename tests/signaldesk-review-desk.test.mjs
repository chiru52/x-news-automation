import test from "node:test";
import assert from "node:assert/strict";
import {reviewCandidates,reviewPost,reviewCounts} from "../dashboard/review-desk.mjs";
const validUrl="https://example.com/article";
const mk=(id,kind="news")=>({
  id:"news:"+id,kind,title:"Source-reported technology item "+id,
  source_url:validUrl,published_at:"2026-10-30T12:00:00Z",post:"Publisher headline\n\n"+validUrl
});
const a=mk("aaaaaaaaaaaaaaaaaaaaaaaa"),b=mk("bbbbbbbbbbbbbbbbbbbbbbbb"),
 c=mk("cccccccccccccccccccccccc"),draft={...mk("dddddddddddddddddddddddd","draft"),kind:"draft"};
const status=new Map([[a.id,"reviewing"],[b.id,"ready"],[c.id,"copied"]]);
const stage=item=>status.get(item.id)||"new";
test("review queue includes only prepared, in-review, ready, or edited drafts",()=>{
  const entries=[a,b,c,draft,mk("eeeeeeeeeeeeeeeeeeeeeeee"),
    {...a,id:"news:old",history_only:true},
    {...a,id:"news:bad",source_url:"javascript:alert(1)"}];
  assert.deepEqual(reviewCandidates(entries,stage,new Map(),new Map()).map(x=>x.id),
    [b.id,a.id,draft.id]);
  const edited=mk("ffffffffffffffffffffffff");
  assert.ok(reviewCandidates([...entries,edited],stage,new Map([[edited.id,"Edited"]]),new Map())
    .some(x=>x.id===edited.id));
  assert.equal(reviewCandidates([a,a],stage,new Map(),new Map()).length,1);
});
test("review desk validates per-post source URL and approximate 280 X characters",()=>{
  const ok=reviewPost("A source attributed summary\n\n"+validUrl,validUrl);
  assert.equal(ok.valid,true);
  assert.match(ok.message,/Verify the claims/);
  assert.match(reviewPost("Article without a link",validUrl).message,/Include the original/);
  assert.match(reviewPost("x".repeat(300)+"\n"+validUrl,validUrl).message,/Shorten/);
  assert.equal(reviewPost("",validUrl).valid,false);
  assert.equal(reviewPost("Fine https://example.com/article","http://example.com/article").valid,false);
});
test("review queue totals ignore copied and archived stories",()=>{
  const items=reviewCandidates([a,b,c,draft],stage,new Map(),new Map());
  assert.deepEqual(reviewCounts(items,stage),{total:3,reviewing:1,ready:1});
});
test("thread draft entries can make a story reviewable without changing workflow stage",()=>{
  const story=mk("ffffffffffffffffffffffff");
  const matched=reviewCandidates([story],stage,new Map(),new Map([[story.id,["1","2","3"]]]));
  assert.equal(matched.length,1);
});
