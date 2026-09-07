"""board.html: every currently eligible posting as a card grid with category tabs.

Self-contained: inline CSS and JS, data embedded as JSON, no network, works from
file://. Graphite (dark) / Ash (light) palette with a theme toggle that follows the
system by default. Stretch roles (fit below the threshold) live in their own tab.
Seen state and theme live in localStorage.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

from zoneinfo import ZoneInfo

from .digest import CATEGORY_ORDER

_CSS = """
:root{
  /* Ash (light) */
  --bg:#ECEDEA;--card:#FFFFFF;--line:#D9DAD5;--ink:#1B1C1F;--muted:#5F615C;--faint:#8A8C86;--hover:#F6F6F4;
  --good:#1E9E5C;--good-soft:#E3F5EA;--ok:#2A6FD6;--warn:#C4841A;--rel:#6B55D6;--accent:#2A6FD6;
  --gold:#B8860B;--gold-soft:#FBF3DC;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono","JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --panel-w:420px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#1B1C1F;--card:#232428;--line:#303136;--ink:#F4F4F2;--muted:#A9AAA6;--faint:#8C8D8A;--hover:#2A2B30;
  --good:#5AD27A;--good-soft:#1E3327;--ok:#7AAFFF;--warn:#F2B54B;--rel:#B49CFF;--accent:#7AAFFF;
  --gold:#F2C94C;--gold-soft:#3A3120;
}}
:root[data-theme="dark"]{
  --bg:#1B1C1F;--card:#232428;--line:#303136;--ink:#F4F4F2;--muted:#A9AAA6;--faint:#8C8D8A;--hover:#2A2B30;
  --good:#5AD27A;--good-soft:#1E3327;--ok:#7AAFFF;--warn:#F2B54B;--rel:#B49CFF;--accent:#7AAFFF;
  --gold:#F2C94C;--gold-soft:#3A3120;
}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{margin:0;font:14px/1.5 var(--sans);color:var(--ink)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button,select,input{font:inherit;color:inherit}

.page{max-width:1180px;margin:0 auto;padding:36px 32px 96px;transition:padding-right .18s ease}
body.open .page{padding-right:calc(var(--panel-w) + 48px)}

.masthead{display:flex;justify-content:space-between;align-items:baseline;gap:24px;flex-wrap:wrap}
.masthead h1{font:400 32px/1.1 var(--serif);margin:0;letter-spacing:-.01em}
.masthead .right{display:flex;align-items:baseline;gap:16px;color:var(--muted)}
.theme{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 10px;font:12px var(--mono);color:var(--muted);cursor:pointer}
.theme:hover{color:var(--ink)}
.summary{font:400 19px/1.4 var(--serif);margin:12px 0 0;max-width:70ch;color:var(--ink)}
.summary em{font-style:normal;color:var(--accent)}

.tabs{display:flex;gap:2px;margin:28px 0 0;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:10px 12px;margin-bottom:-1px;color:var(--muted);cursor:pointer;white-space:nowrap;display:flex;gap:8px;align-items:center}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink);border-bottom-color:var(--ink);font-weight:600}
.tab .n{font:11px var(--mono);color:var(--faint)}
.tab.active .n{color:var(--ink)}
.tab.stretch{margin-left:auto}

.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0 20px}
.toolbar select,.toolbar input[type=search]{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:7px 10px;height:36px;color:var(--ink)}
.toolbar input[type=search]{min-width:260px;flex:1;max-width:420px}
.toolbar label.check{display:inline-flex;gap:6px;align-items:center;color:var(--muted)}
.toolbar .count{margin-left:auto;color:var(--faint);font:12px var(--mono)}

.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:stretch}
@media (max-width:1100px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.grid{grid-template-columns:1fr}}
body.open .grid{grid-template-columns:repeat(2,minmax(0,1fr))}

