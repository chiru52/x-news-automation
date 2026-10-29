"""No-framework private editorial inbox UI.

All untrusted GitHub Issue fields render through textContent/value only. No
external JavaScript, analytics, remote images, or browser-stored credentials.
"""
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Private X Editorial Inbox</title>
<link rel="stylesheet" href="/dashboard.css">
<script src="/dashboard.js" defer></script>
</head>
<body>
<header>
  <div><p class="eyebrow">X News Automation / Private workspace</p>
    <h1>Editorial Inbox</h1><p class="sub">Review AI news stories in one place</p></div>
  <div class="header-actions"><button id="reload" type="button">Refresh GitHub</button>
  <span id="connection" role="status">Connecting…</span></div>
</header>
<main>
  <div class="notice" role="note"><strong>Human review only.</strong> Source excerpts are not independently verified.
  Saving a review or rejecting a story does <strong>not</strong> authorize any X post. No AI or publishing requests happen here.</div>
  <div class="stats" aria-label="Editorial review status">
    <div class="stat"><strong id="total">0</strong><span>AI Drafts</span></div>
    <div class="stat"><strong id="pending">0</strong><span>Pending</span></div>
    <div class="stat"><strong id="reviewed">0</strong><span>Reviewed</span></div>
    <div class="stat"><strong id="rejected">0</strong><span>Rejected</span></div>
  </div>
  <div class="workspace">
    <aside class="rail">
      <div class="filters">
      <label for="search">Search stories</label>
      <input id="search" placeholder="Company, headline, keyword" autocomplete="off">
      <label for="filter">Review status</label>
      <select id="filter"><option value="all">All drafts</option><option value="pending">Pending</option><option value="reviewed">Reviewed</option><option value="rejected">Rejected</option></select>
      </div>
      <div id="stories" class="stories" aria-label="News stories"></div>
      <p id="empty" class="muted"></p>
    </aside>
    <section class="detail" aria-label="Selected draft">
      <div id="landing"><h2>Choose a story to review</h2><p class="muted">Your private AI Drafts appear on the left. Read the evidence and edit the proposed post here.</p></div>
      <div id="review" hidden>
        <div class="story-meta"><span id="current-status" class="pill">Pending</span>
          <a id="issue-link" href="#" target="_blank" rel="noopener noreferrer">Open original private Issue</a></div>
        <h2 id="headline"></h2>
        <div class="proposal"><h3>Original AI draft (unverified)</h3><p id="proposed"></p></div>
        <a id="source-link" href="#" target="_blank" rel="noopener noreferrer">Read original publisher story</a>
        <div class="columns">
          <div><h3>Publisher excerpts</h3><p class="muted">Short, unverified snippets. Open the complete article for context.</p>
            <div id="evidence"></div></div>
          <div><h3>Editorial checks</h3><div id="warnings"></div>
            <details><summary>Copilot's full analysis (untrusted)</summary>
             <pre id="analysis"></pre></details></div>
        </div>
        <div class="edit">
        <h3>Write your reviewed X post</h3>
        <p class="muted">Edits and review labels are saved privately to the original GitHub Issue, not to X.</p>
        <label for="editor">Editable draft</label>
        <textarea id="editor" rows="6" spellcheck="true"></textarea>
        <p id="length" class="hint"></p>
        <label for="decision">Editorial decision</label>
        <select id="decision">
          <option value="pending">Pending — still working</option>
          <option value="reviewed">Reviewed — still NOT approved for publication</option>
          <option value="rejected">Rejected — set aside</option>
        </select>
        <div class="buttons">
          <button id="save" class="primary">Save privately to GitHub</button>
          <button id="copy">Copy edited post</button>
          <button id="reset">Discard unsaved edits</button>
        </div>
        <p id="message" role="status" aria-live="polite"></p>
        </div>
      </div>
    </section>
  </div>
