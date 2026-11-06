/* ======================================================================
   Decision models appbook — the shell.
   Utilities, the sidebar and status card, the model chooser, the Model
   context rail, the Data Explorer and the router. Pages live in
   architecture.js (reference architecture), pages.js (the five decision
   pages and the playground) and results.js (benchmark, providers,
   tokenomics). charts.js draws the inline SVG.
   ====================================================================== */

const I = {
  arch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="4" rx="1"/><rect x="3" y="17" width="5" height="4" rx="1"/><rect x="9.5" y="17" width="5" height="4" rx="1"/><rect x="16" y="17" width="5" height="4" rx="1"/><path d="M12 7v5M5.5 17v-2.5h13V17M12 12v5"/></svg>',
  bench: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  three: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 12h3M12 12l3-5M12 12l3 5"/></svg>',
  coin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v5c0 1.7 3.1 3 7 3s7-1.3 7-3V7M5 12v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/></svg>',
  window: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 13h8M8 16h5"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 6-6 6 6 6"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
};
const ORDER = ["local", "jev", "openai"];
const COLOR = { local: "#199e70", jev: "#d55181", openai: "#d95926", typical: "#3987e5", embedding: "#3987e5", gold: "#c98500" };
const LABEL = { local: "d1", jev: "Jev", openai: "OpenAI Decisions", typical: "Typical", embedding: "Embedding top-k" };
const STAGE_COLOR = { Retain: "var(--st-retain)", Refine: "var(--st-refine)", Recall: "var(--st-recall)", Reuse: "var(--st-reuse)" };
const OUTCOME = { better: { c: "var(--ok)", cls: "win" }, level: { c: "var(--text-3)", cls: "nogain" }, worse: { c: "var(--bad)", cls: "loss" } };

// ── utilities ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 3) => (v == null || isNaN(v) ? "—" : Number(v).toFixed(d));
const pct = (v, d = 0) => (v == null || isNaN(v) ? "—" : (Number(v) * 100).toFixed(d) + "%");
const ms = (v) => (v == null || isNaN(v) ? "—" : Number(v) >= 100 ? Math.round(v).toLocaleString() + " ms" : Number(v).toFixed(1) + " ms");
const usd = (v, d = 6) => (v == null || isNaN(v) ? "—" : "$" + Number(v).toFixed(d));
const int = (v) => (v == null || isNaN(v) ? "—" : Math.round(v).toLocaleString());

