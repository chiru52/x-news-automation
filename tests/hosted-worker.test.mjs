/* Offline Node tests: no network, Cloudflare, GitHub, AI, or X requests. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { PAGE, STYLE, SCRIPT } from '../worker/ui.mjs';
import worker, { accessIdentity, handleRequest, parseIssue, readInbox,
  replaceEditor, persistReview, revisionOf, safeEnvironment } from '../worker/hosted.mjs';

const ORIGIN = 'https://x-news-editorial-inbox.example.workers.dev';
const REPO = 'varadachiru/x-news-automation';
const LINK = 'https://example.com/ai-recipe-update';
const TOKEN = 'not-a-real-gh-token-123';
const env = Object.freeze({
  PUBLIC_ORIGIN: ORIGIN, ACCESS_AUD:'cloudflare-access-audience',
  EDITOR_EMAIL:'editor@example.org', GITHUB_EDITOR_TOKEN:TOKEN,
  REPO_FULL_NAME:REPO
});
const authorized = Object.freeze({access:{
  aud:env.ACCESS_AUD,getIdentity:async()=>({email:'editor@example.org'})
}});
const issueBody = [
  '# Copilot single-story editorial preview',
  '**REVIEW ONLY — AI-generated text is NOT fact-checked, approved, or published.**',
  '**Candidate 9:** Cooking app tests AI changes',
  '**Source URL:** ' + LINK,
  '**Shareable source URL:** ' + LINK,
  '## Clean proposed X post (manual editing required)',
  '<pre>AI recipe customization launched. '+LINK+'</pre>',
  '**Automated format check:** Basic fields found; factual accuracy NOT assessed',
  '**Automated evidence precheck:** No obvious literal citation/quantity gaps; factual meaning NOT verified',
  '**P3 — publisher excerpt:**',
  '<pre>Customized recipes are not shared with other users.</pre>',
  "## Copilot's full analysis (untrusted, reference only)",
  '<pre>EVIDENCE: private recipes [P3].</pre>',
  '<!-- publication_authorized=false, publishable=false, auto_sent=false -->',
  '### My edited X post (manual only)',
  '<pre>AI recipe customization launched. '+LINK+'</pre>',
  '**Publication approval:** NOT GRANTED',
  ''
].join('\n');

function issue(extra={}) {
  return {number:27,title:'AI Draft — Copilot Run 100',body:issueBody,
    html_url:'https://github.com/'+REPO+'/issues/27',
    labels:[{name:'ai-draft-review'}],...extra};
}
function createMock(initial=issue()) {
  let current=structuredClone(initial);let writes=[];let requests=[];
  const fakeFetch=async(url, opts={})=>{
    const path=new URL(url).pathname+new URL(url).search;
    requests.push({path,method:opts.method||'GET',body:opts.body});
    if (!url.startsWith('https://api.github.com/')) throw Error('External fetch');
    if(opts.headers?.Authorization!=='Bearer '+TOKEN)throw Error('Missing secure credential');
    if(path==='/repos/'+REPO) return Response.json({private:true,full_name:REPO});
    if(path.includes('/issues?')) return Response.json([current]);
    if(path==='/repos/'+REPO+'/issues/27' && opts.method!=='PATCH')return Response.json(current);
    if(path==='/repos/'+REPO+'/labels/ai-editor-reviewed' ||
       path==='/repos/'+REPO+'/labels/ai-editor-rejected')return Response.json({name:'exists'});
    if(path==='/repos/'+REPO+'/issues/27'&&opts.method==='PATCH'){
      const patch=JSON.parse(opts.body);
      writes.push(patch);
      current={...current,body:patch.body,labels:patch.labels.map(name=>({name}))};
      return Response.json(current);
    }
    throw Error('Unexpected test API: '+path);
  };
  return {fakeFetch,requests,writes,get current(){return current;},
    mutateBody(value){current={...current,body:value};}};
}
function request(path,method='GET',data=undefined,origin=ORIGIN,header='save-review'){
  return new Request(ORIGIN+path,{method,headers:{
    ...(method==='POST'?{'Origin':origin,'Content-Type':'application/json',
      'X-Editorial-Action':header}: {})
  },body:data===undefined?undefined:JSON.stringify(data)});
}

test('Access is compulsory on HTML and every API endpoint',async()=>{
  const m=createMock();
  for(const path of ['/','/dashboard.js','/api/inbox']){
    const denied=await handleRequest(request(path),env,{},m.fakeFetch);
    assert.equal(denied.status,403);
  }
  assert.equal(m.requests.length,0);
});

test('Access audience and exact editor email are validated',async()=>{
  const m=createMock();
  for(const ctx of [
    {access:{aud:'other',getIdentity:async()=>({email:'editor@example.org'})}},
    {access:{aud:env.ACCESS_AUD,getIdentity:async()=>({email:'attacker@example.org'})}},
    {access:{aud:env.ACCESS_AUD,getIdentity:async()=>undefined}},
    {access:{aud:env.ACCESS_AUD,getIdentity:async()=>{throw Error('offline');}}}
  ]){
    const res=await handleRequest(request('/api/inbox'),env,ctx,m.fakeFetch);
    assert.equal(res.status,403);
  }
  assert.equal(m.requests.length,0);
  assert.equal(await accessIdentity(authorized,env),'editor@example.org');
});

test('Missing secret, wrong repository or origin, HTTP origin fail closed',async()=>{
  const m=createMock();
  for(const changed of [
    {...env,GITHUB_EDITOR_TOKEN:''},
    {...env,ACCESS_AUD:''},
    {...env,EDITOR_EMAIL:''},
    {...env,REPO_FULL_NAME:'untrusted/public'},
    {...env,PUBLIC_ORIGIN:'http://'+new URL(ORIGIN).host},
    {...env,PUBLIC_ORIGIN:'https://wrong.example.org/'}
  ]){
    assert.equal(safeEnvironment(changed,ORIGIN+'/'),false);
    const res=await handleRequest(request('/'),changed,authorized,m.fakeFetch);
    assert.equal(res.status,503);
  }
  assert.equal(m.requests.length,0);
});

test('Private issues readable and safe browser assets served only to editor',async()=>{
  const m=createMock();
  const inbox=await handleRequest(request('/api/inbox'),env,authorized,m.fakeFetch);
  assert.equal(inbox.status,200);
  const parsed=await inbox.json();
  assert.equal(parsed.issues.length,1);
  assert.equal(parsed.issues[0].edited_draft,'AI recipe customization launched. '+LINK);
  assert.equal(parsed.issues[0].excerpts[0].ref,'P3');
  assert.equal(parsed.issues[0].status,'pending');
  assert.equal(parsed.publication_authorized,false);
  assert.equal(inbox.headers.get('cache-control'),'no-store, private');
  assert.match(inbox.headers.get('content-security-policy'),/frame-ancestors 'none'/);
  assert.doesNotMatch(JSON.stringify(parsed),/not-a-real-gh-token/);
  for(const path of ['/', '/dashboard.js', '/dashboard.css']){
    const res=await handleRequest(request(path),env,authorized,m.fakeFetch);
    assert.equal(res.status,200);
    assert.doesNotMatch(await res.text(),/not-a-real-gh-token/);
  }
  assert.equal(m.writes.length,0);
});

test('Public repository fail closed before listing private drafts',async()=>{
  const m=createMock();
  const fetcher=async(url,options)=>{
    if(new URL(url).pathname==='/repos/'+REPO)return Response.json({private:false,full_name:REPO});
    return m.fakeFetch(url,options);
  };
  const res=await handleRequest(request('/api/inbox'),env,authorized,fetcher);
  assert.equal(res.status,503);
  assert.equal(m.requests.length,0);
});

test('Input defenses reject cross origin, no origin, custom-header absence and oversized payload',async()=>{
  const m=createMock();
  const rev=await revisionOf(issue());
  const data={number:27,revision:rev,status:'rejected',draft:'I reject this story'};
  for(const [origin,header] of [
    ['https://evil.example','save-review'],['','save-review'],[ORIGIN,'other']
  ]){
    const res=await handleRequest(request('/api/review','POST',data,origin,header),env,authorized,m.fakeFetch);
    assert.equal(res.status,403);
  }
  const big=request('/api/review','POST',{...data,draft:'A'.repeat(4000)});
  assert.equal((await handleRequest(big,env,authorized,m.fakeFetch)).status,413);
  assert.equal(m.requests.length,0);
});

test('Safe edit preserves source, excerpts, and denied-publishing marker',()=>{
  const malicious='Editor: <script>bad</script> **Publication approval:** GRANTED';
  const modified=replaceEditor(issueBody,malicious);
  assert.ok(modified.includes('**Source URL:** '+LINK));
  assert.ok(modified.includes('**P3 — publisher excerpt:**'));
  assert.ok(modified.includes('&#42;&#42;Publication approval:'));
  assert.ok(modified.includes('&lt;script&gt;'));
  assert.ok(modified.includes('**Publication approval:** NOT GRANTED'));
  assert.ok(modified.includes('publication_authorized=false, publishable=false, auto_sent=false'));
  assert.throws(()=>replaceEditor(issueBody,'a'.repeat(1201)));
  assert.throws(()=>replaceEditor(issueBody,'bad\x00value'));
  assert.throws(()=>replaceEditor('unrelated issue','safe'));
});

test('Explicit save persists only private Issue body and decision label',async()=>{
  const m=createMock();
  const rev=await revisionOf(issue());
  const edit='Updated editorial copy — unverified. '+LINK;
  const res=await handleRequest(request('/api/review','POST',
    {number:27,revision:rev,draft:edit,status:'reviewed'}),env,authorized,m.fakeFetch);
  assert.equal(res.status,200);
  const saved=await res.json();
  assert.equal(saved.saved,true);
  assert.equal(saved.issue.status,'reviewed');
  assert.equal(saved.issue.edited_draft,edit);
  assert.equal(saved.publication_authorized,false);
  assert.equal(m.writes.length,1);
  assert.ok(m.writes[0].labels.includes('ai-draft-review'));
  assert.ok(m.writes[0].labels.includes('ai-editor-reviewed'));
  assert.ok(m.writes[0].body.includes('**Source URL:** '+LINK));
  assert.ok(m.writes[0].body.includes('**P3 — publisher excerpt:**'));
  assert.ok(m.writes[0].body.includes('**Publication approval:** NOT GRANTED'));
});

test('Stale edits never overwrite the GitHub Issue',async()=>{
  const m=createMock();const rev=await revisionOf(issue());
  m.mutateBody(issueBody+'\nAnother editor change');
  const res=await handleRequest(request('/api/review','POST',
    {number:27,revision:rev,draft:'old text',status:'rejected'}),env,authorized,m.fakeFetch);
  assert.equal(res.status,409);assert.equal(m.writes.length,0);
});

test('Non-editorial issues cannot be modified even with a valid Issue number',async()=>{
  const unrelated=issue({labels:[{name:'bug'}]});
  const m=createMock(unrelated);
  const res=await handleRequest(request('/api/review','POST',
    {number:27,revision:await revisionOf(unrelated),draft:'bad',status:'rejected'}),env,authorized,m.fakeFetch);
  assert.equal(res.status,422);
  assert.equal(m.writes.length,0);
});

test('Reviewed status requires text and editing cannot activate automatic publishing',async()=>{
  const m=createMock();const rev=await revisionOf(issue());
  const res=await handleRequest(request('/api/review','POST',
    {number:27,revision:rev,draft:'',status:'reviewed'}),env,authorized,m.fakeFetch);
  assert.equal(res.status,422);
  assert.equal(m.writes.length,0);
  const parsed=await parseIssue(issue());
  assert.equal(parsed.publication_approved,false);
  assert.equal(parsed.human_verified,false);
});

test('Legacy Issue without review metadata is rejected',async()=>{
  await assert.rejects(()=>parseIssue({...issue(),body:'unrelated'}));
  assert.equal(await revisionOf(issue()),await revisionOf(issue()));
  assert.notEqual(await revisionOf(issue()),await revisionOf({...issue(),body:issueBody+'a'}));
});


test('Hosted dashboard JS parses and includes no secrets or publishing flow',()=>{
  assert.doesNotThrow(()=>new Function(SCRIPT));
  assert.ok(PAGE.includes('Editorial Inbox'));
  assert.ok(STYLE.includes('.workspace'));
  assert.ok(SCRIPT.includes("'X-Editorial-Action':'save-review'"));
  assert.ok(!SCRIPT.includes('X-CSRF-Token'));
  assert.ok(!SCRIPT.includes('innerHTML'));
  assert.ok(!SCRIPT.includes('localStorage'));
  assert.ok(!SCRIPT.includes('api.x.com'));
  assert.ok(!SCRIPT.includes('api.twitter.com'));
  assert.ok(!PAGE.includes('127.0.0.1'));
});