</main>
<footer>Local-only interface at 127.0.0.1. GitHub authentication stays in your computer's gh CLI.
Editorial review and publication approval are separate. No X integration.</footer>
</body></html>"""

STYLE = r""":root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#243147;background:#f5f7fb;color-scheme:light}
*{box-sizing:border-box}body{margin:0}button,input,select,textarea{font:inherit}
header{background:#fff;padding:20px max(20px,calc((100vw - 1260px)/2));border-bottom:1px solid #dde4ef;display:flex;justify-content:space-between;align-items:center;gap:15px}
.eyebrow{text-transform:uppercase;color:#4263a1;font-weight:800;letter-spacing:1.2px;font-size:11px;margin:0 0 5px}
h1{font-size:27px;margin:0}h2{font-size:23px;margin:5px 0 15px}h3{font-size:17px;margin:0 0 7px}
.sub,.muted,.hint{color:#6c778b}header .sub{margin:4px 0}
main{max-width:1280px;margin:0 auto;padding:20px}
.notice{background:#fff9ec;border:1px solid #f1ddb0;padding:13px 16px;border-radius:10px;margin-bottom:15px;line-height:1.55}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:15px}
.stat{background:white;border:1px solid #e0e6f0;border-radius:12px;padding:14px}
.stat strong{display:block;font-size:26px}.stat span{color:#6c778b;font-size:13px}
.workspace{display:grid;grid-template-columns:minmax(280px,340px) minmax(0,1fr);gap:15px;align-items:start}
.rail,.detail{background:#fff;border:1px solid #e0e6f0;border-radius:13px;min-height:490px}
.rail{overflow:hidden}.detail{padding:23px}
.filters{padding:15px;border-bottom:1px solid #e0e6f0;display:grid;gap:7px}
.filters label,.edit label{font-size:13px;font-weight:700}
input,textarea,select{width:100%;border:1px solid #cdd6e5;background:white;color:#243147;padding:10px;border-radius:8px;min-width:0}
textarea{resize:vertical;line-height:1.5}
.stories{max-height:70vh;overflow:auto}
.story{padding:13px 15px;border:0;border-bottom:1px solid #e7edf5;width:100%;background:white;text-align:left;cursor:pointer;display:block}
.story strong{display:block;line-height:1.35;font-size:14px;margin:6px 0}
.story small{display:block;color:#64748b}
.story:hover,.story.active{background:#eff4ff}.story.active{border-left:4px solid #2555a5;padding-left:11px}
.pill{display:inline-block;color:#334566;background:#e9eef8;border-radius:20px;padding:4px 10px;font-size:12px;font-weight:800}
.pill.reviewed{color:#176344;background:#e3f5ea}.pill.rejected{color:#a33346;background:#ffedf0}
.story-meta{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:14px}
a{color:#1b50a2;text-underline-offset:3px;overflow-wrap:anywhere}
.columns{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin:25px 0}
.proposal{background:#f3f6fc;border:1px solid #e1e7f1;border-radius:9px;padding:14px;margin:12px 0}.proposal p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.6;margin:0}
.excerpt{padding:12px;border:1px solid #e1e7f1;border-radius:8px;margin:9px 0}
.excerpt strong{font-size:12px;color:#425b82}
.excerpt p{white-space:pre-wrap;line-height:1.5;font-size:13px;margin:7px 0 0;overflow-wrap:anywhere}
.alert{background:#fff4eb;border:1px solid #efd4bd;padding:12px;border-radius:8px;font-size:13px;margin-bottom:10px;overflow-wrap:anywhere}
.note{background:#f2f6fb;padding:12px;border-radius:8px;font-size:13px;overflow-wrap:anywhere}
details{border:1px solid #e1e7f1;border-radius:8px;padding:11px;margin-top:12px}
summary{cursor:pointer;font-size:13px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}
.edit{border-top:1px solid #e1e7f1;padding-top:20px}
.edit label{display:block;margin:14px 0 5px}
.hint{font-size:12px;margin:5px 0}.hint.over{color:#bc293c}
.buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:15px}
button{padding:9px 13px;border:1px solid #cdd6e5;background:white;color:#243147;border-radius:8px;cursor:pointer}
button.primary{background:#2251a3;color:white;border-color:#2251a3}button:disabled{opacity:.5;cursor:not-allowed}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:3px solid #80a6ea;outline-offset:2px}
.header-actions{display:flex;gap:12px;align-items:center;font-size:12px;color:#66748b}
#message{font-size:13px;font-weight:600;min-height:18px}#message.error{color:#a31e37}#message.success{color:#176344}
footer{max-width:1280px;margin:0 auto;padding:8px 20px 28px;color:#6c778b;font-size:12px}
@media(max-width:820px){.workspace{grid-template-columns:1fr}.rail,.detail{min-height:0}.stories{max-height:260px}.columns{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}header{align-items:flex-start;flex-direction:column}.detail{padding:16px}}
"""

SCRIPT = r"""'use strict';
(() => {
  let issues = [], csrf = '', selected = null, drafts = new Map(), dirty = new Set();
  const $ = id => document.getElementById(id);
  const text = (el, value) => { el.textContent = String(value == null ? '' : value); return el; };
  const node = (tag, value, className) => {
    const e = document.createElement(tag); text(e,value); if(className)e.className=className; return e;
  };
  const approx = text => [...String(text).replace(/https?:\/\/\S+/gi,'x'.repeat(23))].length;
  const safeUrl = address => {
    try{const u=new URL(address);return u.protocol==='https:' ? u.href : null}catch(_){return null}
  };
  const label = status => status === 'reviewed' ? 'Reviewed' : status === 'rejected' ? 'Rejected' : 'Pending';
  const putMessage = (value, type='') => {text($('message'),value);$('message').className=type;};
  const stateFor = issue => drafts.has(issue.number)
    ? drafts.get(issue.number)
    : {draft: issue.edited_draft, status: issue.status};
  const choose = number => {
    if(selected !== null && dirty.has(selected)) {
      drafts.set(selected,{draft:$('editor').value,status:$('decision').value});
    }
    selected=number;render();
  };
  const stat = () => {
    text($('total'),issues.length);
    for(const status of ['pending','reviewed','rejected']){
      text($(status),issues.filter(i=>i.status===status).length);
    }
  };
  function renderList(){
    const container=$('stories');container.replaceChildren();
    const term=$('search').value.toLowerCase().trim();
    const status=$('filter').value;
    const visible=issues.filter(i=>(status==='all'||i.status===status) &&
      (!term || [i.title,i.source_url,i.analysis].join(' ').toLowerCase().includes(term)));
    for(const issue of visible){
      const row=node('button','', 'story'+(issue.number===selected?' active':''));
      row.type='button';
      row.append(node('small','#'+issue.number+' · '+label(issue.status)
        +(dirty.has(issue.number)?' · Unsaved':'')));
      row.append(node('strong',issue.title));
      row.append(node('small',issue.source_url.replace(/^https:\/\//,'')));
      row.addEventListener('click',()=>choose(issue.number));
      container.append(row);
    }
    text($('empty'),visible.length?'':'No draft matches this filter.');
    stat();
  }
  function render(){
    renderList();
    const issue=issues.find(i=>i.number===selected);
    $('review').hidden=!issue;$('landing').hidden=!!issue;
    if(!issue)return;
    const edit=stateFor(issue);
    text($('current-status'),label(issue.status));
    $('current-status').className='pill '+issue.status;
    text($('headline'),issue.title);
    text($('proposed'),issue.proposed_draft||'No supported AI draft was generated.');
    for(const [element,url] of [[$('issue-link'),issue.url],[$('source-link'),issue.source_url]]){
      const safe=safeUrl(url);
      if(safe){element.href=safe;element.hidden=false}else{element.hidden=true;element.removeAttribute('href')}
    }
    const evidence=$('evidence');evidence.replaceChildren();
    if(!issue.excerpts.length){evidence.append(node('p','No excerpt available. Open the original article.','muted'))}
    for(const item of issue.excerpts){
      const block=node('div','', 'excerpt');
      block.append(node('strong',item.ref+' — publisher excerpt'));
      block.append(node('p',item.text));
      evidence.append(block);
    }
    const warnings=$('warnings');warnings.replaceChildren();
    if(issue.warnings.length){
      for(const warning of issue.warnings){
        warnings.append(node('div',warning,warning.includes('Needs')?'alert':'note'));
      }
    }else{
      warnings.append(node('div','No automated review checks are available; independently verify every claim.','note'));
    }
    text($('analysis'),issue.analysis||'Model analysis unavailable in this older draft.');
    $('editor').value=edit.draft;
    $('decision').value=edit.status;
    updateLength();
    putMessage(dirty.has(issue.number)?'Unsaved changes — click Save privately to GitHub.':'');
  }
  function updateLength(){
    const value=$('editor').value;
    const length=approx(value);
    text($('length'),'Approximate X length: '+length+' / 280 · '+value.length+
      ' raw characters. Verify formatting on X; no publishing here.');
    $('length').className='hint'+(length>280?' over':'');
  }
  async function load(){
    text($('connection'),'Loading…');
    try{
      const response=await fetch('/api/inbox',{cache:'no-store'});
      if(!response.ok)throw Error('Unable to read private drafts. Check gh auth status.');
      const data=await response.json();
      if(!Array.isArray(data.issues)||!data.csrf)throw Error('Unexpected inbox response');
      issues=data.issues;csrf=data.csrf;
      if(selected===null || !issues.some(i=>i.number===selected))selected=issues[0]?.number??null;
      for(const number of Array.from(drafts.keys()))if(!issues.some(i=>i.number===number))drafts.delete(number);
      text($('connection'),'Connected · private GitHub');
      render();
    }catch(err){text($('connection'),'Unable to connect');putMessage(err.message,'error')}
  }
  function editChanged(){
    if(selected===null)return;
    dirty.add(selected);
    drafts.set(selected,{draft:$('editor').value,status:$('decision').value});
    updateLength();renderList();putMessage('Unsaved changes — save privately to GitHub.');
  }
  $('editor').addEventListener('input',editChanged);
  $('decision').addEventListener('change',editChanged);
  $('search').addEventListener('input',renderList);
  $('filter').addEventListener('change',renderList);
  $('reload').addEventListener('click',()=>{
    if(dirty.size && !confirm('Discard all unsaved changes and reload from GitHub?'))return;
    dirty.clear();drafts.clear();load();
  });
  $('reset').addEventListener('click',()=>{
    if(selected===null)return;
    drafts.delete(selected);dirty.delete(selected);render();
  });
  $('copy').addEventListener('click',async()=>{
    if(!$('editor').value.trim())return putMessage('No draft to copy','error');
    try{await navigator.clipboard.writeText($('editor').value);
      putMessage('Copied locally. This does not post to X.','success');
    }catch(_){putMessage('Clipboard unavailable — select the text manually.','error')}
  });
  $('save').addEventListener('click',async()=>{
    const issue=issues.find(i=>i.number===selected);
    if(!issue)return;
    const draft=$('editor').value, status=$('decision').value;
    if(status==='reviewed' && !draft.trim())
      return putMessage('A reviewed story needs an edited post.','error');
    if(draft.length>1200)return putMessage('Editor text exceeds 1,200 characters.','error');
    $('save').disabled=true;putMessage('Saving private GitHub review…');
    try{
      const response=await fetch('/api/review',{
        method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
        body:JSON.stringify({number:issue.number,revision:issue.revision,draft,status})
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.error||'Could not save review');
      const idx=issues.findIndex(i=>i.number===issue.number);
      issues[idx]=data.issue;
      drafts.delete(issue.number);dirty.delete(issue.number);
      render();putMessage('Saved to private GitHub Issue. Not published.','success');
    }catch(err){putMessage(err.message,'error')}finally{$('save').disabled=false}
  });
  window.addEventListener('beforeunload',event=>{
    if(dirty.size){event.preventDefault();event.returnValue=''}
  });
  load();
})();"""