async function getJSON(url) {
  const r = await fetch(url);
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(errText(d, r.status));
  return d;
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(errText(d, r.status));
  return d;
}
function errText(d, status) {
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map((e) => e.msg).join("; ");
  return "HTTP " + status;
}
// A POST whose reply is a server-sent event stream: progress events, then one result (or error).
async function postStream(url, body, onProgress) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  if (!r.ok) { let d = {}; try { d = await r.json(); } catch (_) {} throw new Error(errText(d, r.status)); }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", result = null, failure = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
      let event = "message", data = "";
      block.split("\n").forEach((line) => {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      });
      if (!data) continue;
      const payload = JSON.parse(data);
      if (event === "progress" && onProgress) onProgress(payload);
      else if (event === "result") result = payload;
      else if (event === "error") failure = payload.detail;
    }
  }
  if (failure) throw new Error(failure);
  return result;
}
function setHTML(sel, html) { const el = typeof sel === "string" ? $(sel) : sel; if (el) el.innerHTML = html; }
function pill(text, cls) { return `<span class="pill ${esc(cls || "")}">${esc(text)}</span>`; }
function tile(label, value, sub) { return `<div class="tile"><div class="tk">${esc(label)}</div><div class="tv">${value}</div>${sub ? `<div class="ts">${sub}</div>` : ""}</div>`; }
function outcomePill(o) { if (!o) return pill("listed only", "listed"); const s = OUTCOME[o] || {}; return pill(o, s.cls); }
function table(columns, rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${esc(opts.empty || "Nothing yet.")}</div>`;
  const head = columns.map((c) => `<th${c.num ? ' class="num"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr class="${esc(typeof opts.rowClass === "function" ? opts.rowClass(r) : "")}">${columns.map((c) => {
    const v = typeof c.get === "function" ? c.get(r) : r[c.key];
    const cls = [c.num ? "num" : "", c.wrap ? "wrap" : "", typeof c.cls === "function" ? c.cls(r) : (c.cls || "")].filter(Boolean).join(" ");
    return `<td${cls ? ` class="${cls}"` : ""}>${c.html ? v : esc(v ?? "—")}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function fold(title, body, open = false) { return `<details class="fold"${open ? " open" : ""}><summary>${esc(title)}</summary><div>${body}</div></details>`; }
function json(v) { return `<pre class="json">${esc(JSON.stringify(v, null, 1))}</pre>`; }
function pbars(probs, color, limit = 6) {
  const rows = Object.entries(probs || {}).sort((a, b) => b[1] - a[1]).slice(0, limit);
  return `<div class="pbars" style="--c:${color}">${rows.map(([k, v], i) => `<div class="pbar-row${i === 0 ? " top" : ""}"><span title="${esc(k)}">${esc(k)}</span><span class="track"><i style="width:${Math.max(1, v * 100)}%"></i></span><b>${num(v, 2)}</b></div>`).join("")}</div>`;
}
function meta(rec) {
  if (!rec || rec.error) return "";
  return `<div class="meta"><span><b>${ms(rec.ms)}</b></span><span><b>${int(rec.input_tokens)}</b> input tokens</span><span><b>${usd(rec.usd, 7)}</b>${rec.backend === "local" ? " at Liquid's rate" : ""}</span></div>`;
}
function howto(points) { return `<div class="howto"><b>How to read it.</b><ul>${points.map((p) => `<li>${p}</li>`).join("")}</ul></div>`; }
function banner(text) { return `<div class="banner warn">${I.alert}<div>${text}</div></div>`; }

// ── tooltip ───────────────────────────────────────────────────────────
function tip(e, html) {
  const t = $("#tooltip");
  if (!t) return;
  if (!html) { t.hidden = true; return; }
  t.innerHTML = html; t.hidden = false;
  const x = Math.min(e.clientX + 14, window.innerWidth - t.offsetWidth - 8);
  const y = Math.min(e.clientY + 14, window.innerHeight - t.offsetHeight - 8);
  t.style.left = x + "px"; t.style.top = y + "px";
}
function bindTips(root) {
  $$("[data-tip]", root).forEach((el) => {
    el.addEventListener("mousemove", (e) => tip(e, el.getAttribute("data-tip")));
    el.addEventListener("mouseleave", (e) => tip(e, null));
  });
}

// ── state, the model chooser ──────────────────────────────────────────
const state = { health: null, route: "home", selected: null };
function loadSelected() {
  try { const v = JSON.parse(localStorage.getItem("dm-models") || "null"); if (Array.isArray(v)) return v; } catch (_) {}
  return ORDER.slice();
}
function saveSelected() { try { localStorage.setItem("dm-models", JSON.stringify(state.selected)); } catch (_) {} }
function availableModels() { const m = state.health?.models || {}; return ORDER.filter((k) => !m[k] || m[k].available); }
function chosen() { const ok = availableModels(); return state.selected.filter((k) => ok.includes(k)); }
function chooser(id, opts = {}) {
  const m = state.health?.models || {};
  const chips = ORDER.map((k) => {
    const info = m[k] || {};
    const ok = !m[k] || info.available;
    const on = ok && state.selected.includes(k);
    const sub = k === "local" ? (info.state === "loaded" ? (info.where || "") : info.state || "") : (ok ? "" : "no key");
    return `<button class="mchip ${on ? "on" : ""}" data-m="${k}" style="--c:${COLOR[k]}" ${ok ? "" : "disabled"} title="${esc((info.model || "") + " · " + (info.where || ""))}"><i></i>${esc(LABEL[k])}${sub ? ` <small>${esc(sub)}</small>` : ""}</button>`;
  }).join("");
  const typ = opts.typical ? `<label class="mchip ${state.typical ? "on" : ""}" style="--c:${COLOR.typical}" id="${id}-typ" title="${esc(opts.typical)}"><input type="checkbox" hidden ${state.typical ? "checked" : ""}/><i></i>${esc(opts.typicalLabel || "Typical path")} <small>${state.health?.typical?.llm ? esc(state.health.typical.chat_model) : "no key"}</small></label>` : "";
  return `<div class="chooser" id="${id}">${chips}${typ}</div>`;
}
function bindChooser(id, onChange) {
  $$(`#${id} [data-m]`).forEach((b) => b.addEventListener("click", () => {
    const k = b.dataset.m;
    state.selected = state.selected.includes(k) ? state.selected.filter((x) => x !== k) : [...state.selected, k];
    saveSelected(); b.classList.toggle("on", state.selected.includes(k));
    if (onChange) onChange();
  }));
  const typ = $(`#${id}-typ`);
  if (typ) typ.addEventListener("click", (e) => {
    e.preventDefault();
    if (!state.health?.typical?.llm) return;
    state.typical = !state.typical; typ.classList.toggle("on", state.typical);
  });
}
function needModels() { return chosen().length ? "" : banner("Choose at least one decision model above. d1 runs on this machine; Jev and OpenAI Decisions need their keys in <span class=\"mono\">.env</span>."); }

