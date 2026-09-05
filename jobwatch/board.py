"""board.html: every currently eligible posting, sortable and filterable, self-contained."""
from __future__ import annotations

import html
import json
from datetime import datetime

from .digest import CATEGORY_ORDER

_CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e5e5e5;--accent:#2563eb;--soft:#f5f5f5}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--muted:#999;--line:#2a2a2a;--accent:#60a5fa;--soft:#1b1b1b}}
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;gap:14px;align-items:center;flex-wrap:wrap}
header h1{font-size:16px;margin:0 8px 0 0}header .meta{color:var(--muted)}
.controls{padding:10px 18px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--line);background:var(--soft)}
.controls label{display:flex;gap:4px;align-items:center;color:var(--muted)}
input,select{font:inherit;padding:4px 6px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--fg)}
input[type=search]{min-width:220px}
table{width:100%;border-collapse:collapse}th,td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{position:sticky;top:0;background:var(--bg);cursor:pointer;user-select:none;white-space:nowrap;font-weight:600}
th.sorted::after{content:" \\25BE";color:var(--muted)}th.sorted.asc::after{content:" \\25B4"}
td.num{text-align:right;font-variant-numeric:tabular-nums;width:1%}
td.title a{color:var(--accent);text-decoration:none;font-weight:600}td.title a:hover{text-decoration:underline}
.reason{color:var(--muted);font-size:13px;margin-top:2px}
.tag{display:inline-block;padding:1px 6px;border-radius:10px;background:var(--soft);border:1px solid var(--line);font-size:12px;color:var(--muted);margin-right:4px}
.tag.bay{border-color:var(--accent);color:var(--accent)}.tag.stretch{border-color:#d97706;color:#d97706}
tr.seen td{opacity:.45}tr.seen td.title a{text-decoration:line-through}
.count{color:var(--muted);margin-left:auto}
"""

_JS = """
const D = JSON.parse(document.getElementById('data').textContent);
const SEEN_KEY = 'jobwatch.seen';
let seen = new Set(); try { seen = new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]')); } catch (e) {}
function saveSeen(){ try { localStorage.setItem(SEEN_KEY, JSON.stringify([...seen])); } catch (e) {} }
let sortKey = 'relevance', sortAsc = false;
const $ = s => document.querySelector(s);
function age(iso){ if(!iso) return ''; const h = Math.max(0, Math.floor((new Date(D.generated_at) - new Date(iso))/36e5)); return h < 48 ? h + 'h' : Math.floor(h/24) + 'd'; }
function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function locTag(r){ return {bay_area:'Bay Area', us_remote:'US remote', other_us: r.location || 'US', non_us:'non-US', unknown: r.location || 'unknown'}[r.location_fit] || r.location_fit; }
function rows(){
  const q = $('#q').value.toLowerCase(), cat = $('#cat').value, loc = $('#loc').value;
  const minFit = +$('#minfit').value, minRel = +$('#minrel').value, hideSeen = $('#hideseen').checked;
  let out = D.rows.filter(r => (!cat || r.category === cat) && (!loc || r.location_fit === loc)
    && r.fit >= minFit && r.relevance >= minRel && (!hideSeen || !seen.has(r.key))
    && (!q || (r.title + ' ' + r.company + ' ' + (r.reason||'') + ' ' + (r.location||'')).toLowerCase().includes(q)));
  const dir = sortAsc ? 1 : -1;
  out.sort((a, b) => {
    let x = a[sortKey], y = b[sortKey];
    if (sortKey === 'posted_at' || sortKey === 'first_seen') { x = x || ''; y = y || ''; }
    if (typeof x === 'string') return dir * x.localeCompare(y);
    if (x !== y) return dir * (x - y);
    if (a.relevance !== b.relevance) return b.relevance - a.relevance;
    if (a.fit !== b.fit) return b.fit - a.fit;
    return (b.posted_at || '').localeCompare(a.posted_at || '');
  });
  return out;
}
function render(){
  const out = rows();
  $('#count').textContent = out.length + ' of ' + D.rows.length;
  document.querySelectorAll('th[data-k]').forEach(th => { th.classList.toggle('sorted', th.dataset.k === sortKey); th.classList.toggle('asc', th.dataset.k === sortKey && sortAsc); });
  $('#body').innerHTML = out.map(r => `
    <tr class="${seen.has(r.key) ? 'seen' : ''}" data-key="${esc(r.key)}">
      <td><input type="checkbox" ${seen.has(r.key) ? 'checked' : ''} title="seen / applied"></td>
      <td class="num">${r.relevance}</td><td class="num">${r.fit}</td>
      <td class="title"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>
        ${r.fit < D.stretch_fit ? '<span class="tag stretch">stretch</span>' : ''}
        <div class="reason">${esc(r.reason)}</div></td>
      <td>${esc(r.company)}</td>
      <td><span class="tag">${esc(D.categories[r.category] || r.category)}</span></td>
      <td><span class="tag ${r.location_fit === 'bay_area' ? 'bay' : ''}">${esc(locTag(r))}</span>${r.location_fit === 'bay_area' || r.location_fit === 'us_remote' ? '<span class="reason">' + esc(r.location) + '</span>' : ''}</td>
      <td class="num" title="${esc(r.posted_at || '')}">${age(r.posted_at)}</td>
      <td class="num" title="${esc(r.first_seen || '')}">${age(r.first_seen)}</td>
    </tr>`).join('');
}
document.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => {
  if (sortKey === th.dataset.k) sortAsc = !sortAsc; else { sortKey = th.dataset.k; sortAsc = th.dataset.k === 'title' || th.dataset.k === 'company'; }
  render();
}));
$('#body').addEventListener('change', e => {
  const tr = e.target.closest('tr'); if (!tr) return;
  if (e.target.checked) seen.add(tr.dataset.key); else seen.delete(tr.dataset.key);
  saveSeen(); render();
});
['#q', '#cat', '#loc', '#minfit', '#minrel', '#hideseen'].forEach(s => $(s).addEventListener('input', render));
render();
"""


def render_board(rows: list[dict], now: datetime, profile: dict) -> str:
    data = {
        "generated_at": now.replace(microsecond=0).isoformat(),
        "stretch_fit": profile["stretch_fit"],
        "categories": dict(CATEGORY_ORDER),
        "rows": rows,
    }
    # A literal "</script>" inside the data would end the block early; escape the slash (still valid JSON).
    payload = json.dumps(data).replace("</", "<\\/")
    cat_opts = "".join(f'<option value="{k}">{html.escape(v)}</option>' for k, v in CATEGORY_ORDER)
    loc_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in
                       [("bay_area", "Bay Area"), ("us_remote", "US remote"), ("other_us", "Other US"), ("unknown", "Unknown")])
    date = now.strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>jobwatch board</title><style>{_CSS}</style></head>
<body>
<header><h1>jobwatch board</h1><span class="meta">{len(rows)} eligible postings · last {profile["board_days"]} days · generated {date}</span></header>
<div class="controls">
  <input id="q" type="search" placeholder="search title, company, reason, location">
  <label>category <select id="cat"><option value="">all</option>{cat_opts}</select></label>
  <label>location <select id="loc"><option value="">all</option>{loc_opts}</select></label>
  <label>min fit <input id="minfit" type="number" min="0" max="10" value="{profile["min_fit"]}" style="width:4em"></label>
  <label>min rel <input id="minrel" type="number" min="0" max="10" value="{profile["min_relevance"]}" style="width:4em"></label>
  <label><input id="hideseen" type="checkbox"> hide seen</label>
  <span class="count" id="count"></span>
</div>
<table><thead><tr>
  <th title="seen / applied (stored in this browser)">✓</th>
  <th data-k="relevance" title="how much this is the work you want">rel</th>
  <th data-k="fit" title="would they realistically hire you">fit</th>
  <th data-k="title">title</th><th data-k="company">company</th><th data-k="category">category</th>
  <th data-k="location_fit">location</th><th data-k="posted_at" title="since the company posted it">posted</th>
  <th data-k="first_seen" title="since jobwatch first saw it">seen</th>
</tr></thead><tbody id="body"></tbody></table>
<script id="data" type="application/json">{payload}</script>
<script>{_JS}</script>
</body></html>
"""