.card{position:relative;display:flex;flex-direction:column;gap:8px;min-height:250px;padding:16px;
  background:var(--card);border:1px solid var(--line);border-radius:8px;cursor:pointer;text-align:left;
  transition:border-color .12s ease,background .12s ease}
.card:hover{border-color:var(--faint)}
.card.selected{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 30%,transparent)}
.card.seen{opacity:.45}
.card>*{flex:none}
.card .top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;font:11px var(--mono);color:var(--faint)}
.card .top .l b{display:block;font:500 13px var(--sans);color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:22ch}
.card .top .r{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:2px;min-width:0;max-width:60%}
.card .top .r .loc{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.card .top .r .loc.bay{color:var(--ok)}
.card.newgrad{border-color:var(--gold);box-shadow:inset 0 0 0 1px var(--gold)}
.card.newgrad:hover{border-color:var(--gold)}
.card.newgrad h3{color:var(--gold)}
.tag.newgrad{display:inline-block;padding:1px 7px;border-radius:999px;background:var(--gold-soft);color:var(--gold);font:500 10.5px var(--mono);letter-spacing:.02em;white-space:nowrap}
.card h3{font:600 15px/1.3 var(--sans);margin:4px 0 0;color:var(--ink);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card h3 a{color:inherit;text-decoration:none}
.card h3 a:hover{text-decoration:underline;text-underline-offset:3px}
.card h3 a::after{content:" ↗";font:500 12px var(--mono);color:var(--faint);white-space:nowrap}
.card h3 a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
.card .why{color:var(--muted);font-size:13px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.comp{display:inline-flex;align-items:center;gap:6px;align-self:flex-start;max-width:100%;padding:4px 10px;border-radius:999px;background:var(--good-soft);color:var(--good);font-size:12px;font-weight:500}
.comp svg{width:13px;height:13px;flex:none}
.comp span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card .foot{display:flex;align-items:center;gap:14px;margin-top:auto;padding-top:10px;border-top:1px solid var(--line);font:11px var(--mono);color:var(--faint)}
.acts{display:flex;gap:6px;justify-content:flex-end;margin-top:auto}
.card .acts+.foot{margin-top:0}
.act{font:500 11px var(--mono);padding:4px 9px;border-radius:5px;border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer;line-height:1}
.act:hover{border-color:var(--faint);color:var(--ink)}
.act.on{background:var(--good-soft);border-color:var(--good);color:var(--good)}
.act.on.save{background:color-mix(in srgb,var(--accent) 14%,transparent);border-color:var(--accent);color:var(--accent)}
.tab.saved{margin-left:0}
.card.applied{border-color:var(--good)}
.tag.applied{display:inline-block;padding:1px 7px;border-radius:999px;background:var(--good-soft);color:var(--good);font:500 10.5px var(--mono);letter-spacing:.02em;white-space:nowrap}
#panel .acts{justify-content:flex-start;margin-top:0}
.kv{display:flex;align-items:baseline;gap:6px}.kv b{font-size:15px;font-weight:500;color:var(--ink)}
.kv.good b{color:var(--good)}.kv.ok b{color:var(--ok)}.kv.warn b{color:var(--warn)}
.cat{margin-left:auto;padding:2px 8px;border-radius:4px;font:11px var(--sans);background:color-mix(in srgb,var(--c) 18%,transparent);color:var(--c);white-space:nowrap}
.cat.fde{--c:var(--ok)}.cat.product{--c:var(--warn)}.cat.applied_ai{--c:var(--good)}.cat.swe{--c:var(--rel)}.cat.devrel{--c:#E07AA0}.cat.other{--c:var(--faint)}

.empty{grid-column:1/-1;padding:56px 0;text-align:center;color:var(--muted)}
.mode{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 12px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--muted);font:500 12px var(--mono);cursor:pointer}
.mode:hover{border-color:var(--faint);color:var(--ink)}
.mode.on{border-color:var(--accent);color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}
.mode .dot{width:7px;height:7px;border-radius:50%;background:currentColor}
#grid.arrivals{display:block}
.day{display:grid;grid-template-columns:150px 1fr;gap:20px;margin:6px 0 26px}
.day .lab{position:sticky;top:12px;align-self:start;padding-top:2px}
.day .lab .d{font:600 14px var(--sans);color:var(--accent)}
.day .lab .m{font:11px var(--mono);color:var(--faint);margin-top:3px;line-height:1.6}
.day .lab .m span{display:block}
.rule{height:1px;background:linear-gradient(90deg,var(--accent) 0,var(--accent) 150px,var(--line) 150px);margin:0 0 20px}
.collapsed{display:flex;align-items:center;gap:12px;padding:14px 16px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--muted);font-size:13px}
.collapsed b{color:var(--ink);font-weight:600}
.collapsed .btn{margin-left:auto;font:500 11px var(--mono);padding:5px 10px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--muted);cursor:pointer}
.collapsed .btn:hover{border-color:var(--faint);color:var(--ink)}
.arrivals .empty{padding:28px 0}
@media (max-width:900px){.day{grid-template-columns:1fr}.day .lab{position:static}}

#panel{position:fixed;top:0;right:0;bottom:0;width:var(--panel-w);max-width:100vw;background:var(--card);
  border-left:1px solid var(--line);padding:28px 28px 32px;overflow:auto;transform:translateX(100%);transition:transform .18s ease}