// ── sidebar, theme, status ────────────────────────────────────────────
const NAV = [
  { group: "Reference" },
  { href: "#/", id: "home", node: I.arch, label: "Reference architecture", c: "#a78bfa" },
  { group: "The seven swaps" },
  { href: "#/chunking", id: "chunking", node: "1", label: "Semantic chunking", c: "var(--st-retain)" },
  { href: "#/reranking", id: "reranking", node: "2", label: "Reranking", c: "var(--st-recall)" },
  { href: "#/cache", id: "cache", node: "3", label: "Semantic cache", c: "var(--st-recall)" },
  { href: "#/routing", id: "routing", node: "4", label: "Memory routing", c: "var(--st-recall)" },
  { href: "#/consolidation", id: "consolidation", node: "5", label: "Consolidation and dedup", c: "var(--st-refine)" },
  { href: "#/extraction", id: "extraction", node: "6", label: "Memory extraction", c: "var(--st-retain)" },
  { href: "#/tools", id: "tools", node: "7", label: "Tool selection", c: "var(--st-reuse)" },
  { group: "Measure" },
  { href: "#/scoreboard", id: "scoreboard", node: I.bench, label: "Scoreboard", c: "#3987e5" },
  { href: "#/providers", id: "providers", node: I.three, label: "Three decision models", c: "#199e70" },
  { href: "#/tokenomics", id: "tokenomics", node: I.coin, label: "Tokenomics", c: "#c98500" },
];
function renderSidebar(active) {
  let delay = 0;
  const items = NAV.map((n) => {
    if (n.group) return `<div class="nav-group">${esc(n.group)}</div>`;
    delay += 30;
    const isText = !n.node.startsWith("<svg");
    return `<a class="nav-item ${active === n.id ? "active" : ""}" href="${n.href}" title="${esc(n.label)}" aria-label="${esc(n.label)}" style="--c:${n.c};animation-delay:${delay}ms"><span class="nav-node${isText ? " num" : ""}">${n.node}</span><span class="nav-label">${esc(n.label)}</span></a>`;
  }).join("");
  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.arch}</span>
      <span class="brand-text"><b>Decision models</b><span>in agent memory</span></span>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button"></button>
    </div>
    <nav class="ladder-rail" aria-label="Pages">${items}
      <a class="nav-item" href="#" id="nav-explorer" title="Data Explorer" aria-label="Data Explorer" style="--c:#fb923c"><span class="nav-node">${I.db}</span><span class="nav-label">Data Explorer</span></a>
    </nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle" type="button"><span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span>${themeLabel()}</span></span><span class="toggle-track"></span></button>
    </div>`;
  syncSidebarToggle();
  $("#sidebar-toggle").addEventListener("click", toggleSidebar);
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#nav-explorer").addEventListener("click", (e) => { e.preventDefault(); toggleExplorer(true); });
  bindStatus();
}
function sidebarCollapsed() { return document.documentElement.getAttribute("data-sidebar") === "collapsed"; }
function syncSidebarToggle() {
  const t = $("#sidebar-toggle"); if (!t) return;
  const c = sidebarCollapsed();
  t.innerHTML = c ? I.expand : I.collapse;
  t.setAttribute("aria-label", c ? "Expand side navigation" : "Collapse side navigation");
}
function toggleSidebar() {
  const next = sidebarCollapsed() ? "expanded" : "collapsed";
  document.documentElement.setAttribute("data-sidebar", next);
  try { localStorage.setItem("dm-sidebar", next); } catch (_) {}
  syncSidebarToggle();
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("dm-theme", next); } catch (_) {}
  renderSidebar(state.route);
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const m = h.models;
  const local = m.local.state;
  const ldot = local === "loaded" ? "ok" : local === "loading" ? "warn pulse" : local === "failed" ? "off" : "off";
  const row = (k, dot, text, extra = "") => `<div class="status-row"><span class="k">${k}</span><span class="dot ${dot}"></span><span>${text}</span>${extra}</div>`;
  return row("d1", ldot, esc(local === "loaded" ? `loaded · ${m.local.where}` : local), local === "not loaded" ? `<button class="mini" id="load-d1" title="Load LiquidAI/d1-2B (about 7 GB)">Load</button>` : "")
    + row("Jev", m.jev.available ? "ok" : "off", m.jev.available ? esc(m.jev.model) : "no key")
    + row("OpenAI", m.openai.available ? "ok" : "off", m.openai.available ? esc(m.openai.model) : "no key")
    + row("Session", "ok", `<span class="mono" title="${esc(h.session.id)}">${esc(h.session.id.slice(-11))}</span> · ${h.session.decisions}`, `<button class="mini" id="reset-session" title="Start a new lab session${h.cleanup ? " and delete this one's store" : "; this one's store and log are kept"}">Reset</button>`);
}
function bindStatus() {
  const load = $("#load-d1");
  if (load) load.addEventListener("click", async () => { await postJSON("/api/models/local/load"); await refreshHealth(); });
  const reset = $("#reset-session");
  if (reset) reset.addEventListener("click", async () => { await postJSON("/api/session/reset"); await refreshHealth(); renderCtxRail(null); route(); });
}
async function refreshHealth() {
  try { state.health = await getJSON("/api/health"); } catch (_) {}
  const c = $("#status-card"); if (c) { c.innerHTML = statusInner(); bindStatus(); }
}
function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "#199e70");
  stage.innerHTML = `<div class="view wide view-enter">${html}</div>`;
  stage.scrollTop = 0;
}

// ── the Model context rail ────────────────────────────────────────────
function ctxRailCollapsed() { return document.documentElement.getAttribute("data-ctxrail") === "collapsed"; }
function syncCtxRailToggle() {
  const t = $("#ctxrail-toggle"); if (!t) return;
  const c = ctxRailCollapsed();
  t.innerHTML = c ? I.collapse : I.expand;
  t.setAttribute("aria-label", c ? "Expand the model context panel" : "Collapse the model context panel");
}
function toggleCtxRail() {
  const next = ctxRailCollapsed() ? "expanded" : "collapsed";
  document.documentElement.setAttribute("data-ctxrail", next);
  try { localStorage.setItem("dm-ctxrail", next); } catch (_) {}
  syncCtxRailToggle();
}
function renderCtxRail(entry) {
  const el = $("#ctxrail"); if (!el) return;
  if (!entry) {
    el.innerHTML = `<div class="ctx-title">${I.window} Model context</div><div class="ctx-empty">Ask a decision on any page: this rail shows exactly what each model received and what it answered.</div>`;
    return;
  }
  const cards = Object.entries(entry.calls).map(([k, c]) => {
    const color = COLOR[k] || COLOR.typical;
    const head = `<h4><span>${esc(c.label || LABEL[k] || k)}</span><small>${c.kind === "batch" ? `${int(c.count)} requests · ` : ""}${ms(c.ms)}</small></h4>`;
    if (c.error) return `<div class="ctx-model" style="--c:${color}">${head}<div class="acard"><span class="err">${esc(c.error)}</span></div></div>`;
    const req = c.request ? `<details><summary>request as sent${k === "openai" ? " (translated)" : ""}</summary>${json(c.request)}</details>` : "";
    const ans = c.answers ? `<details open><summary>answers${k === "openai" ? ", in d1's shape" : ""}</summary>${json(c.answers)}</details>` : "";
    const raw = c.raw && k === "openai" ? `<details><summary>raw reply from /v1/decisions</summary>${json(c.raw)}</details>` : "";
    return `<div class="ctx-model" style="--c:${color}">${head}<div class="ctx-sub">${int(c.input_tokens)} input tokens · ${usd(c.usd, 7)}${c.model ? ` · ${esc(c.model)}` : ""}</div>${req}${ans}${raw}</div>`;
  }).join("");
  el.innerHTML = `<div class="ctx-title">${I.window} Model context</div>
    <div class="ctx-sub">#${entry.n} · ${esc(entry.page)}</div>
    <div class="masked" style="margin-top:0">${esc((entry.summary || "").slice(0, 280))}</div>
    ${cards}
    <div class="ctx-foot">Jev and d1 take the same request; OpenAI's is translated by the harness, and its answers are translated back. Keys never leave the server.</div>`;
}
async function refreshCtx() {
  try { const s = await getJSON("/api/session"); renderCtxRail(s.last); } catch (_) {}
  refreshHealth();
  if ($("#data-explorer").classList.contains("open")) loadActivity();
}

