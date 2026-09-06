"""board.html: every currently eligible posting as a card grid with category tabs.

Self-contained: inline CSS and JS, data embedded as JSON, no network, works from
file://. White SaaS look; the masthead keeps a serif. Cards lead with fit, location,
and posted date. Stretch roles (fit below the threshold) live in their own tab.
Seen state lives in localStorage.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

from .digest import CATEGORY_ORDER

_CSS = """
:root{
  --bg:#FFFFFF;--ink:#111827;--muted:#6B7280;--faint:#9CA3AF;--line:#E5E7EB;--soft:#F3F4F6;--hover:#F9FAFB;
  --accent:#2563EB;--accent-soft:#EFF6FF;
  --good:#047857;--good-soft:#ECFDF5;--ok:#1D4ED8;--ok-soft:#EFF6FF;--warn:#B45309;--warn-soft:#FFFBEB;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --panel-w:420px;
}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{margin:0;font:14px/1.5 var(--sans);color:var(--ink)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button,select,input{font:inherit;color:inherit}

.page{max-width:1240px;margin:0 auto;padding:36px 32px 96px;transition:padding-right .18s ease}
body.open .page{padding-right:calc(var(--panel-w) + 48px)}

.masthead{display:flex;justify-content:space-between;align-items:baseline;gap:24px;flex-wrap:wrap}
.masthead h1{font:400 32px/1.1 var(--serif);margin:0;letter-spacing:-.01em}
.masthead time{color:var(--muted)}
.summary{font:400 19px/1.4 var(--serif);margin:12px 0 0;max-width:70ch;color:var(--ink)}
.summary em{font-style:normal;color:var(--accent)}

.tabs{display:flex;gap:4px;margin:28px 0 0;border-bottom:1px solid var(--line);overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:10px 12px;margin-bottom:-1px;color:var(--muted);cursor:pointer;white-space:nowrap;display:flex;gap:8px;align-items:center;border-radius:6px 6px 0 0}
.tab:hover{color:var(--ink);background:var(--hover)}
.tab.active{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
.tab .n{background:var(--soft);color:var(--muted);border-radius:999px;padding:1px 8px;font-size:12px;font-weight:500}
.tab.active .n{background:var(--accent-soft);color:var(--accent)}
.tab.stretch{margin-left:auto}

.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0 20px}
.toolbar select,.toolbar input[type=search]{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:7px 10px;height:36px}
.toolbar input[type=search]{min-width:260px;flex:1;max-width:420px}
.toolbar label.check{display:inline-flex;gap:6px;align-items:center;color:var(--muted)}
.toolbar .count{margin-left:auto;color:var(--faint);font-size:13px}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.card{position:relative;display:flex;flex-direction:column;gap:10px;aspect-ratio:1/1;min-height:310px;padding:18px 18px 14px;
  background:var(--bg);border:1px solid var(--line);border-radius:14px;cursor:pointer;text-align:left;
  transition:box-shadow .15s ease,border-color .15s ease,transform .15s ease}
.card:hover{box-shadow:0 10px 30px rgba(17,24,39,.09);border-color:#D1D5DB;transform:translateY(-2px)}
.card.selected{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.card.seen{opacity:.5}
.card>*{flex:none}
.card .top{display:flex;align-items:center;gap:10px}
.avatar{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-weight:700;font-size:13px;color:#fff;letter-spacing:.02em;flex:none}
.card .co{color:var(--ink);font-weight:500;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;flex:1}
.card .age{color:var(--faint);font-size:12px;white-space:nowrap}
.seenbtn{width:26px;height:26px;border-radius:50%;border:1.5px solid var(--line);background:var(--bg);display:grid;place-items:center;cursor:pointer;color:transparent;flex:none;padding:0}
.seenbtn:hover{border-color:var(--faint);color:var(--faint)}
.seenbtn.on{background:var(--accent);border-color:var(--accent);color:#fff}
.seenbtn svg{width:14px;height:14px}
.card h3{font:600 16px/1.3 var(--sans);margin:4px 0 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;letter-spacing:-.005em}
.card .why{color:var(--muted);font-size:13px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .pills{margin-top:auto;display:flex;flex-wrap:wrap;gap:6px}
.pill{display:inline-flex;align-items:center;gap:5px;padding:4px 9px;border-radius:999px;background:var(--soft);color:var(--muted);font-size:12px;max-width:100%}
.pill svg{width:12px;height:12px;flex:none}
.pill span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pill.bay{background:var(--accent-soft);color:var(--accent);font-weight:500}
.pill.cash{background:var(--good-soft);color:var(--good)}
.card .scores{display:flex;align-items:center;gap:18px;padding-top:12px;border-top:1px solid var(--line)}
.gauge{display:flex;align-items:center;gap:8px}
.gauge svg{width:40px;height:40px;transform:rotate(-90deg)}
.gauge circle{fill:none;stroke-width:4}
.gauge .track{stroke:var(--soft)}
.gauge .arc{stroke-linecap:round;transition:stroke-dashoffset .3s ease}
.gauge .good{stroke:var(--good)}.gauge .ok{stroke:var(--ok)}.gauge .warn{stroke:var(--warn)}.gauge .rel{stroke:#6366F1}
.gauge .val{position:absolute}
.gauge .wrap{position:relative;width:40px;height:40px;display:grid;place-items:center}
.gauge .num{position:absolute;font-weight:700;font-size:13px}
.gauge .lbl{font-size:11px;color:var(--muted);line-height:1.25;white-space:nowrap}
.gauge .lbl b{display:block;font-size:12px;color:var(--ink);font-weight:600}
.pill.cat{background:transparent;border:1px solid var(--line)}

.empty{grid-column:1/-1;padding:56px 0;text-align:center;color:var(--muted)}

#panel{position:fixed;top:0;right:0;bottom:0;width:var(--panel-w);max-width:100vw;background:var(--bg);
  border-left:1px solid var(--line);box-shadow:-8px 0 24px rgba(17,24,39,.06);padding:28px 28px 32px;overflow:auto;transform:translateX(100%);transition:transform .18s ease}
body.open #panel{transform:none}
#panel .close{position:absolute;top:16px;right:16px;width:32px;height:32px;border-radius:8px;background:none;border:1px solid var(--line);font-size:18px;line-height:1;cursor:pointer;color:var(--muted)}
#panel .close:hover{background:var(--hover)}
#panel .cat{margin-top:6px}
#panel h3{font:600 20px/1.3 var(--sans);margin:12px 40px 4px 0}
#panel .company{color:var(--muted);font-size:15px}
#panel .scores{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}
#panel .score{border:1px solid var(--line);border-radius:10px;padding:12px 14px}
#panel .score b{display:block;font-size:26px;line-height:1;font-weight:700}
#panel .score span{display:block;color:var(--muted);font-size:12px;margin-top:6px}
#panel dl{margin:0 0 18px;display:grid;grid-template-columns:auto 1fr;gap:8px 16px;font-size:13px}
#panel dt{color:var(--muted)}#panel dd{margin:0}
#panel .why{background:var(--soft);border-radius:10px;padding:12px 14px;margin:0 0 16px;font-size:14px}
#panel .excerpt{color:var(--muted);font-size:13px;line-height:1.55;white-space:pre-line;max-height:34vh;overflow:auto;padding-right:6px}
#panel .actions{display:flex;gap:12px;align-items:center;margin-top:20px}
#panel .open-link{display:inline-block;background:var(--accent);color:#fff;padding:9px 16px;border-radius:8px;font-weight:600}
#panel .open-link:hover{text-decoration:none;background:#1D4ED8}
#panel .hint{color:var(--faint);font-size:12px;margin-top:24px}

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
const SEEN_KEY = 'jobwatch.seen', TAB_KEY = 'jobwatch.tab';
let seen = new Set(); try { seen = new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); } catch (e) {}
function saveSeen(){ try { localStorage.setItem(SEEN_KEY, JSON.stringify([...seen])); } catch (e) {} }
let tab = 'all'; try { tab = localStorage.getItem(TAB_KEY) || 'all'; } catch (e) {}
const $ = s => document.querySelector(s);
let selected = null, visible = [];
const CATS = new Map(D.categories);
const isStretch = r => r.fit < D.stretch_fit;

const ICON = {
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
  cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  cash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/></svg>'
};

const PALETTE = ['#2563EB','#7C3AED','#DB2777','#DC2626','#EA580C','#D97706','#059669','#0891B2','#4F46E5','#0D9488'];
function avatarColor(name){ let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0; return PALETTE[h % PALETTE.length]; }
function initials(name){ const w = name.replace(/[^a-z0-9 ]/gi, ' ').trim().split(/\s+/).filter(Boolean); return ((w[0] || '?')[0] + (w[1] ? w[1][0] : '')).toUpperCase(); }
function gauge(value, cls, label, sub){
  const r = 16, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(10, value)) / 10);
  return `<div class="gauge"><div class="wrap"><svg viewBox="0 0 40 40" aria-hidden="true"><circle class="track" cx="20" cy="20" r="${r}"/><circle class="arc ${cls}" cx="20" cy="20" r="${r}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/></svg><span class="num">${value}</span></div><div class="lbl"><b>${label}</b>${esc(sub)}</div></div>`;
}
const CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
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
  if (t === 'stretch') return isStretch(r);
  if (isStretch(r)) return false;
  return t === 'all' || r.category === t;
}
function rows(t){
  const q = $('#q').value.toLowerCase(), loc = $('#loc').value, hideSeen = $('#hideseen').checked, sort = $('#sort').value;
  let out = D.rows.filter(r => inTab(r, t) && (!loc || r.location_fit === loc) && (!hideSeen || !seen.has(r.key))
    && (!q || (r.title + ' ' + r.company + ' ' + (r.reason || '') + ' ' + (r.location || '')).toLowerCase().includes(q)));
  const byRel = (a, b) => (b.relevance - a.relevance) || (b.fit - a.fit) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byFit = (a, b) => (b.fit - a.fit) || (b.relevance - a.relevance) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byNew = (a, b) => (b.posted_at || '').localeCompare(a.posted_at || '') || byFit(a, b);
  const byCo = (a, b) => a.company.localeCompare(b.company) || byFit(a, b);
  out.sort({fit: byFit, relevance: byRel, posted: byNew, company: byCo}[sort] || byFit);
  return out;
}

function cardHtml(r){
  const isSeen = seen.has(r.key), bay = r.location_fit === 'bay_area';
  const fitSub = r.fit >= 9 ? 'new-grad open' : r.fit >= D.stretch_fit ? 'worth a shot' : 'stretch';
  const relSub = r.relevance >= 9 ? 'builds daily' : r.relevance >= 6 ? 'mostly builds' : 'less building';
  const co = r.company ? r.company[0].toUpperCase() + r.company.slice(1) : '';
  return `<div class="card ${isSeen ? 'seen' : ''} ${selected === r.key ? 'selected' : ''}" data-key="${esc(r.key)}" tabindex="0" role="button" aria-label="${esc(r.title)} at ${esc(r.company)}">
    <div class="top">
      <div class="avatar" style="background:${avatarColor(r.company)}">${esc(initials(r.company))}</div>
      <div class="co" title="${esc(r.company)}">${esc(co)}</div>
      <span class="age">${esc(age(r.posted_at))}</span>
      <button class="seenbtn ${isSeen ? 'on' : ''}" data-seen aria-label="${isSeen ? 'Mark unseen' : 'Mark seen'}" title="${isSeen ? 'Seen' : 'Mark seen'}">${CHECK}</button>
    </div>
    <h3>${esc(r.title)}</h3>
    ${r.reason ? `<div class="why">${esc(r.reason)}</div>` : ''}
    <div class="pills">
      <span class="pill ${bay ? 'bay' : ''}" title="${esc(r.location || '')}">${ICON.pin}<span>${esc(locLabel(r))}</span></span>
      ${r.comp ? `<span class="pill cash" title="${esc(r.comp)}">${ICON.cash}<span>${esc(r.comp)}</span></span>` : ''}
      ${tab === 'all' || tab === 'stretch' ? `<span class="pill cat"><span>${esc(CATS.get(r.category) || 'Other')}</span></span>` : ''}
    </div>
    <div class="scores">
      ${gauge(r.fit, fitClass(r.fit), 'Fit', fitSub)}
      ${gauge(r.relevance, 'rel', 'Relevance', relSub)}
    </div>
  </div>`;
}

function renderTabs(){
  const counts = {};
  const base = D.rows;
  counts.all = base.filter(r => !isStretch(r)).length;
  for (const [k] of D.categories) counts[k] = base.filter(r => !isStretch(r) && r.category === k).length;
  counts.stretch = base.filter(isStretch).length;
  const t = (key, label, cls='') => `<button class="tab ${cls} ${tab === key ? 'active' : ''}" data-tab="${key}" role="tab" aria-selected="${tab === key}">${esc(label)}<span class="n">${counts[key] || 0}</span></button>`;
  $('#tabs').innerHTML = t('all', 'All roles') + D.categories.map(([k, v]) => t(k, v)).join('') + t('stretch', 'Stretch', 'stretch');
}

function render(){
  renderTabs();
  visible = rows(tab);
  $('#count').textContent = `${visible.length} shown`;
  $('#grid').innerHTML = visible.map(cardHtml).join('') ||
    `<div class="empty">Nothing here with these filters. Try another tab, clear the search, or show seen roles.</div>`;
}

function showPanel(key){
  const r = D.rows.find(x => x.key === key); if (!r) return;
  selected = key;
  $('#panel').innerHTML = `
    <button class="close" aria-label="Close">×</button>
    <span class="chip cat">${esc(CATS.get(r.category) || 'Other')}${isStretch(r) ? ' · stretch' : ''}</span>
    <h3>${esc(r.title)}</h3>
    <div class="company">${esc(r.company)}</div>
    <div class="scores">
      <div class="score"><b class="${fitClass(r.fit)}" style="color:var(--${fitClass(r.fit)})">${r.fit}<small style="font-size:12px;font-weight:600;margin-left:4px">/10 fit</small></b><span>${esc(fitWords(r.fit))}</span></div>
      <div class="score"><b>${r.relevance}<small style="font-size:12px;font-weight:600;margin-left:4px">/10 relevance</small></b><span>${esc(relWords(r.relevance))}</span></div>
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
function toggleSeen(key, on){ if (on) seen.add(key); else seen.delete(key); saveSeen(); render(); if (selected === key) showPanel(key); }

$('#tabs').addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b) return;
  tab = b.dataset.tab; try { localStorage.setItem(TAB_KEY, tab); } catch (err) {}
  render();
});
$('#grid').addEventListener('click', e => {
  const card = e.target.closest('.card'); if (!card) return;
  const btn = e.target.closest('[data-seen]');
  if (btn) { e.stopPropagation(); toggleSeen(card.dataset.key, !seen.has(card.dataset.key)); return; }
  showPanel(card.dataset.key);
});
$('#grid').addEventListener('keydown', e => {
  const card = e.target.closest('.card'); if (!card) return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showPanel(card.dataset.key); }
});
$('#panel').addEventListener('click', e => { if (e.target.closest('.close')) closePanel(); });
$('#panel').addEventListener('change', e => { if (e.target.id === 'panel-seen' && selected) toggleSeen(selected, e.target.checked); });
document.addEventListener('keydown', e => {
  if (e.target.matches('input, select, textarea')) return;
  if (e.key === 'Escape' && selected) closePanel();
  if (e.key === 'ArrowRight') { e.preventDefault(); move(1); }
  if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1); }
});
['#q', '#loc', '#hideseen', '#sort'].forEach(s => $(s).addEventListener('input', render));
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
        "stretch_fit": profile["stretch_fit"],
        "categories": [list(c) for c in CATEGORY_ORDER],
        "rows": rows,
    }
    # A literal "</script>" inside the data would end the block early; escape the slash (still valid JSON).
    payload = json.dumps(data).replace("</", "<\\/")
    loc_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in
                       [("bay_area", "Bay Area"), ("us_remote", "US remote"), ("other_us", "Elsewhere in the US"),
                        ("unknown", "Location not stated")])
    date_long = now.strftime("%A, %B %-d")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>jobwatch</title><style>{_CSS}</style></head>
<body>
<main class="page">
  <header class="masthead">
    <h1>jobwatch</h1>
    <time datetime="{data['generated_at']}">{date_long}</time>
  </header>
  <p class="summary">{_summary(rows, now, profile)}</p>

  <nav class="tabs" id="tabs" role="tablist"></nav>

  <div class="toolbar" role="search">
    <input id="q" type="search" placeholder="Search titles, companies, reasons" aria-label="search">
    <select id="loc" aria-label="location"><option value="">All locations</option>{loc_opts}</select>
    <select id="sort" aria-label="sort"><option value="fit">Sort by fit</option><option value="relevance">Sort by relevance</option><option value="posted">Newest posted</option><option value="company">Company A–Z</option></select>
    <label class="check"><input id="hideseen" type="checkbox"> Hide seen</label>
    <span class="count" id="count"></span>
  </div>

  <div class="grid" id="grid"></div>
</main>
<aside id="panel" aria-label="Role details"></aside>
<script id="data" type="application/json">{payload}</script>
<script>{_JS}</script>
</body></html>
"""