body.open #panel{transform:none}
#panel .close{position:absolute;top:16px;right:16px;width:30px;height:30px;border-radius:6px;background:none;border:1px solid var(--line);font-size:18px;line-height:1;cursor:pointer;color:var(--muted)}
#panel .close:hover{background:var(--hover)}
#panel .cat{margin:0;display:inline-block}
#panel h3{font:600 20px/1.3 var(--sans);margin:12px 40px 4px 0}
#panel .company{color:var(--muted);font-size:15px}
#panel .scores{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}
#panel .score{border:1px solid var(--line);border-radius:8px;padding:12px 14px}
#panel .score b{display:block;font:500 26px/1 var(--mono)}
#panel .score small{font:11px var(--mono);color:var(--faint);margin-left:6px}
#panel .score span{display:block;color:var(--muted);font-size:12px;margin-top:6px}
#panel dl{margin:0 0 18px;display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:13px}
#panel dt{color:var(--faint);font:11px var(--mono);align-self:center}#panel dd{margin:0}
#panel .why{background:var(--bg);border-radius:8px;padding:12px 14px;margin:0 0 16px;font-size:14px}
#panel .excerpt{color:var(--muted);font-size:13px;line-height:1.55;white-space:pre-line;max-height:34vh;overflow:auto;padding-right:6px}
#panel .actions{display:flex;gap:12px;align-items:center;margin-top:20px}
#panel .open-link{display:inline-block;background:var(--ink);color:var(--card);padding:9px 16px;border-radius:6px;font-weight:600}
#panel .open-link:hover{text-decoration:none;opacity:.9}
#panel .hint{color:var(--faint);font:11px var(--mono);margin-top:24px}

