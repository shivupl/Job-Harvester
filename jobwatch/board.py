"""board.html: every currently eligible posting as a briefing, with a detail panel.

Self-contained: inline CSS and JS, data embedded as JSON, no network, works from
file://. System serif for the masthead, titles, and the score numeral; system sans
for everything else. One accent color. Seen state lives in localStorage.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

from .digest import CATEGORY_ORDER

_CSS = """
:root{
  --paper:#FBFAF7;--ink:#1B1A17;--muted:#6B675F;--faint:#A19C92;--rule:#E3E0D8;--wash:#F1EFE9;
  --accent:#155E63;--accent-ink:#0F474B;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --panel-w:400px;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#201F1C;--ink:#ECE9E2;--muted:#A8A399;--faint:#6E6A62;--rule:#35332E;--wash:#2A2925;
  --accent:#6FB8B0;--accent-ink:#8FD0C8;
}}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0;font:15px/1.5 var(--sans);color:var(--ink);background:var(--paper)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button,select,input{font:inherit;color:inherit}

.page{max-width:1100px;margin:0 auto;padding:40px 32px 96px;transition:padding-right .18s ease}
body.open .page{padding-right:calc(var(--panel-w) + 48px)}

.masthead{display:flex;justify-content:space-between;align-items:baseline;gap:24px;flex-wrap:wrap}
.masthead h1{font:400 34px/1.1 var(--serif);margin:0;letter-spacing:-.01em}
.masthead time{color:var(--muted)}
.summary{font:400 20px/1.4 var(--serif);margin:14px 0 0;max-width:62ch}
.summary em{font-style:normal;color:var(--accent-ink)}

.controls{margin:28px 0 8px;padding:14px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  display:flex;flex-wrap:wrap;gap:8px 6px;align-items:center;color:var(--muted)}
.controls select,.controls input[type=number]{background:transparent;border:0;border-bottom:1px solid var(--faint);
  padding:2px 2px;color:var(--ink);border-radius:0}
.controls input[type=number]{width:3.2em;text-align:center}
.controls input[type=search]{margin-left:auto;background:var(--wash);border:0;border-radius:2px;padding:6px 10px;min-width:240px}
.controls label.check{display:inline-flex;gap:6px;align-items:center}
.count{width:100%;color:var(--faint);font-size:13px}

section.cat{margin-top:36px}
section.cat h2{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 6px;
  font:400 22px/1.2 var(--serif);border-bottom:1px solid var(--ink);padding-bottom:8px}
section.cat h2 span{font:13px var(--sans);color:var(--muted)}

.row{display:grid;grid-template-columns:76px 1fr 32px;gap:0 12px;padding:14px 0;border-bottom:1px solid var(--rule);cursor:pointer}
.row:hover{background:var(--wash);margin:0 -12px;padding-left:12px;padding-right:12px}
.row.selected{background:var(--wash);margin:0 -12px;padding-left:12px;padding-right:12px;box-shadow:inset 3px 0 0 var(--accent)}
.row.seen{opacity:.42}
.mark{font:400 30px/1 var(--serif);color:var(--ink);letter-spacing:-.02em}
.mark small{display:block;font:12px/1.3 var(--sans);color:var(--muted);margin-top:4px}
.mark small.stretch{font-style:italic}
.row .title{font:400 18px/1.25 var(--serif);margin:0}
.row .meta{color:var(--muted);margin-top:3px}
.row .meta .bay{color:var(--accent-ink)}
.row .why{color:var(--muted);margin-top:4px;max-width:70ch}
.row .seenbox{align-self:start;justify-self:end;margin-top:4px}
.row input[type=checkbox]{width:16px;height:16px;accent-color:var(--accent);cursor:pointer}

.empty{padding:48px 0;color:var(--muted);font:400 18px/1.4 var(--serif)}

#panel{position:fixed;top:0;right:0;bottom:0;width:var(--panel-w);max-width:100vw;background:var(--paper);
  border-left:1px solid var(--rule);padding:32px 28px;overflow:auto;transform:translateX(100%);transition:transform .18s ease}
