/* Cloudflare Access-protected editorial review for a private GitHub repository.
 * No Node server, no browser GitHub token, no AI calls, no X publishing.
 * A Cloudflare Access Worker policy must be configured; no token-only fallback.
 */
import { PAGE, STYLE, SCRIPT } from './ui.mjs';

const GH_BASE = 'https://api.github.com';
const MAX_BODY = 40000;
const MAX_DRAFT = 1200;
const MAX_REQUEST = 3600;
const MAX_ISSUES = 300;
const STATUS_LABEL = Object.freeze({
  reviewed: 'ai-editor-reviewed',
  rejected: 'ai-editor-rejected'
});
const ALL_STATUSES = ['pending', 'reviewed', 'rejected'];
const EDIT_REGION = /(### My edited X post \(manual only\)\s*\n)([\s\S]*?)(\n\*\*Publication approval:\*\* NOT GRANTED\b)/;
const PUBLICATION_DENIED = '**Publication approval:** NOT GRANTED';
const HISTORY_MARKER = 'publication_authorized=false, publishable=false, auto_sent=false';

function response(body, status=200, kind='application/json; charset=utf-8') {
  const value = typeof body === 'string' ? body : JSON.stringify(body);
  return new Response(value, {status, headers: {
    'Content-Type': kind, 'Cache-Control': 'no-store, private',
    'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer', 'Cross-Origin-Resource-Policy':'same-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
  }});
}
const fail = (code, message) => response({error: message, publication_authorized: false}, code);
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

export function safeEnvironment(env, url) {
  if (!env || typeof env !== 'object') return false;
  const mandatory = ['PUBLIC_ORIGIN', 'EDITOR_EMAIL', 'ACCESS_AUD', 'GITHUB_EDITOR_TOKEN', 'REPO_FULL_NAME'];
  if (mandatory.some(k => typeof env[k] !== 'string' || !env[k].trim())) return false;
  if (env.REPO_FULL_NAME !== 'varadachiru/x-news-automation') return false;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(env.EDITOR_EMAIL.trim())) return false;
  try {
    const origin = new URL(env.PUBLIC_ORIGIN);
    return origin.protocol === 'https:' && !origin.username && !origin.password &&
      origin.pathname === '/' && !origin.search && !origin.hash &&
      env.PUBLIC_ORIGIN === origin.origin && new URL(url).origin === origin.origin;
  } catch (_) { return false; }
}

export async function accessIdentity(ctx, env) {
  if (!ctx?.access || ctx.access.aud !== env.ACCESS_AUD ||
      typeof ctx.access.getIdentity !== 'function') return null;
  try {
    const identity = await ctx.access.getIdentity();
    const email = typeof identity?.email === 'string' ? identity.email.toLowerCase().trim() : '';
    return email && email === env.EDITOR_EMAIL.toLowerCase().trim() ? email : null;
  } catch (_) { return null; }
}

export async function ghRequest(env, path, options={}, transport=fetch) {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('..') || path.includes('#')) {
    throw new Error('Invalid GitHub API path');
  }
  const res = await transport(GH_BASE + path, {
    method: options.method || 'GET',
    headers: {
      'Authorization': 'Bearer ' + env.GITHUB_EDITOR_TOKEN,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'Private-X-Editorial-Worker/1.0',
      ...(options.body ? {'Content-Type': 'application/json'} : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    redirect: 'error'
  });
  if (!res.ok) throw new Error('GitHub API error ' + res.status);
  return res.json();
}

export async function assertPrivate(env, transport=fetch) {
  const repo = await ghRequest(env, '/repos/' + env.REPO_FULL_NAME, {}, transport);
  if (repo?.private !== true || repo?.full_name?.toLowerCase() !==
      env.REPO_FULL_NAME.toLowerCase()) throw new Error('Repository must be private');
}

const escapeHTML = value => String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;')
  .replace(/\*/g,'&#42;');
export function unescapeHTML(value) {
  return String(value).replace(/&(?:amp|lt|gt|quot|#x27|#39|#42);/gi, entity => ({
    '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'",
    '&#39;': "'", '&#42;': '*'
  })[entity.toLowerCase()] ?? entity);
}
const match = (rx, value, max=1500) => {
  const result = rx.exec(value);
  return result ? unescapeHTML(result[1]).trim().slice(0,max) : '';
};
const labelNames = issue => Array.isArray(issue.labels) ?
  issue.labels.map(x => typeof x === 'string' ? x : x?.name).filter(x=>typeof x === 'string') : [];