@media (max-width:900px){
  body.open .page{padding-right:32px}
  #panel{width:100vw}
  .page{padding:24px 16px 64px}
  .tab.stretch{margin-left:0}
}
@media (prefers-reduced-motion:reduce){.page,#panel,.card{transition:none}}
"""

_JS = """
const D = JSON.parse(document.getElementById('data').textContent);
const SEEN_KEY = 'jobwatch.seen', APPLIED_KEY = 'jobwatch.applied', HIDDEN_KEY = 'jobwatch.hidden', SAVED_KEY = 'jobwatch.saved', TAB_KEY = 'jobwatch.tab';
function loadSet(k){ try { return new Set(JSON.parse(localStorage.getItem(k) || '[]')); } catch (e) { return new Set(); } }
function saveSet(k, v){ try { localStorage.setItem(k, JSON.stringify([...v])); } catch (e) {} }
let seen = loadSet(SEEN_KEY), applied = loadSet(APPLIED_KEY), hidden = loadSet(HIDDEN_KEY), saved = loadSet(SAVED_KEY);
function saveSeen(){ saveSet(SEEN_KEY, seen); }
let tab = 'all'; try { tab = localStorage.getItem(TAB_KEY) || 'all'; } catch (e) {}
// "New" means first seen after the newest board you had opened before this one.
const VISIT_KEY = 'jobwatch.lastvisit';
let lastGen = null; try { lastGen = localStorage.getItem(VISIT_KEY); } catch (e) {}
try { if (!lastGen || D.generated_at > lastGen) localStorage.setItem(VISIT_KEY, D.generated_at); } catch (e) {}
const isNew = r => !lastGen || (r.first_seen || '') > lastGen;
const newTotal = D.rows.filter(isNew).length;
let arrivals = newTotal > 0;
const dayFmt = new Intl.DateTimeFormat('en-CA', {timeZone: D.tz, year: 'numeric', month: '2-digit', day: '2-digit'});
const labelFmt = new Intl.DateTimeFormat('en-US', {timeZone: D.tz, weekday: 'short', month: 'short', day: 'numeric'});
function dayKey(iso){ return dayFmt.format(new Date(iso)); }
function dayName(key, iso){
  const today = dayKey(D.generated_at), y = dayKey(new Date(new Date(D.generated_at).getTime() - 864e5).toISOString());
  return key === today ? 'Today' : key === y ? 'Yesterday' : labelFmt.format(new Date(iso));
}
const THEME_KEY = 'jobwatch.theme';
function applyTheme(){
  let t = 'system'; try { t = localStorage.getItem(THEME_KEY) || 'system'; } catch (e) {}
  if (t === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
  const b = document.getElementById('theme'); if (b) b.textContent = {system: 'theme: system', light: 'theme: light', dark: 'theme: dark'}[t];
}
function cycleTheme(){
  let t = 'system'; try { t = localStorage.getItem(THEME_KEY) || 'system'; } catch (e) {}
  const next = {system: 'dark', dark: 'light', light: 'system'}[t];
  try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
  applyTheme();
}
applyTheme();
const $ = s => document.querySelector(s);
let selected = null, visible = [];
const CATS = new Map(D.categories);
const isStretch = r => r.fit < D.stretch_fit;

const ICON = {
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
  cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  cash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/></svg>'
};

function gauge(value, cls, label, sub){
  const r = 16, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(10, value)) / 10);
  return `<div class="gauge"><div class="wrap"><svg viewBox="0 0 40 40" aria-hidden="true"><circle class="track" cx="20" cy="20" r="${r}"/><circle class="arc ${cls}" cx="20" cy="20" r="${r}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/></svg><span class="num">${value}</span></div><div class="lbl"><b>${label}</b>${esc(sub)}</div></div>`;
}
function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function age(iso){
  if (!iso) return 'date not stated';
  const h = Math.max(0, Math.floor((new Date(D.generated_at) - new Date(iso)) / 36e5));
  if (h < 1) return 'just now'; if (h < 24) return h + 'h ago';
  const d = Math.floor(h / 24); return d === 1 ? 'yesterday' : d + ' days ago';
}
function locLabel(r){
  const raw = r.location || '';
  switch (r.location_fit) {
    case 'bay_area': return raw && !/san francisco|bay area/i.test(raw) ? 'Bay Area · ' + raw : (raw || 'Bay Area');
    case 'us_remote': return raw && !/^remote$/i.test(raw) ? 'US remote · ' + raw : 'US remote';
    case 'other_us': return raw || 'United States';
    case 'non_us': return raw ? raw + ' (outside the US)' : 'Outside the US';
    default: return raw || 'Location not stated';
  }
}
function fitClass(f){ return f >= 9 ? 'good' : f >= D.stretch_fit ? 'ok' : 'warn'; }
function fitWords(f){ return f >= 9 ? 'Open to new grads' : f >= 6 ? 'A strong new grad could get an interview' : f >= 3 ? 'Reads mid-level; a stretch' : 'Senior in substance'; }
function relWords(r){ return r >= 9 ? 'Building most days, in a target role' : r >= 6 ? 'Mostly building' : r >= 3 ? 'Builder title, non-builder work' : 'Not a building role'; }