body.open #panel{transform:none}
#panel .close{position:absolute;top:18px;right:18px;background:none;border:0;font-size:22px;line-height:1;cursor:pointer;color:var(--muted)}
#panel h3{font:400 24px/1.2 var(--serif);margin:16px 0 4px}
#panel .company{color:var(--muted);font-size:16px}
#panel .scores{display:flex;gap:28px;margin:22px 0}
#panel .scores div{font:400 34px/1 var(--serif)}
#panel .scores div small{display:block;font:13px/1.4 var(--sans);color:var(--muted);margin-top:6px;max-width:14ch}
#panel dl{margin:18px 0;padding:14px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:14px}
#panel dt{color:var(--muted)}#panel dd{margin:0}
#panel .why{font:400 17px/1.45 var(--serif);margin:0 0 16px}
#panel .excerpt{color:var(--muted);font-size:14px;white-space:pre-line;max-height:38vh;overflow:auto;padding-right:6px}
#panel .actions{display:flex;gap:12px;align-items:center;margin-top:22px}
#panel .open-link{display:inline-block;background:var(--accent);color:var(--paper);padding:9px 16px;border-radius:2px}
#panel .open-link:hover{text-decoration:none;background:var(--accent-ink)}
#panel .hint{color:var(--faint);font-size:12px;margin-top:28px}

@media (max-width:900px){
  body.open .page{padding-right:32px}
  #panel{width:100vw}
  .row{grid-template-columns:60px 1fr 28px}
  .mark{font-size:26px}
}
@media (prefers-reduced-motion:reduce){.page,#panel{transition:none}}
"""

_JS = """
const D = JSON.parse(document.getElementById('data').textContent);
const SEEN_KEY = 'jobwatch.seen';
let seen = new Set(); try { seen = new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); } catch (e) {}
function saveSeen(){ try { localStorage.setItem(SEEN_KEY, JSON.stringify([...seen])); } catch (e) {} }
const $ = s => document.querySelector(s);
let selected = null, visible = [];

function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function age(iso){
  if (!iso) return '';
  const h = Math.max(0, Math.floor((new Date(D.generated_at) - new Date(iso)) / 36e5));
  if (h < 1) return 'just now'; if (h < 48) return h + (h === 1 ? ' hour ago' : ' hours ago');
  const d = Math.floor(h / 24); return d + (d === 1 ? ' day ago' : ' days ago');
}
function locLabel(r){
  const raw = r.location || '';
  switch (r.location_fit) {
    case 'bay_area': return raw && !/san francisco|bay area/i.test(raw) ? 'Bay Area, ' + raw : (raw || 'Bay Area');
    case 'us_remote': return raw && !/^remote$/i.test(raw) ? 'US remote, ' + raw : 'US remote';
    case 'other_us': return raw || 'United States';
    case 'non_us': return raw ? raw + ' (outside the US)' : 'Outside the US';
    default: return raw || 'Location not stated';
  }
}
function fitWords(f){ return f >= 9 ? 'open to new grads' : f >= 6 ? 'a strong new grad could get an interview' : f >= 3 ? 'reads mid-level; a stretch' : 'senior in substance'; }
function relWords(r){ return r >= 9 ? 'building most days, in a target role' : r >= 6 ? 'mostly building' : r >= 3 ? 'builder title, non-builder work' : 'not a building role'; }

function rows(){
  const q = $('#q').value.toLowerCase(), cat = $('#cat').value, loc = $('#loc').value;
  const minFit = +$('#minfit').value, minRel = +$('#minrel').value, hideSeen = $('#hideseen').checked;
  const sort = $('#sort').value;
  let out = D.rows.filter(r => (!cat || r.category === cat) && (!loc || r.location_fit === loc)
    && r.fit >= minFit && r.relevance >= minRel && (!hideSeen || !seen.has(r.key))
    && (!q || (r.title + ' ' + r.company + ' ' + (r.reason || '') + ' ' + (r.location || '')).toLowerCase().includes(q)));
  const byRel = (a, b) => (b.relevance - a.relevance) || (b.fit - a.fit) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byFit = (a, b) => (b.fit - a.fit) || (b.relevance - a.relevance) || (b.posted_at || '').localeCompare(a.posted_at || '');
  const byNew = (a, b) => (b.posted_at || '').localeCompare(a.posted_at || '') || byRel(a, b);
  const bySeen = (a, b) => (b.first_seen || '').localeCompare(a.first_seen || '') || byRel(a, b);
  const byCo = (a, b) => a.company.localeCompare(b.company) || byRel(a, b);
  out.sort({relevance: byRel, fit: byFit, posted: byNew, seen: bySeen, company: byCo}[sort] || byRel);
  return out;
}