export function reviewStatus(issue) {
  const labels = labelNames(issue);
  return labels.includes(STATUS_LABEL.rejected) ? 'rejected' :
    labels.includes(STATUS_LABEL.reviewed) ? 'reviewed' : 'pending';
}
export async function revisionOf(issue) {
  const value = JSON.stringify([issue.body, [...labelNames(issue)].sort()]);
  const sum = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(sum), b=>b.toString(16).padStart(2,'0')).join('');
}

export async function parseIssue(issue) {
  const body = issue?.body;
  if (typeof body !== 'string' || new TextEncoder().encode(body).length > MAX_BODY ||
      !body.includes(HISTORY_MARKER) || !body.includes(PUBLICATION_DENIED) ||
      !body.includes('**REVIEW ONLY') || !EDIT_REGION.test(body) ||
      !Number.isSafeInteger(issue.number)) throw new Error('Invalid private AI Issue');
  const source = match(/^\*\*Source URL:\*\*\s*(https?:\/\/[^\s<]+)/m, body, 2500);
  let address;
  try { address = new URL(source); } catch (_) { throw new Error('Invalid publisher URL'); }
  if (address.protocol !== 'https:' || !address.hostname || address.username ||
      address.password || source.match(/\s/)) throw new Error('Unsafe publisher URL');
  const excerpts = [...body.matchAll(/\*\*(P\d+) — publisher excerpt:\*\*\s*<pre>([\s\S]*?)<\/pre>/g)]
    .slice(0,4).map(m=>({ref:m[1], text:unescapeHTML(m[2]).trim().slice(0,250)}));
  const editor = EDIT_REGION.exec(body)[2];
  return {
    number: issue.number,
    title: match(/^\*\*Candidate \d+:\*\*\s*(.+)/m, body, 400) ||
      String(issue.title || '').slice(0,400),
    url: 'https://github.com/' + 'varadachiru/x-news-automation/issues/' + issue.number,
    source_url: source,
    proposed_draft: match(/## Clean proposed X post \(manual editing required\)\s*<pre>([\s\S]*?)<\/pre>/,body,MAX_DRAFT),
    edited_draft: match(/<pre>([\s\S]*?)<\/pre>/,editor,MAX_DRAFT),
    excerpts, analysis: match(/## Copilot's full analysis \(untrusted, reference only\)\s*<pre>([\s\S]*?)<\/pre>/,body,4000),
    warnings: [
      match(/^\*\*Automated format check:\*\*\s*(.+)/m,body,380),
      match(/^\*\*Automated evidence precheck:\*\*\s*(.+)/m,body,380)
    ].filter(Boolean),
    status:reviewStatus(issue),
    revision:await revisionOf(issue),
    human_verified:false, publication_approved:false
  };
}

export async function readInbox(env, transport=fetch) {
  const all = [];
  for (let page=1;page<=4;page++) {
    const chunk = await ghRequest(env,'/repos/'+env.REPO_FULL_NAME+
      '/issues?state=all&labels=ai-draft-review&per_page=100&page='+page,
      {},transport);
    if (!Array.isArray(chunk)) throw new Error('Malformed GitHub list');
    all.push(...chunk.filter(i=>!i.pull_request && labelNames(i).includes('ai-draft-review')));
    if (chunk.length < 100) {
      if (all.length >= MAX_ISSUES) throw new Error('Too many AI issues');
      const result = await Promise.all(all.map(parseIssue));
      return result.sort((a,b)=>b.number-a.number);
    }
  }
  throw new Error('Private AI history exceeds review limit');
}
export function replaceEditor(body, draft) {
  if (typeof body !== 'string' || typeof draft !== 'string' ||
      draft.length > MAX_DRAFT || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(draft) ||
      !body.includes(HISTORY_MARKER) || !body.includes(PUBLICATION_DENIED) ||
      !EDIT_REGION.test(body)) throw new Error('Unsafe editor update');
  const edited = draft.trim() ? '<pre>' + escapeHTML(draft) + '</pre>' :
    '> [No reviewed post entered]';
  const updated = body.replace(EDIT_REGION, (_all,prefix,_old,suffix)=>prefix+edited+suffix);
  if (new TextEncoder().encode(updated).length > MAX_BODY ||
      !updated.includes(HISTORY_MARKER) || !updated.includes(PUBLICATION_DENIED))
    throw new Error('Updated issue is invalid');
  return updated;
}
export async function persistReview(env, payload, transport=fetch) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) ||
      !Number.isSafeInteger(payload.number) || payload.number < 1 ||
      !/^[a-f0-9]{64}$/.test(payload.revision || '') ||
      !ALL_STATUSES.includes(payload.status) || typeof payload.draft !== 'string')
    throw new Error('Invalid editor request');
  if (payload.status === 'reviewed' && !payload.draft.trim())
    throw new Error('Reviewed draft requires text');
  // Never allow a client to name a different repository or edit arbitrary issues.
  const prefix = '/repos/'+env.REPO_FULL_NAME;
  const issue = await ghRequest(env,prefix+'/issues/'+payload.number,{},transport);
  if (!labelNames(issue).includes('ai-draft-review')) throw new Error('Not an AI Draft');
  await parseIssue(issue);
  if (await revisionOf(issue) !== payload.revision) {
    const err = new Error('Issue changed; reload before saving');err.code=409;throw err;
  }
  const body = replaceEditor(issue.body,payload.draft);
  const labels = labelNames(issue).filter(x=>!Object.values(STATUS_LABEL).includes(x));
  if (payload.status !== 'pending') {
    const required = STATUS_LABEL[payload.status];
    try {
      await ghRequest(env,prefix+'/labels/'+required,{},transport);
    } catch (_) {
      // Only create the needed status label during explicit user Save.
      await ghRequest(env,prefix+'/labels',{
        method:'POST',body:{name:required,
          color:payload.status==='reviewed'?'2F855A':'C34D63',
          description:'Private editorial review only — not publishing permission'}
      },transport);
    }
    labels.push(required);
  }
  const updated = await ghRequest(env,prefix+'/issues/'+payload.number,{
    method:'PATCH',body:{body, labels:[...new Set(labels)].sort()}
  },transport);
  if (updated?.body !== body || reviewStatus(updated) !== payload.status)
    throw new Error('GitHub write not confirmed');
  return parseIssue(updated);
}
export async function handleRequest(request, env, ctx, transport=fetch) {
  const pathname = new URL(request.url).pathname;
  // Deny before reading GitHub secrets or serving even the front-end.
  if (!safeEnvironment(env,request.url)) return fail(503,'Dashboard configuration incomplete');
  if (!await accessIdentity(ctx,env)) return fail(403,'Cloudflare Access sign-in required');
  if (!['GET','POST'].includes(request.method)) return fail(405,'Method not allowed');
  if (request.method==='GET' && pathname==='/') return response(PAGE,200,'text/html; charset=utf-8');
  if (request.method==='GET' && pathname==='/dashboard.css') return response(STYLE,200,'text/css; charset=utf-8');
  if (request.method==='GET' && pathname==='/dashboard.js') return response(SCRIPT,200,'application/javascript; charset=utf-8');
  if (request.method==='GET' && pathname==='/api/inbox') {
    try {
      await assertPrivate(env,transport);
      return response({issues:await readInbox(env,transport),publication_authorized:false});
    } catch (_) { return fail(503,'Cannot safely read private GitHub AI Drafts'); }
  }
  if (request.method==='POST' && pathname==='/api/review') {
    const origin = request.headers.get('Origin');
    const fetchSite = request.headers.get('Sec-Fetch-Site');
    if (origin !== env.PUBLIC_ORIGIN || (fetchSite && fetchSite !== 'same-origin') ||
        request.headers.get('X-Editorial-Action') !== 'save-review') return fail(403,'Same-origin review required');
    if (request.headers.get('Content-Type')?.split(';')[0].trim()!=='application/json')
      return fail(415,'JSON required');
    const declared = Number(request.headers.get('Content-Length'));
    if (Number.isFinite(declared) && declared > MAX_REQUEST) return fail(413,'Review request too large');
    const raw = await request.text();
    if (new TextEncoder().encode(raw).length > MAX_REQUEST) return fail(413,'Review request too large');
    let payload;
    try { payload = JSON.parse(raw); } catch (_) { return fail(400,'Invalid review JSON'); }
    try {
      await assertPrivate(env,transport);
      return response({issue:await persistReview(env,payload,transport),
        saved:true,publication_authorized:false});
    } catch (e) {
      if (e?.code===409) return fail(409,'Issue was changed elsewhere; refresh before saving');
      if (e?.message==='Invalid editor request' || e?.message==='Reviewed draft requires text' ||
          e?.message==='Unsafe editor update' || e?.message==='Not an AI Draft')
        return fail(422,'Invalid editorial review; no changes saved');
      return fail(503,'Private GitHub review could not be saved');
    }
  }
  return fail(404,'Not found');
}
export default { fetch(request,env,ctx){return handleRequest(request,env,ctx);} };