function inTab(r, t){
  if (t === 'saved') return saved.has(r.key);
  if (t === 'stretch') return isStretch(r);
  if (isStretch(r)) return false;
  return t === 'all' || r.category === t;
}
function rows(t){
  const q = $('#q').value.toLowerCase(), loc = $('#loc').value, view = $('#view').value, sort = $('#sort').value;
  const inView = r => view === 'applied' ? applied.has(r.key) : view === 'hidden' ? hidden.has(r.key)
    : view === 'unseen' ? !hidden.has(r.key) && !seen.has(r.key) && !applied.has(r.key) : !hidden.has(r.key);
  let out = D.rows.filter(r => inTab(r, t) && (!loc || r.location_fit === loc) && inView(r)
    && (!q || (r.title + ' ' + r.company + ' ' + (r.reason || '') + ' ' + (r.location || '')).toLowerCase().includes(q)));
  const byRel = (a, b) => (b.relevance - a.relevance) || (b.fit - a.fit) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byFit = (a, b) => (b.fit - a.fit) || (b.relevance - a.relevance) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byNew = (a, b) => (b.posted_at || '').localeCompare(a.posted_at || '') || byFit(a, b);
  const byCo = (a, b) => a.company.localeCompare(b.company) || byFit(a, b);
  out.sort({fit: byFit, relevance: byRel, posted: byNew, company: byCo}[sort] || byFit);
  return out;
}

function actsHtml(key){
  const a = applied.has(key), h = hidden.has(key), sv = saved.has(key);
  return `<div class="acts">
      <button class="act ${sv ? 'on save' : ''}" data-act="saved" title="${sv ? 'Saved. Click to remove from the Saved tab' : 'Save for later in the Saved tab'}">${sv ? 'Saved ★' : 'Save'}</button>
      <button class="act ${a ? 'on' : ''}" data-act="applied" title="${a ? 'Applied. Click to undo' : 'Mark as applied'}">${a ? 'Applied ✓' : 'Applied'}</button>
      <button class="act" data-act="hidden" title="${h ? 'Put it back on the board' : 'Hide this role from the board'}">${h ? 'Unhide' : 'Hide'}</button>
    </div>`;
}
function cardHtml(r){
  const isSeen = seen.has(r.key), bay = r.location_fit === 'bay_area', ng = r.level === 'new_grad';
  const isApplied = applied.has(r.key), isHidden = hidden.has(r.key);
  const co = r.company ? r.company[0].toUpperCase() + r.company.slice(1) : '';
  return `<div class="card ${isSeen ? 'seen' : ''} ${ng ? 'newgrad' : ''} ${isApplied ? 'applied' : ''} ${selected === r.key ? 'selected' : ''}" data-key="${esc(r.key)}" tabindex="0" role="button" aria-label="${esc(r.title)} at ${esc(r.company)}${ng ? ', new grad role' : ''}">
    <div class="top">
      <div class="l"><b title="${esc(r.company)}">${esc(co)}</b>${esc(age(r.posted_at))}</div>
      <div class="r"><span class="loc ${bay ? 'bay' : ''}" title="${esc(r.location || '')}">${esc(locLabel(r))}</span>${ng ? '<span class="tag newgrad" title="The posting explicitly targets new grads">new grad</span>' : ''}${isApplied ? '<span class="tag applied">applied</span>' : ''}</div>
    </div>
    <h3><a href="${esc(r.url)}" target="_blank" rel="noopener" title="Open the posting in a new tab">${esc(r.title)}</a></h3>
    ${r.reason ? `<div class="why">${esc(r.reason)}</div>` : ''}
    ${r.comp ? `<span class="comp" title="${esc(r.comp)}">${ICON.cash}<span>${esc(r.comp)}</span></span>` : ''}
    ${actsHtml(r.key)}
    <div class="foot">
      <span class="kv ${fitClass(r.fit)}">fit <b>${r.fit}</b></span>
      <span class="kv">rel <b>${r.relevance}</b></span>
      <span class="cat ${esc(r.category)}">${esc(CATS.get(r.category) || 'Other')}</span>
    </div>
  </div>`;
}