function rowHtml(r){
  const stretch = r.fit < D.stretch_fit;
  const isSeen = seen.has(r.key);
  const bay = r.location_fit === 'bay_area';
  const parts = [esc(r.company), `<span class="${bay ? 'bay' : ''}">${esc(locLabel(r))}</span>`];
  const a = age(r.posted_at); if (a) parts.push('posted ' + a);
  if (r.comp) parts.push(esc(r.comp));
  return `<div class="row ${isSeen ? 'seen' : ''} ${selected === r.key ? 'selected' : ''}" data-key="${esc(r.key)}" tabindex="0" role="button" aria-label="${esc(r.title)} at ${esc(r.company)}">
    <div class="mark">${r.relevance}<small class="${stretch ? 'stretch' : ''}">${stretch ? 'stretch, ' : ''}fit ${r.fit}</small></div>
    <div>
      <p class="title">${esc(r.title)}</p>
      <div class="meta">${parts.join(', ')}</div>
      ${r.reason ? `<div class="why">${esc(r.reason)}</div>` : ''}
    </div>
    <div class="seenbox"><input type="checkbox" ${isSeen ? 'checked' : ''} aria-label="seen" title="seen"></div>
  </div>`;
}

function render(){
  visible = rows();
  $('#count').textContent = visible.length === D.rows.length ? `All ${D.rows.length} roles` : `${visible.length} of ${D.rows.length} roles`;
  const groups = new Map();
  for (const r of visible) { if (!groups.has(r.category)) groups.set(r.category, []); groups.get(r.category).push(r); }
  let html = '';
  for (const [key, label] of D.categories) {
    const g = groups.get(key); if (!g) continue;
    html += `<section class="cat"><h2>${esc(label)}<span>${g.length}</span></h2>${g.map(rowHtml).join('')}</section>`;
  }
  $('#list').innerHTML = html || `<div class="empty">Nothing matches these filters. Loosen fit or relevance, or clear the search.</div>`;
}