// ── Data Explorer (read-only) ─────────────────────────────────────────
const explorer = { tables: [], selected: null, offset: 0, limit: 40, scope: "session", token: 0 };
function toggleExplorer(force) {
  const el = $("#data-explorer");
  const open = force ?? !el.classList.contains("open");
  el.classList.toggle("open", open);
  $("#explorer-body").hidden = !open;
  $("#explorer-toggle").setAttribute("aria-expanded", String(open));
  document.body.classList.toggle("explorer-open", open);
  if (open) { loadExplorerTables(); loadActivity(); }
}
async function loadExplorerTables() {
  try {
    const d = await getJSON(`/api/data_explorer/tables?scope=${explorer.scope}`);
    explorer.tables = d.tables;
    $("#explorer-summary").textContent = `${d.tables.length} tables · session ${d.session.slice(-11)}`;
    renderExplorerList();
    if (!explorer.selected && d.tables.length) selectExplorer("session_decisions", 0);
  } catch (e) { $("#explorer-summary").textContent = e.message; }
}
function renderExplorerList() {
  const f = ($("#explorer-filter").value || "").toLowerCase();
  let group = "";
  $("#explorer-table-list").innerHTML = explorer.tables.filter((t) => !f || t.name.includes(f)).map((t) => {
    const head = t.group !== group ? `<div class="nav-group" style="padding:10px 6px 4px">${esc(t.group)}</div>` : "";
    group = t.group;
    return `${head}<button class="explorer-table-item ${explorer.selected === t.name ? "selected" : ""}" data-t="${esc(t.name)}" title="${esc(t.role)}"><span><i></i>${esc(t.name)}</span><b>${t.rows < 0 ? "—" : t.rows.toLocaleString()}</b></button>`;
  }).join("");
  $$("#explorer-table-list [data-t]").forEach((b) => b.addEventListener("click", () => selectExplorer(b.dataset.t, 0)));
}
async function selectExplorer(name, offset) {
  explorer.selected = name; explorer.offset = offset;
  $$("#explorer-table-list [data-t]").forEach((b) => b.classList.toggle("selected", b.dataset.t === name));
  const token = ++explorer.token;
  try {
    const d = await getJSON(`/api/data_explorer/tables/${encodeURIComponent(name)}/rows?limit=${explorer.limit}&offset=${offset}&scope=${explorer.scope}`);
    if (token !== explorer.token) return;
    $("#explorer-table-name").textContent = d.table;
    $("#explorer-role").textContent = d.role;
    $("#explorer-page").textContent = `${d.rows.length ? offset + 1 : 0}–${offset + d.rows.length} of ${d.total.toLocaleString()}`;
    $("#explorer-prev").disabled = offset === 0;
    $("#explorer-next").disabled = offset + d.rows.length >= d.total;
    const cell = (v) => v == null ? '<span class="explorer-null">NULL</span>' : esc(typeof v === "object" ? JSON.stringify(v) : String(v));
    $("#explorer-grid").innerHTML = d.rows.length ? `<table class="explorer-data-table"><thead><tr>${d.columns.map((c) => `<th><span>${esc(c)}</span></th>`).join("")}</tr></thead><tbody>${d.rows.map((r) => `<tr>${d.columns.map((c) => `<td>${cell(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>` : '<div class="explorer-empty">No rows yet.</div>';
  } catch (e) { $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(e.message)}</div>`; }
}
async function loadActivity() {
  try {
    const d = await getJSON("/api/data_explorer/activity");
    $("#explorer-activity-list").innerHTML = d.activity.length ? d.activity.map((a) => `<div class="explorer-activity-event ${a.op === "write" ? "write" : "read"}"><i></i><span>${esc(a.what)}</span><b>${esc(a.at)}</b></div>`).join("") : '<div class="explorer-empty">Nothing yet in this session.</div>';
  } catch (_) {}
}
function initExplorer() {
  $("#explorer-toggle").addEventListener("click", () => toggleExplorer());
  $("#explorer-refresh").addEventListener("click", loadExplorerTables);
  $("#explorer-filter").addEventListener("input", renderExplorerList);
  $("#explorer-prev").addEventListener("click", () => selectExplorer(explorer.selected, Math.max(0, explorer.offset - explorer.limit)));
  $("#explorer-next").addEventListener("click", () => selectExplorer(explorer.selected, explorer.offset + explorer.limit));
  $("#explorer-scope").addEventListener("click", (e) => {
    explorer.scope = explorer.scope === "session" ? "all" : "session";
    e.currentTarget.textContent = explorer.scope === "session" ? "This session" : "All stores";
    e.currentTarget.classList.toggle("active", explorer.scope === "session");
    loadExplorerTables(); if (explorer.selected) selectExplorer(explorer.selected, 0);
  });
}

// ── router and boot ───────────────────────────────────────────────────
const SWAP_IDS = ["chunking", "reranking", "cache", "routing", "consolidation", "extraction", "tools"];
function routes() {
  const r = { "": viewArchitecture, scoreboard: viewScoreboard, providers: viewProviders, tokenomics: viewTokenomics };
  SWAP_IDS.forEach((id) => { r[id] = () => viewSwap(id); });
  return r;
}
function route() {
  tip(null, null);
  const id = location.hash.replace(/^#\/?/, "").split("?")[0].trim();
  state.route = id || "home";
  renderSidebar(state.route);
  (routes()[id] || viewArchitecture)();
  if (window.innerWidth <= 760) closeMenu();
}
function openMenu() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }
async function boot() {
  state.selected = loadSelected();
  state.typical = false;
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);
  $("#ctxrail-mini").innerHTML = `${I.window}<span>Model context</span>`;
  $("#ctxrail-toggle").addEventListener("click", toggleCtxRail);
  $("#ctxrail-mini").addEventListener("click", toggleCtxRail);
  syncCtxRailToggle();
  window.addEventListener("hashchange", route);
  initExplorer();
  try { state.health = await getJSON("/api/health"); } catch (_) {}
  route();
  refreshCtx();
  setInterval(refreshHealth, 10000);
}
window.addEventListener("DOMContentLoaded", boot);