function renderTabs(){
  const counts = {};
  const base = D.rows;
  counts.all = base.filter(r => !isStretch(r)).length;
  for (const [k] of D.categories) counts[k] = base.filter(r => !isStretch(r) && r.category === k).length;
  counts.stretch = base.filter(isStretch).length;
  counts.saved = base.filter(r => saved.has(r.key)).length;
  const t = (key, label, cls='') => `<button class="tab ${cls} ${tab === key ? 'active' : ''}" data-tab="${key}" role="tab" aria-selected="${tab === key}">${esc(label)}<span class="n">${counts[key] || 0}</span></button>`;
  $('#tabs').innerHTML = t('all', 'All roles') + D.categories.map(([k, v]) => t(k, v)).join('') + t('stretch', 'Stretch', 'stretch') + t('saved', 'Saved', 'saved');
}

function sinceText(){
  if (!lastGen || !newTotal) return '';
  return `<em>${newTotal}</em> arrived since you last opened the board.`;
}
function render(){
  $('#since').innerHTML = sinceText();
  renderTabs();
  visible = rows(tab);
  $('#count').textContent = `${visible.length} shown`;
  $('#view option[value=applied]').textContent = `Applied (${applied.size})`;
  $('#view option[value=hidden]').textContent = `Hidden (${hidden.size})`;
  const mode = $('#mode'); mode.classList.toggle('on', arrivals); mode.setAttribute('aria-pressed', arrivals);
  $('#grid').classList.toggle('arrivals', arrivals);
  const empty = `<div class="empty">Nothing here with these filters. Try another tab, clear the search, or switch the view.</div>`;
  if (!arrivals) { $('#grid').innerHTML = visible.map(cardHtml).join('') || empty; return; }
  const groups = new Map();
  for (const r of visible) if (isNew(r)) { const k = dayKey(r.first_seen); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); }
  const older = visible.length - [...groups.values()].reduce((n, g) => n + g.length, 0);
  let html = '';
  for (const k of [...groups.keys()].sort().reverse()) {
    const g = groups.get(k), runs = new Set(g.map(r => r.first_seen)).size, ng = g.filter(r => r.level === 'new_grad').length;
    html += `<section class="day"><div class="lab"><div class="d">${esc(dayName(k, g[0].first_seen))}</div><div class="m">
        <span>${esc(labelFmt.format(new Date(g[0].first_seen)))} · ${runs} run${runs === 1 ? '' : 's'}</span><span>${g.length} new</span>${ng ? `<span>${ng} new grad</span>` : ''}</div></div>
      <div class="grid">${g.map(cardHtml).join('')}</div></section><div class="rule"></div>`;
  }
  if (!groups.size) html += `<div class="empty">${newTotal ? 'No new arrivals match these filters.' : 'Nothing has arrived since you last opened the board.'}</div>`;
  html += `<div class="collapsed"><span><b>Earlier</b> · ${older} role${older === 1 ? ' was' : 's were'} already on the board</span><button class="btn" id="showall">Show all</button></div>`;
  $('#grid').innerHTML = html;
}