function showPanel(key){
  const r = D.rows.find(x => x.key === key); if (!r) return;
  selected = key;
  const stretch = r.fit < D.stretch_fit;
  $('#panel').innerHTML = `
    <button class="close" aria-label="Close">×</button>
    <h3>${esc(r.title)}</h3>
    <div class="company">${esc(r.company)}</div>
    <div class="scores">
      <div>${r.relevance}<small>relevance: ${esc(relWords(r.relevance))}</small></div>
      <div>${r.fit}<small>fit: ${esc(fitWords(r.fit))}${stretch ? ' (stretch)' : ''}</small></div>
    </div>
    <dl>
      <dt>Category</dt><dd>${esc((D.categories.find(c => c[0] === r.category) || [,'Other'])[1])}</dd>
      <dt>Location</dt><dd>${esc(locLabel(r))}</dd>
      ${r.level ? `<dt>Level read</dt><dd>${esc(r.level.replace('_', ' '))}${r.years_stated != null ? `, ${r.years_stated}+ years stated` : ''}</dd>` : ''}
      ${r.comp ? `<dt>Compensation</dt><dd>${esc(r.comp)}</dd>` : ''}
      <dt>Posted</dt><dd>${r.posted_at ? esc(age(r.posted_at)) : 'not stated'}</dd>
      <dt>First seen</dt><dd>${esc(age(r.first_seen))}</dd>
    </dl>
    ${r.reason ? `<p class="why">${esc(r.reason)}</p>` : ''}
    ${r.excerpt ? `<div class="excerpt">${esc(r.excerpt)}</div>` : `<div class="excerpt">No description excerpt stored for this posting yet.</div>`}
    <div class="actions">
      <a class="open-link" href="${esc(r.url)}" target="_blank" rel="noopener">Open posting</a>
      <label class="check"><input type="checkbox" id="panel-seen" ${seen.has(r.key) ? 'checked' : ''}> seen</label>
    </div>
    <div class="hint">Esc closes. Up and down move to the next role.</div>`;
  document.body.classList.add('open');
  render();
  const el = document.querySelector(`.row[data-key="${CSS.escape(key)}"]`);
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

$('#list').addEventListener('click', e => {
  const row = e.target.closest('.row'); if (!row) return;
  if (e.target.matches('input[type=checkbox]')) { toggleSeen(row.dataset.key, e.target.checked); return; }
  showPanel(row.dataset.key);
});
$('#list').addEventListener('keydown', e => {
  const row = e.target.closest('.row'); if (!row) return;
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showPanel(row.dataset.key); }
});
$('#panel').addEventListener('click', e => {
  if (e.target.closest('.close')) closePanel();
});
$('#panel').addEventListener('change', e => {
  if (e.target.id === 'panel-seen' && selected) toggleSeen(selected, e.target.checked);
});
document.addEventListener('keydown', e => {
  if (e.target.matches('input, select, textarea')) return;
  if (e.key === 'Escape' && selected) closePanel();
  if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
  if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
});
['#q', '#cat', '#loc', '#minfit', '#minrel', '#hideseen', '#sort'].forEach(s => $(s).addEventListener('input', render));
render();
"""


def _summary(rows: list[dict], now: datetime, profile: dict) -> str:
    n = len(rows)
    if n == 0:
        return "Nothing to look at right now. The next run may change that."
    day_ago = now.timestamp() - 86400
    fresh = sum(1 for r in rows if r.get("first_seen") and
                datetime.fromisoformat(r["first_seen"]).timestamp() >= day_ago)
    top = sum(1 for r in rows if r["relevance"] >= 9 and r["fit"] >= 8)
    parts = [f"<em>{n}</em> role{'s' if n != 1 else ''} worth a look from the last {profile['board_days']} days"]
    if fresh:
        parts.append(f"<em>{fresh}</em> arrived in the last day")
    if top:
        parts.append(f"<em>{top}</em> score 9 or better on both counts")
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
    cat_opts = "".join(f'<option value="{k}">{html.escape(v)}</option>' for k, v in CATEGORY_ORDER)
    loc_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in
                       [("bay_area", "the Bay Area"), ("us_remote", "US remote"), ("other_us", "elsewhere in the US"),
                        ("unknown", "an unstated location")])
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

  <div class="controls" role="search">
    <span>Show</span>
    <select id="cat" aria-label="category"><option value="">all categories</option>{cat_opts}</select>
    <span>in</span>
    <select id="loc" aria-label="location"><option value="">all locations</option>{loc_opts}</select>
    <span>with fit at least</span><input id="minfit" type="number" min="0" max="10" value="{profile['min_fit']}" aria-label="minimum fit">
    <span>and relevance at least</span><input id="minrel" type="number" min="0" max="10" value="{profile['min_relevance']}" aria-label="minimum relevance">
    <span>, sorted by</span>
    <select id="sort" aria-label="sort"><option value="relevance">relevance</option><option value="fit">fit</option><option value="posted">newest posted</option><option value="seen">newest here</option><option value="company">company</option></select>
    <label class="check"><input id="hideseen" type="checkbox"> hide seen</label>
    <input id="q" type="search" placeholder="Search titles, companies, reasons" aria-label="search">
    <span class="count" id="count"></span>
  </div>

  <div id="list"></div>
</main>
<aside id="panel" aria-label="Role details"></aside>
<script id="data" type="application/json">{payload}</script>
<script>{_JS}</script>
</body></html>
"""