function showPanel(key){
  const r = D.rows.find(x => x.key === key); if (!r) return;
  selected = key;
  $('#panel').innerHTML = `
    <button class="close" aria-label="Close">×</button>
    <span class="cat ${esc(r.category)}">${esc(CATS.get(r.category) || 'Other')}${isStretch(r) ? ' · stretch' : ''}</span>
    <h3>${esc(r.title)}</h3>
    <div class="company">${esc(r.company)}</div>
    <div class="scores">
      <div class="score"><b style="color:var(--${fitClass(r.fit)})">${r.fit}<small>fit</small></b><span>${esc(fitWords(r.fit))}</span></div>
      <div class="score"><b>${r.relevance}<small>rel</small></b><span>${esc(relWords(r.relevance))}</span></div>
    </div>
    <dl>
      <dt>Location</dt><dd>${esc(locLabel(r))}</dd>
      <dt>Posted</dt><dd>${esc(age(r.posted_at))}</dd>
      ${r.comp ? `<dt>Compensation</dt><dd>${esc(r.comp)}</dd>` : ''}
      ${r.level ? `<dt>Level read</dt><dd>${esc(r.level.replace('_', ' '))}${r.years_stated != null ? `, ${r.years_stated}+ years stated` : ''}</dd>` : ''}
      <dt>First seen</dt><dd>${esc(age(r.first_seen))}</dd>
    </dl>
    ${r.reason ? `<div class="why">${esc(r.reason)}</div>` : ''}
    ${r.excerpt ? `<div class="excerpt">${esc(r.excerpt)}</div>` : `<div class="excerpt">No description excerpt stored for this posting yet.</div>`}
    <div class="actions">
      <a class="open-link" href="${esc(r.url)}" target="_blank" rel="noopener">Open posting</a>
      <label class="check"><input type="checkbox" id="panel-seen" ${seen.has(r.key) ? 'checked' : ''}> Mark seen</label>
    </div>
    ${actsHtml(r.key)}
    <div class="hint">Esc closes. Left and right arrows move between cards.</div>`;
  document.body.classList.add('open');
  render();
  const el = document.querySelector(`.card[data-key="${CSS.escape(key)}"]`);
  if (el) el.scrollIntoView({block: 'nearest'});
}
function closePanel(){ selected = null; document.body.classList.remove('open'); render(); }
function move(delta){
  if (!selected || !visible.length) return;
  const i = visible.findIndex(r => r.key === selected);
  const next = visible[Math.min(visible.length - 1, Math.max(0, i + delta))];
  if (next && next.key !== selected) showPanel(next.key);
}
function toggleAct(key, which){
  const set = {applied, hidden, saved}[which];
  if (set.has(key)) set.delete(key); else set.add(key);
  saveSet({applied: APPLIED_KEY, hidden: HIDDEN_KEY, saved: SAVED_KEY}[which], set);
  if (which === 'hidden' && selected === key && set.has(key) && $('#view').value !== 'hidden') closePanel();
  render(); if (selected === key) showPanel(key);
}
function toggleSeen(key, on){ if (on) seen.add(key); else seen.delete(key); saveSeen(); render(); if (selected === key) showPanel(key); }

document.getElementById('theme').addEventListener('click', cycleTheme);
$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b) return;
  tab = b.dataset.tab; try { localStorage.setItem(TAB_KEY, tab); } catch (err) {}
  render();
});
$('#mode').addEventListener('click', () => { arrivals = !arrivals; render(); });
$('#grid').addEventListener('click', e => {
  if (e.target.closest('#showall')) { arrivals = false; render(); return; }
  if (e.target.closest('h3 a')) return;                      // title link opens the posting, not the panel
  const card = e.target.closest('.card'); if (!card) return;
  const act = e.target.closest('[data-act]');
  if (act) { e.stopPropagation(); toggleAct(card.dataset.key, act.dataset.act); return; }
  showPanel(card.dataset.key);
});
$('#grid').addEventListener('keydown', e => {
  const card = e.target.closest('.card'); if (!card) return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showPanel(card.dataset.key); }
});
$('#panel').addEventListener('click', e => {
  if (e.target.closest('.close')) { closePanel(); return; }
  const act = e.target.closest('[data-act]');
  if (act && selected) toggleAct(selected, act.dataset.act);
});
$('#panel').addEventListener('change', e => { if (e.target.id === 'panel-seen' && selected) toggleSeen(selected, e.target.checked); });
document.addEventListener('keydown', e => {
  if (e.target.matches('input, select, textarea')) return;
  if (e.key === 'Escape' && selected) closePanel();
  if (e.key === 'ArrowRight') { e.preventDefault(); move(1); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1); }
});
['#q', '#loc', '#view', '#sort'].forEach(s => $(s).addEventListener('input', render));
render();
"""


def _summary(rows: list[dict], now: datetime, profile: dict) -> str:
    n = len(rows)
    if n == 0:
        return "Nothing to look at right now. The next run may change that."
    two_days_ago = now.timestamp() - 2 * 86400
    fresh = sum(1 for r in rows if r.get("posted_at") and
                datetime.fromisoformat(r["posted_at"]).timestamp() >= two_days_ago)
    stretch = sum(1 for r in rows if r["fit"] < profile["stretch_fit"])
    top = sum(1 for r in rows if r["relevance"] >= 9 and r["fit"] >= 8)
    parts = [f"<em>{n - stretch}</em> role{'s' if n - stretch != 1 else ''} worth a look from the last {profile['board_days']} days"]
    if 0 < fresh < n:
        parts.append(f"<em>{fresh}</em> posted in the last two days")
    if top:
        parts.append(f"<em>{top}</em> score 9 or better on both counts")
    if stretch:
        parts.append(f"<em>{stretch}</em> more in the Stretch tab")
    return ". ".join(parts) + "."


def render_board(rows: list[dict], now: datetime, profile: dict) -> str:
    data = {
        "generated_at": now.replace(microsecond=0).isoformat(),
        "tz": profile["timezone"],
        "stretch_fit": profile["stretch_fit"],
        "categories": [list(c) for c in CATEGORY_ORDER],
        "rows": rows,
    }
    # A literal "</script>" inside the data would end the block early; escape the slash (still valid JSON).
    payload = json.dumps(data).replace("</", "<\\/")
    loc_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in
                       [("bay_area", "Bay Area"), ("us_remote", "US remote"), ("other_us", "Elsewhere in the US"),
                        ("unknown", "Location not stated")])
    date_long = now.astimezone(ZoneInfo(profile["timezone"])).strftime("%A, %B %-d")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>jobwatch</title><style>{_CSS}</style></head>
<body>
<main class="page">
  <header class="masthead">
    <h1>jobwatch</h1>
    <div class="right"><time datetime="{data['generated_at']}">{date_long}</time><button class="theme" id="theme" type="button">theme: system</button></div>
  </header>
  <p class="summary">{_summary(rows, now, profile)} <span id="since"></span></p>

  <nav class="tabs" id="tabs" role="tablist"></nav>

  <div class="toolbar" role="search">
    <input id="q" type="search" placeholder="Search titles, companies, reasons" aria-label="search">
    <select id="loc" aria-label="location"><option value="">All locations</option>{loc_opts}</select>
    <select id="sort" aria-label="sort"><option value="fit">Sort by fit</option><option value="relevance">Sort by relevance</option><option value="posted">Newest posted</option><option value="company">Company A–Z</option></select>
    <button class="mode" id="mode" type="button" aria-pressed="false" title="Group what arrived since you last opened the board"><span class="dot"></span>Arrivals</button>
    <select id="view" aria-label="view"><option value="active">Active</option><option value="unseen">Unseen only</option><option value="applied">Applied</option><option value="hidden">Hidden</option></select>
    <span class="count" id="count"></span>
  </div>

  <div class="grid" id="grid"></div>
</main>
<aside id="panel" aria-label="Role details"></aside>
<script id="data" type="application/json">{payload}</script>
<script>{_JS}</script>
</body></html>
"""
