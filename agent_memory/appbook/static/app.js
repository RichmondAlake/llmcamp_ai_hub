import {lessons, glossary, architecture, starter, probes} from './content.js';

const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => value == null ? '—' : Number(value).toLocaleString();
const short = value => (value || '').slice(0, 8);
const clock = value => new Date(value).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
const readLocal = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const paths = {
  menu:'M4 6h16M4 12h16M4 18h16', close:'m6 6 12 12M6 18 18 6',
  home:'m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9',
  compress:'M5 3v6h6M19 21v-6h-6M5 9l5-5M19 15l-5 5',
  archive:'M3 3h18v5H3zM5 8v13h14V8M10 12h4',
  compare:'M9 3v18M15 3v18M2 9l3 3-3 3M22 9l-3 3 3 3',
  notes:'M5 3h14v18H5zM8 7h8M8 11h8M8 15h5',
  arrow:'M5 12h14m-6-6 6 6-6 6', left:'m15 5-7 7 7 7', right:'m9 5 7 7-7 7',
  send:'M12 19V5m-6 6 6-6 6 6', plus:'M12 5v14M5 12h14',
  panel:'M3 4h18v16H3zM14 4v16', search:'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14m5-2 5 5',
  settings:'M4 7h16M4 17h16M8 4v6M16 14v6',
  book:'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3zM12 6v15',
  download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  play:'m8 4 12 8-12 8z', chevron:'m6 9 6 6 6-6', check:'m5 12 4 4L19 6',
  bolt:'m13 2-9 12h7l-1 8 10-13h-7z', external:'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',
  info:'M12 11v6M12 7v1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
};
const icon = (name, cls='') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[name] || paths.info}"/></svg>`;
const textHtml = text => escape(text).replace(/```(?:[a-z]+)?\n([\s\S]*?)```/g,'<pre>$1</pre>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/\n/g,'<br>');

const state = {
  route: location.hash.slice(1) || 'home', collapsed: readLocal('appbook.nav', false),
  settings: readLocal('appbook.settings', {model:'gpt-6-astra', effort:'low', budget:6000, notes_budget:2400, diagnostic_checks:120}),
  ids: readLocal('appbook.sessions', {}), sessions: {}, list: [], busy: new Set(),
  inspector: true, inspectorTab: 'context', windowIndex: {}, drafts: {}, searchResults: {},
  architecture: 'notes', loading: false, config: {}, errors: {},
};
if (innerWidth <= 650 && !localStorage.getItem('appbook.nav')) state.collapsed = true;

async function api(path, method='GET', body) {
  const response = await fetch('/api' + path, {method, headers: body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
  return value;
}
function toast(text) {
  const element = $('#toast'); element.textContent = text; element.classList.add('visible');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => element.classList.remove('visible'), 5000);
}
function persist() {
  localStorage.setItem('appbook.sessions', JSON.stringify(state.ids));
  localStorage.setItem('appbook.settings', JSON.stringify(state.settings));
  localStorage.setItem('appbook.nav', JSON.stringify(state.collapsed));
}
function currentSessions() {
  const ids = state.ids[state.route];
  return (Array.isArray(ids) ? ids : ids ? [ids] : []).map(id=>state.sessions[id]).filter(Boolean);
}
const isBusy = session => !!session && (state.busy.has(session.id) || session.busy);
const labBusy = () => state.loading || currentSessions().some(isBusy);
const disabled = value => value ? ' disabled' : '';

function sidebar() {
  return `<aside class="sidebar" aria-label="Appbook navigation">
    <a href="#home" class="brand" aria-label="LLMCAMP home"><span class="brand-mark">A</span><span class="brand-name">LLMCAMP<span>THE APPBOOK SERIES</span></span></a>
    <div class="nav-label">AGENT MEMORY <span>01</span></div>
    <nav><a href="#home" title="Field guide" class="nav-link ${state.route==='home'?'active':''}">${icon('home')}<span>Field guide</span></a>
      <div class="nav-divider"></div>${Object.entries(lessons).map(([key,lesson])=>`<a href="#${key}" title="${lesson.name}" class="nav-link ${state.route===key?'active':''}"><span class="nav-number">${lesson.number}</span><span>${lesson.name}</span>${state.route===key?'<i></i>':''}</a>`).join('')}
    </nav>
    <div class="sidebar-bottom"><div class="sidebar-note"><span class="tiny-label">LEARN BY INSPECTING</span><p>The conversation is the surface.<br>The context is the mechanism.</p></div>
      <a class="nav-link" href="/resources/notebook">${icon('book')}<span>Source notebook</span>${icon('download','end-icon')}</a>
      <button class="nav-link collapse-button" data-action="collapse" aria-label="${state.collapsed?'Expand':'Collapse'} navigation" aria-expanded="${!state.collapsed}">${icon(state.collapsed?'right':'left')}<span>Collapse navigation</span></button>
    </div>
  </aside>`;
}

function header() {
  return `<header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-nav" data-action="collapse" aria-label="Toggle navigation">${icon('menu')}</button><span>APPBOOK / 01</span><i></i><span>${state.route==='home'?'Agent memory':lessons[state.route]?.name || 'Agent memory'}</span></div>
    <div class="topbar-actions"><span class="connection ${state.config.ready?'ready':''}"><i></i>${state.config.ready?'API configured':'API key needed'}</span>
    <button class="model-button" data-action="settings">${icon('settings')}<span>${escape(currentSessions()[0]?.model || state.settings.model)}</span>${icon('chevron')}</button></div></header>`;
}

function home() {
  return `<main id="main" class="home-page" tabindex="-1">
    <section class="hero"><div><div class="eyebrow"><span class="gold-line"></span>AGENT MEMORY & CONTEXT ENGINEERING</div>
      <h1>What does your agent<br>actually <em>remember?</em></h1>
      <p class="hero-copy">An interactive field guide to the space between a conversation<br class="wide-only"> and what a model knows. Talk to an agent. Open its context.<br class="wide-only"> Change its memory. See what survives.</p>
      <div class="hero-actions"><a class="button primary" href="#summary">Enter the memory lab ${icon('arrow')}</a><a class="text-link" href="https://www.youtube.com/watch?v=WWUB9W5pl2w" target="_blank" rel="noreferrer">${icon('play')} Watch the webinar ${icon('external')}</a></div>
    </div><div class="hero-emblem" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="orbit orbit-three"></div><div class="memory-core">M<span>CONTEXT ≠ MEMORY</span></div><span class="orbit-label label-one">RETAIN</span><span class="orbit-label label-two">RECALL</span><span class="orbit-label label-three">REUSE</span></div></section>
    <div class="intro-strip"><span><b>03</b> memory mechanisms</span><span><b>04</b> interactive labs</span><span>${icon('bolt')} Real OpenAI responses</span><span>${icon('search')} Inspectable evidence</span></div>
    <section class="section-block"><div class="section-heading"><div><div class="eyebrow">THE LEARNING PATH</div><h2>Same agent. Different memory.</h2></div><span class="muted small">Start with loss. Build towards recovery.</span></div>
      <div class="lesson-grid">${Object.entries(lessons).map(([key,l])=>`<a class="lesson-card ${l.color}" href="#${key}"><div class="card-top"><span class="card-number">${l.number} / LAB</span>${icon(l.icon)}</div><h3>${l.name}</h3><p>${l.short}</p><span class="card-link">Open lab ${icon('arrow')}</span></a>`).join('')}</div>
    </section>
    <section class="architecture-section section-block"><div class="section-heading"><div><div class="eyebrow">REFERENCE ARCHITECTURES</div><h2>Follow the information.</h2></div><div class="segmented" aria-label="Architecture diagram">${['summary','offload','notes'].map(key=>`<button data-action="architecture" data-kind="${key}" class="${state.architecture===key?'selected':''}" aria-pressed="${state.architecture===key}">${lessons[key].name}</button>`).join('')}</div></div>
      <div class="architecture-card"><div class="architecture-text"><span class="tag ${lessons[state.architecture].color}">${lessons[state.architecture].eyebrow}</span><h3>${lessons[state.architecture].short}</h3><p>${lessons[state.architecture].definition}</p><a class="text-link" href="#${state.architecture}">Explore this mechanism ${icon('arrow')}</a></div><div class="diagram-container">${architecture(state.architecture)}</div></div>
    </section>
    <section class="source-section section-block"><div><div class="eyebrow">THE OBSERVATION BEHIND THE BUILD</div><h2>Notes should accumulate.<br>Evidence should remain findable.</h2><p>Repeated compaction can drop the reason a fix failed or the way a component behaves. The Astra release describes notes that survive context windows, alongside searchable earlier messages and tool outputs.</p><blockquote>“Astra can keep notes across context windows, preserving accumulated details without repeatedly compressing them into a single summary.”</blockquote><a class="text-link" href="https://openai.com/index/gpt-6-astra/" target="_blank" rel="noreferrer">OpenAI · GPT-6 Astra release ${icon('external')}</a></div><div class="source-note"><span class="tiny-label">WHAT THIS APPBOOK IMPLEMENTS</span><h3>An observable pattern.<br>An explicit design.</h3><p>The append-only notes, typed evidence, 80% trigger, small input budget, search ranking and prompts here are our implementation choices. OpenAI’s paragraph does not disclose its internal algorithms.</p><p>Adapted from the companion notebook and styled after Richmond Alake’s <em>Unpacking Agent Memory Patterns in GPT-6 Astra</em> presentation.</p><a class="text-link" href="/resources/notebook">Explore the source notebook ${icon('book')}</a></div></section>
    <section class="section-block"><div class="section-heading"><div><div class="eyebrow">A SHARED VOCABULARY</div><h2>Know what you’re looking at.</h2></div></div><div class="glossary-grid">${glossary.map(([term,definition])=>`<details class="glossary-item"><summary>${term}${icon('plus')}</summary><p>${definition}</p></details>`).join('')}</div></section>
    <footer class="home-footer"><span>LLMCAMP · Built to be understood.</span><span>Local memory. Live model calls. Visible mechanisms.</span></footer>
  </main>`;
}

function labHeader() {
  const lesson = lessons[state.route];
  return `<section class="lab-heading"><div class="eyebrow"><span class="color-dot ${lesson.color}"></span>LAB ${lesson.number} / ${lesson.eyebrow}</div><div class="lab-title-row"><div><h1>${lesson.title}</h1><p>${lesson.intro}</p></div><button class="button ghost" data-action="lesson">${icon('book')} Read the mechanism</button></div>
    <div class="lab-steps">${lesson.steps.map((s,i)=>`<span><b>${i+1}</b>${s}</span>${i<2?icon('right'):''}`).join('')}<span class="teaching-badge">Teaching budget · real token counts</span></div></section>`;
}

function sessionToolbar(sessions) {
  const busy = labBusy();
  const history = state.route==='compare'
    ? state.list.filter(s=>s.group_id && s.mode==='summary').map(s=>({...s,id:s.group_id}))
    : state.list.filter(s=>s.mode===state.route && !s.group_id);
  return `<div class="session-toolbar"><div class="session-identity"><span class="live-dot"></span><span>${sessions.length===2?'PAIRED SESSIONS':'SESSION'} <code>${sessions.map(s=>short(s.id)).join(' / ')}</code></span><select class="session-select" aria-label="Resume a previous session" data-action="resume"${disabled(busy)}><option value="">Session history</option>${history.map(s=>`<option value="${s.id}">${short(s.id)} · ${s.window_count} windows · ${clock(s.created_at)}</option>`).join('')}</select></div>
    <div class="toolbar-actions"><button class="button small ghost" data-action="new"${disabled(busy)}>${icon('plus')} New ${state.route==='compare'?'pair':'session'}</button><button class="icon-button ${state.inspector?'selected':''}" data-action="inspector" aria-label="${state.inspector?'Collapse':'Show'} context inspector" aria-expanded="${state.inspector}">${icon('panel')}</button></div></div>`;
}

function reductionCard(session, reduction, inline=false) {
  const savings = reduction.saved_tokens;
  return `<div class="reduction-card ${session.mode}" data-reduction="${reduction.id}"><div class="reduction-icon">${icon(lessons[session.mode].icon)}</div><div><strong>${reduction.automatic?'80% threshold · ':''}${session.mode==='notes'?'Notes carried forward':session.mode==='summary'?'Context summarised':'Context offloaded'}</strong><span>W${session.windows.find(w=>w.id===reduction.before_window_id)?.number} → W${session.windows.find(w=>w.id===reduction.after_window_id)?.number} <i>·</i> ${number(reduction.before_tokens)} → ${number(reduction.after_tokens)} tokens</span></div><button class="reduction-delta ${savings<0?'negative':''}" data-action="reduction" data-session="${session.id}" data-id="${reduction.id}" title="Inspect before and after">${savings>=0?'−':'+'}${number(Math.abs(savings))} <span>${savings>=0?'tokens':'overhead'} ${icon('external')}</span></button></div>`;
}

function chatPanel(session, compare=false) {
  const busy = isBusy(session);
  const lesson = lessons[session.mode];
  return `<section class="chat-panel ${compare?'comparison-chat':''}" aria-label="${lesson.name} chat"><div class="chat-heading"><span class="agent-avatar ${lesson.color}">A</span><div><strong>${compare?lesson.name:'Memory lab assistant'}</strong><span>${escape(session.model)} · ${compare?lesson.short:'Your conversation, with the mechanics exposed'}</span></div><span class="tag ${lesson.color}">W${session.windows.length}</span></div>
    <div class="chat-messages" data-scroll="chat-${session.id}" aria-label="Conversation history">
      ${session.messages.length ? session.messages.map(m=>m.role==='transition' ? reductionCard(session,session.reductions.find(r=>r.id===m.reduction_id),true) : `<article class="message ${m.role}"><div class="message-meta">${m.role==='user'?'YOU':'ASSISTANT'}<span>W${m.window_number} · ${clock(m.created_at)}</span></div><div class="message-body">${textHtml(m.text)}</div></article>`).join('') : `<div class="empty-chat"><span class="empty-mark ${lesson.color}">${icon(lesson.icon)}</span><h3>Start with something<br>worth remembering.</h3><p>Tell the agent a few facts, or run the release diagnostic to create real tool evidence.</p>${!compare?`<button class="starter-card" data-action="starter"><span class="tiny-label">GUIDED EXPERIMENT</span><strong>Mina’s release & the failed clock fix ${icon('arrow')}</strong><span>A Python diagnostic, an incidental marker, and a reason to remember.</span></button>`:''}</div>`}
      ${busy?`<div class="working-indicator" role="status"><span class="spinner"></span><span>${escape(session.status==='Ready'?'Preparing request…':session.status)}</span></div>`:''}
      ${session.error?`<div class="error-card" role="alert">${icon('info')}<div><strong>This action needs attention</strong><p>${escape(session.error)}</p></div></div>`:''}
    </div>
    <div class="chat-footnote">Chat history stays visible. Only the active context is sent to the model.</div>
  </section>`;
}

function contextItem(item, index) {
  const label = item.kind==='reasoning'?'opaque API state':item.kind==='function_call'?'tool call':item.kind==='function_call_output'?'tool result':item.role;
  return `<details data-disclosure="${item.event_id}" class="context-item ${item.origin==='seed'?'seed':''}" ${item.origin==='seed'?'open':''}><summary><span class="item-index">${String(index+1).padStart(2,'0')}</span><span>${label}</span><span class="origin-tag">${item.origin}</span>${icon('chevron')}</summary><div class="context-item-content"><pre>${escape(item.text)}</pre><div class="source-line">${escape(item.source)}:${item.line}</div>${item.call_id?`<code class="source-line">call_id: ${escape(item.call_id)}</code>`:''}</div></details>`;
}

function contextView(session) {
  const index = state.windowIndex[session.id] ?? session.windows.length-1;
  const win = session.windows[Math.max(0,Math.min(index,session.windows.length-1))];
  const tokens = win.tokens;
  const percent = tokens == null ? 0 : tokens / session.budget * 100;
  return `<div class="window-navigation"><button class="icon-button" data-action="window-prev" data-session="${session.id}" aria-label="Previous context window"${disabled(win.number===1)}>${icon('left')}</button><div><strong>Window ${win.number}<span class="window-state ${win.active?'active':''}">${win.active?'ACTIVE':'ARCHIVED'}</span></strong><code>${short(win.id)} · ${clock(win.created_at)}</code></div><button class="icon-button" data-action="window-next" data-session="${session.id}" aria-label="Next context window"${disabled(win.active)}>${icon('right')}</button></div>
    <div class="token-meter"><div class="token-heading"><strong>${number(tokens)}<span> / ${number(session.budget)}</span></strong><span>${tokens==null?'Not measured':percent.toFixed(1)+'%'}</span></div><div class="meter-track"><div style="width:${Math.min(100,percent)}%" class="${percent>=80?'near-limit':''}"></div><i style="left:80%" title="80% rollover threshold"></i></div><div class="meter-caption"><span>APPLICATION INPUT BUDGET</span><span>80% ${session.mode==='notes'?'auto rollover':'guide'}</span></div></div>
    <div class="context-explainer">${win.active?'These are the items in the next request.':'This window is archived. These items are not automatically sent again.'} Counts include shared instructions and tool schemas. Opaque reasoning is preserved but hidden.</div>
    <details data-disclosure="envelope-${session.id}" class="request-envelope"><summary>${icon('settings')} Shared request envelope ${icon('chevron')}</summary><p>Model: <code>${escape(session.model)}</code><br>Reasoning effort: ${escape(session.effort || 'model default')}<br>Latest user statement wins. Treat memory as evidence. Never invent missing facts.</p><p>Tools: multiply, read_diagnostic_log${session.mode==='offload'?', just_in_time_retrieval':session.mode==='notes'?', search_notes, search_session':''}.</p><p>The count uses the full request envelope. The physical model window is separate from this teaching budget.</p>${session.request_envelope?`<pre class="envelope-json">${escape(JSON.stringify(session.request_envelope,null,2))}</pre>`:''}</details>
    <div class="context-items">${win.items.length?win.items.map(contextItem).join(''):'<div class="empty-small">Your first message will appear here.<br>Nothing is sent until you start chatting.</div>'}</div>
    <div class="inspector-footer"><span>${win.items.length} request items</span><button class="text-button" data-action="measure" data-session="${session.id}"${disabled(isBusy(session))}>${icon('bolt')} Count active window</button></div>`;
}

function notesView(session) {
  const carried = session.reductions.at(-1)?.carried_notes?.notes || [];
  return `<div class="notes-overview"><strong>${session.notes.length} durable notes</strong><span>notes_id = session_id</span><p>Typed facts and their evidence. Old entries stay unchanged. The next window carries ${carried.filter(n=>n.detail==='full').length} full entries and ${carried.filter(n=>n.detail==='headline').length} headlines.</p></div>
    ${session.notes.length?[...session.notes].reverse().map(note=>`<article class="note-card ${note.kind}"><div class="note-meta"><span>${note.kind.replace('_',' ')}</span><button data-action="source-window" data-session="${session.id}" data-window="${note.window_id}">W${note.window_number} ${icon('external')}</button></div><h4>${escape(note.headline)}</h4><p>${escape(note.content)}</p><details><summary>Evidence · ${note.evidence.length} source${note.evidence.length===1?'':'s'} ${icon('chevron')}</summary>${note.evidence.map(e=>`<blockquote>${escape(e.quote)}</blockquote><span class="source-line">W${e.window_number} · line ${e.line} · ${clock(e.created_at)}</span>`).join('')}</details><code class="note-id">${short(note.note_id)} · ${carried.find(n=>n.note_id===note.note_id)?.detail || 'searchable'}</code></article>`).join(''):'<div class="empty-small">Notes appear when you rotate a window.<br>Start with a fact or the diagnostic.</div>'}`;
}

function traceView(session) {
  const calls = session.usage;
  return `<div class="usage-summary"><div><strong>${calls.length}</strong><span>model calls</span></div><div><strong>${number(calls.reduce((a,c)=>a+c.input_tokens,0))}</strong><span>input billed</span></div><div><strong>${number(calls.reduce((a,c)=>a+c.output_tokens,0))}</strong><span>output billed</span></div></div><p class="inspector-note">Counts above come from completed API responses. ${session.count_calls} separate input-count requests. Summary and note-writing calls are included. No price estimate is substituted for measured usage.</p>
    <div class="trace-list">${[...session.trace].reverse().map(event=>`<details data-disclosure="trace-${event.id}" class="trace-entry ${event.kind}"><summary><span class="trace-dot"></span><span>${escape(event.label)}<small>W${event.window_number} · ${clock(event.created_at)}</small></span>${event.kind==='tool'?icon('bolt'):icon('chevron')}</summary><pre>${escape(JSON.stringify(event.kind==='tool'?{tool:event.tool,arguments:event.arguments,result:event.result}:event,null,2))}</pre></details>`).join('') || '<div class="empty-small">Model calls, tool execution and transitions will appear here.</div>'}</div>`;
}

function searchView(session) {
  const results = state.searchResults[session.id];
  return `<div class="search-panel"><h3>Follow a fact to its source.</h3><p>Search within this session. Original-history search excludes the active window and seed copies. This manual inspector does not add results to the model’s context.</p><form data-form="search" data-session="${session.id}"><select name="target" aria-label="Search target"><option value="session">Original closed windows</option><option value="notes">Durable notes</option></select><div class="search-input"><input name="query" id="search-query-${session.id}" data-draft-key="search-${session.id}" value="${escape(state.drafts['search-'+session.id] || '')}" placeholder="e.g. trace_marker" aria-label="Literal search query" required><button class="icon-button" aria-label="Search memory">${icon('search')}</button></div></form>${results?`<div class="search-count">${results.length} result${results.length===1?'':'s'} · newest first</div>${results.map(hit=>`<article class="search-hit"><button data-action="source-window" data-session="${session.id}" data-window="${hit.window_id}">Window ${hit.window_number} · ${clock(hit.timestamp)} ${icon('external')}</button><p>${escape(hit.excerpt)}</p><span class="source-line">${escape(hit.source)}:${hit.line}</span></article>`).join('') || '<div class="empty-small">No matching original evidence. Try a shorter literal phrase.</div>'}`:''}</div>`;
}

function inspector(session, compare=false) {
  const tab = state.inspectorTab;
  const tabs = ['context', ...(session.mode==='notes'?['notes','search']:[]), 'trace'];
  const activeTab = tabs.includes(tab)?tab:'context';
  return `<aside class="context-inspector ${compare?'compare-inspector':''}" aria-label="${lessons[session.mode].name} context inspector"><div class="inspector-heading"><div>${icon('panel')}<strong>Inside the context</strong></div><span class="tiny-label">${compare?lessons[session.mode].number:'LIVE VIEW'}</span></div><div class="inspector-tabs" role="tablist">${tabs.map(t=>`<button role="tab" aria-selected="${activeTab===t}" data-action="inspector-tab" data-tab="${t}" class="${activeTab===t?'active':''}">${t==='trace'?'Tool trace':t.charAt(0).toUpperCase()+t.slice(1)}${t==='notes'?`<span>${session.notes.length}</span>`:''}</button>`).join('')}</div><div class="inspector-body" data-scroll="inspect-${session.id}">${activeTab==='notes'?notesView(session):activeTab==='trace'?traceView(session):activeTab==='search'?searchView(session):contextView(session)}</div><div class="inspector-bottom"><a href="/api/sessions/${session.id}/export" class="text-link">${icon('download')} Export inspection data</a></div></aside>`;
}

function controlBar(sessions) {
  const busy = labBusy();
  const reduceDisabled = busy || sessions.some(s=>!s.windows.at(-1)?.items.length);
  const mode = state.route;
  return `<div class="reduction-controls"><div><button class="button reduce-button ${lessons[mode].color}" data-action="reduce"${disabled(reduceDisabled)}>${icon(lessons[mode].icon)} ${lessons[mode].action}</button>${mode==='offload'?'<select id="offload-scope" data-draft-key="offload-scope" aria-label="Offload scope"><option value="window">Whole window</option><option value="tools">Tool exchanges only</option></select>':''}${mode==='notes'?`<label class="toggle-label"><input id="auto-notes" type="checkbox" data-action="auto-notes" ${sessions[0]?.auto_rollover?'checked':''}${disabled(busy)}> Auto at 80%</label>`:''}</div><button class="text-button" data-action="policy">${icon('settings')} ${mode==='notes'?'Extraction policy':'Selection rule'}</button></div>`;
}

function composer(sessions) {
  return `<div class="composer-area"><div class="prompt-chips"><button data-action="prompt" data-prompt="retained">Ask what survived</button><button data-action="prompt" data-prompt="marker">Recover the marker</button>${state.route==='notes'?'<button data-action="prompt" data-prompt="staging">Add a W2 decision</button><button data-action="prompt" data-prompt="correction">Change the retry limit</button>':''}<button data-action="starter">${icon('bolt')} Run diagnostic</button></div><form id="chat-form" data-form="chat"><div class="composer"><textarea id="chat-input" data-draft-key="chat-${state.route}" rows="2" placeholder="${state.route==='compare'?'Send the same message to both agents…':'Ask a question, share a fact, or try a suggested experiment…'}" aria-label="Message the ${state.route==='compare'?'two agents':'agent'}"${disabled(labBusy())}>${escape(state.drafts['chat-'+state.route] || '')}</textarea><button class="send-button" aria-label="${state.route==='compare'?'Send to both agents':'Send message'}"${disabled(labBusy() || !state.config.ready)}>${labBusy()?'<span class="spinner"></span>':icon('send')}</button></div></form><div class="composer-caption"><span>${state.route==='compare'?'Two independent live calls per message. Each branch can also use tools.':'Enter to send · Shift + Enter for a new line'}</span><span>OpenAI API usage applies</span></div></div>`;
}

function notesTimeline(session) {
  return `<div class="notes-timeline"><div><span class="tiny-label">ONE SESSION · ACCUMULATING KNOWLEDGE</span><strong>${session.notes.length} notes <span>across ${session.windows.length} windows</span></strong></div><div class="window-trail">${session.windows.map(w=>`<button data-action="source-window" data-session="${session.id}" data-window="${w.id}" class="${w.active?'active':''}">W${w.number}<small>${w.active?'live':session.notes.filter(n=>n.window_id===w.id).length+' notes'}</small></button>`).join('<span>→</span>')}</div><button class="text-button" data-action="inspector-tab" data-tab="notes">Inspect notes ${icon('arrow')}</button></div>`;
}

function lab() {
  const sessions = currentSessions();
  if (!sessions.length) return `<main id="main" class="lab-page">${labHeader()}<div class="loading-state"><span class="spinner"></span>Opening your lab…</div></main>`;
  const isCompare = state.route==='compare';
  return `<main id="main" class="lab-page ${isCompare?'compare-page':''}" tabindex="-1">${labHeader()}${!state.config.ready?'<div class="setup-banner">Add OPENAI_API_KEY to appbook/.env and restart the server to use live chat. The field guide remains available.</div>':''}${sessionToolbar(sessions)}${state.route==='notes'?notesTimeline(sessions[0]):''}
    <div class="workspace ${state.inspector?'with-inspector':''} ${isCompare?'comparison-workspace':''}">${isCompare?sessions.map(s=>`<div class="comparison-branch ${s.mode}">${chatPanel(s,true)}${state.inspector?inspector(s,true):''}</div>`).join(''):`<div class="conversation-column">${chatPanel(sessions[0])}${controlBar(sessions)}${composer(sessions)}</div>${state.inspector?inspector(sessions[0]):''}`}</div>${isCompare?`<div class="comparison-controls">${controlBar(sessions)}${composer(sessions)}</div>`:''}
    <div class="lab-bottom-note">${icon('info')} ${state.route==='summary'?'A summary can lose detail. The original journal is visible to you; this assistant has no archive-search tool.':state.route==='offload'?'Pointers carry source_window_id, offload_id and tool_call_ids. Retrieval adds evidence back only when needed.':state.route==='notes'?'Notes are session-scoped working memory, stored under long_term/episodic for continuity with the notebook.':'Compare evidence and retrieval traces, not just confidence. Small windows may grow when pointer overhead exceeds the removed content.'}</div>
  </main>`;
}

function render() {
  $$('[data-draft-key]').forEach(el=>state.drafts[el.dataset.draftKey]=el.value);
  const focus = document.activeElement?.id;
  const selection = document.activeElement?.selectionStart;
  const scrolls = Object.fromEntries($$('[data-scroll]').map(el=>[el.dataset.scroll,{top:el.scrollTop,bottom:el.scrollHeight-el.scrollTop-el.clientHeight<70}]));
  const disclosures = Object.fromEntries($$('#app details[data-disclosure]').map(el=>[el.dataset.disclosure,el.open]));
  $('#app').innerHTML = `<div class="app-shell ${state.collapsed?'nav-collapsed':''}">${sidebar()}<div class="main-shell">${header()}${state.route==='home'?home():lab()}</div></div>`;
  $$('[data-draft-key]').forEach(el=>{if(state.drafts[el.dataset.draftKey]!=null)el.value=state.drafts[el.dataset.draftKey];});
  $$('[data-scroll]').forEach(el=>{const previous=scrolls[el.dataset.scroll];el.scrollTop=el.dataset.scroll.startsWith('chat-') && (!previous || previous.bottom)?el.scrollHeight:previous?.top || 0;});
  if (focus && document.getElementById(focus)) { const el=document.getElementById(focus);el.focus({preventScroll:true});if(selection!=null && el.setSelectionRange)el.setSelectionRange(selection,selection); }
  $$('#app details[data-disclosure]').forEach(el=>{if(el.dataset.disclosure in disclosures)el.open=disclosures[el.dataset.disclosure];});
}

async function ensureSession(force=false) {
  if (state.route==='home') return;
  const route=state.route;
  state.loading=true; render();
  try {
    let ids = force ? null : state.ids[route];
    if (ids) {
      try { for (const id of Array.isArray(ids)?ids:[ids]) state.sessions[id]=await api('/sessions/'+id); }
      catch { ids=null; }
    }
    if (!ids) {
      if (route==='compare') {
        const pair=await api('/comparisons','POST',state.settings);
        ids=pair.sessions.map(s=>{state.sessions[s.id]=s;return s.id;});
      } else {
        const s=await api('/sessions','POST',{...state.settings,mode:route});
        state.sessions[s.id]=s;ids=s.id;
      }
      state.ids[route]=ids; persist();
    }
    state.list=await api('/sessions');
  } catch(error) { toast(error.message); }
  finally {if(state.route===route){state.loading=false;render();}}
}

async function perform(action, body) {
  const sessions=currentSessions();
  if (labBusy() || !sessions.length) return;
  sessions.forEach(s=>{state.busy.add(s.id);s.error=null;s.status=action==='reduce'?'Preparing context transition…':'Preparing request…';});
  render();
  const results=await Promise.allSettled(sessions.map(async s=>{
    try {state.sessions[s.id]=await api(`/sessions/${s.id}/${action}`,'POST',body);state.windowIndex[s.id]=null;}
    catch(error){toast(`${lessons[s.mode].name}: ${error.message}`);state.sessions[s.id]=await api('/sessions/'+s.id);}
  }));
  results.filter(r=>r.status==='rejected').forEach(r=>toast(r.reason.message));
  try {state.list=await api('/sessions');}catch(error){toast(error.message);}
  sessions.forEach(s=>{state.busy.delete(s.id);state.sessions[s.id].busy=false;});
  render();
}

function openLesson() {
  const l=lessons[state.route];const kind=state.route==='compare'?'offload':state.route;
  $('#lesson-dialog').innerHTML=`<div class="dialog-header"><div><div class="eyebrow">LAB ${l.number} · THE MECHANISM</div><h2 id="lesson-title">${l.name}</h2></div><button class="icon-button" data-action="close-dialog" aria-label="Close explanation">${icon('close')}</button></div><div class="dialog-body"><p class="lesson-definition">${l.definition}</p>${architecture(kind,true)}<div class="mechanics-list">${l.mechanics.map(([name,copy])=>`<div><strong>${name}</strong><p>${copy}</p></div>`).join('')}</div><div class="experiment-box"><span class="tiny-label">TRY THIS</span><p>${l.experiment}</p></div></div>`;
  $('#lesson-dialog').showModal();
}

function openPolicy() {
  const notes=state.route==='notes';
  $('#lesson-dialog').innerHTML=`<div class="dialog-header"><h2 id="lesson-title">${notes?'How notes are selected':'What should the synopsis keep?'}</h2><button class="icon-button" data-action="close-dialog" aria-label="Close policy">${icon('close')}</button></div><div class="dialog-body">${notes?`<p>Only <strong>fresh original user statements and work-tool results</strong> reach the note writer. Old notes, bootstrap seeds and retrieval copies are excluded.</p><ul><li>Requirements and decisions.</li><li>Failures: exact test/component, error, expected/actual values and recorded cause.</li><li>Component behavior, including what repeated calls do.</li><li>Unfinished work, with uncertainty preserved.</li></ul><p>Each typed note must quote an original event. Incidental trace markers and repetitive check lines are intentionally excluded. The archive remains searchable.</p><p>Notes are never re-summarised. If they outgrow the ${number(currentSessions()[0]?.notes_budget)}-token notes envelope, older fixed headlines replace full entries in the carried projection. Stored entries remain intact.</p>`:`<p>This rule is sent to a separate live model call for each summary or synopsis. It also makes the lossy-summary experiment explicit.</p><label class="field-label" for="focus-input">Selection rule</label><textarea id="focus-input" rows="6">${escape(state.drafts.focus || state.config.default_focus)}</textarea><button class="button primary" data-action="save-policy">Save selection rule ${icon('check')}</button>`}</div>`;
  $('#lesson-dialog').showModal();
}

function openReduction(session,id) {
  const r=session.reductions.find(r=>r.id===id);
  const before=session.windows.find(w=>w.id===r.before_window_id);
  const after=session.windows.find(w=>w.id===r.after_window_id);
  // Show only the seed immediately after reduction, even if the window has since grown.
  const seeds=after.items.filter(i=>i.origin==='seed');
  $('#lesson-dialog').innerHTML=`<div class="dialog-header"><div><div class="eyebrow">MEASURED AT THE TRANSITION</div><h2 id="lesson-title">What actually changed?</h2></div><button class="icon-button" data-action="close-dialog" aria-label="Close comparison">${icon('close')}</button></div><div class="dialog-body"><div class="reduction-stats"><div><strong>${number(r.before_tokens)}</strong><span>tokens before</span></div><div>${icon('arrow')}</div><div><strong>${number(r.after_tokens)}</strong><span>tokens after</span></div><div><strong class="${r.saved_tokens>=0?'cyan-text':'pink-text'}">${r.saved_percent}%</strong><span>${r.saved_tokens>=0?'reduction':'reduction (negative = growth)'}</span></div></div><p>The same model, instructions and tool schemas are counted on both sides. ${r.saved_tokens<0?'This transition added overhead: the replacement is larger than the small original.':''}</p><div class="before-after"><section><h3>Before · W${before.number}</h3><div>${before.items.map(contextItem).join('')}</div></section><section><h3>Immediately after · W${after.number}</h3><div>${seeds.map(contextItem).join('')}</div></section></div>${r.reference?`<div class="pointer-key"><strong>Read the pointer</strong><p><code>offload_id</code> locates the stored snapshot. <code>source_window_id</code> identifies its source window. <code>tool_call_ids</code> preserve call/result linkage. They are distinct identifiers, not interchangeable addresses.</p></div>`:''}</div>`;
  $('#lesson-dialog').showModal();
}

function openSettings() {
  const s=state.settings; const sessions=currentSessions();
  $('#settings-dialog').innerHTML=`<div class="dialog-header"><div><div class="eyebrow">YOUR LOCAL LAB</div><h2 id="settings-title">Model & session settings</h2></div><button class="icon-button" data-action="close-dialog" aria-label="Close settings">${icon('close')}</button></div><form class="dialog-body" data-form="settings"><p>Model changes apply to <strong>new sessions</strong>. Your API key stays on the server in an environment variable.</p><label class="field-label" for="model-input">OpenAI model name</label><input id="model-input" name="model" value="${escape(s.model)}" required maxlength="100" list="models"><datalist id="models"><option value="gpt-6-astra"><option value="gpt-5.4"></datalist><p class="field-hint">The notebook uses gpt-6-astra. GPT-5.4 with low reasoning was also tested there. Access depends on your OpenAI project.</p><div class="field-grid"><label>Reasoning effort<select name="effort">${['','none','low','medium','high'].map(e=>`<option value="${e}" ${s.effort===e?'selected':''}>${e || 'Model default'}</option>`).join('')}</select></label><label>Input budget<input type="number" name="budget" value="${s.budget}" min="3000" max="100000" step="500" required></label><label>Notes budget<input type="number" name="notes_budget" value="${s.notes_budget}" min="800" max="10000" step="100" required></label><label>Diagnostic check lines<input type="number" name="diagnostic_checks" value="${s.diagnostic_checks}" min="10" max="400" required></label></div><p class="field-hint">This budget controls the lesson, not the physical model limit. In the notes lab, rotation is checked before every model call, including after tool results. Large logs make this easier to observe.</p><button class="button primary" type="submit">Save defaults ${icon('check')}</button>${sessions.length?`<div class="current-budget"><label class="field-label" for="current-budget">Change the current ${sessions.length===2?'pair’s':'session’s'} input budget</label><div><input id="current-budget" type="number" min="3000" max="100000" step="500" value="${sessions[0].budget}"><button type="button" class="button ghost" data-action="current-budget"${disabled(labBusy())}>Apply</button></div></div>`:''}<div class="cost-note">Live requests use your OpenAI account. One message can make multiple model calls when tools run. A reduction adds a summary or note-writing call. Inspect the Tool trace tab for actual usage.</div></form>`;
  $('#settings-dialog').showModal();
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action]');if(!button || button.disabled)return;
  const action=button.dataset.action;
  const session=state.sessions[button.dataset.session] || currentSessions()[0];
  try {
    if(action==='collapse'){state.collapsed=!state.collapsed;persist();render();}
    if(action==='architecture'){state.architecture=button.dataset.kind;render();}
    if(action==='inspector'){state.inspector=!state.inspector;render();}
    if(action==='inspector-tab'){state.inspectorTab=button.dataset.tab;state.inspector=true;render();}
    if(action==='settings')openSettings();
    if(action==='lesson')openLesson();
    if(action==='policy')openPolicy();
    if(action==='close-dialog')button.closest('dialog').close();
    if(action==='save-policy'){state.drafts.focus=$('#focus-input').value.trim() || state.config.default_focus;$('#lesson-dialog').close();toast('Selection rule saved for the next reduction.');}
    if(action==='new')await ensureSession(true);
    if(action==='starter' || action==='prompt'){
      const text=action==='starter'?starter:probes[button.dataset.prompt];
      state.drafts['chat-'+state.route]=text;const input=$('#chat-input');if(input){input.value=text;input.focus();}
    }
    if(action==='reduce')await perform('reduce',{focus:state.drafts.focus || state.config.default_focus,tool_only:$('#offload-scope')?.value==='tools'});
    if(action==='window-prev' || action==='window-next'){
      state.windowIndex[session.id]=(state.windowIndex[session.id]??session.windows.length-1)+(action==='window-prev'?-1:1);render();
    }
    if(action==='source-window'){
      state.windowIndex[session.id]=session.windows.findIndex(w=>w.id===button.dataset.window);state.inspectorTab='context';state.inspector=true;render();
    }
    if(action==='reduction')openReduction(session,button.dataset.id);
    if(action==='measure'){
      state.busy.add(session.id);render();try{state.sessions[session.id]=await api(`/sessions/${session.id}/measure`,'POST');}finally{state.busy.delete(session.id);render();}
    }
    if(action==='current-budget'){
      const budget=Number($('#current-budget').value);if(budget<3000 || budget>100000)throw new Error('Choose a budget between 3,000 and 100,000.');
      await Promise.all(currentSessions().map(async s=>state.sessions[s.id]=await api(`/sessions/${s.id}/settings`,'PATCH',{budget,auto_rollover:s.auto_rollover})));
      $('#settings-dialog').close();render();toast('Current input budget updated.');
    }
  } catch(error){toast(error.message);}
});

document.addEventListener('change',async event=>{
  const el=event.target;
  try {
    if(el.dataset.action==='resume' && el.value){state.ids[state.route]=state.route==='compare'?state.list.filter(s=>s.group_id===el.value).sort((a,b)=>a.mode==='summary'?-1:1).map(s=>s.id):el.value;persist();await ensureSession();}
    if(el.dataset.action==='auto-notes'){
      const s=currentSessions()[0];state.sessions[s.id]=await api(`/sessions/${s.id}/settings`,'PATCH',{budget:s.budget,auto_rollover:el.checked});render();
    }
  }catch(error){toast(error.message);}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!form.dataset.form)return;event.preventDefault();
  try {
    if(form.dataset.form==='chat'){
      const input=$('#chat-input'),prompt=input.value.trim();if(!prompt || labBusy())return;
      input.value='';state.drafts['chat-'+state.route]='';await perform('chat',{prompt});
    }
    if(form.dataset.form==='search'){
      const data=new FormData(form);state.searchResults[form.dataset.session]=await api(`/sessions/${form.dataset.session}/search?query=${encodeURIComponent(data.get('query'))}&target=${data.get('target')}`);render();
    }
    if(form.dataset.form==='settings'){
      const data=Object.fromEntries(new FormData(form));['budget','notes_budget','diagnostic_checks'].forEach(k=>data[k]=Number(data[k]));
      state.settings=data;persist();$('#settings-dialog').close();render();toast('Defaults saved. Start a new session to use them.');
    }
  }catch(error){toast(error.message);}
});
document.addEventListener('keydown',event=>{
  if(event.target.id==='chat-input' && event.key==='Enter' && !event.shiftKey && !event.isComposing){event.preventDefault();$('#chat-form').requestSubmit();}
});
window.addEventListener('hashchange',async()=>{
  state.route=location.hash.slice(1) || 'home';if(state.route!=='home' && !lessons[state.route])state.route='home';
  if(innerWidth<=650){state.collapsed=true;persist();}
  state.inspectorTab='context';render();await ensureSession();window.scrollTo(0,0);
});
for(const dialog of $$('dialog'))dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});

setInterval(async()=>{
  const ids=new Set([...state.busy,...currentSessions().filter(s=>s.busy).map(s=>s.id)]);
  if(!ids.size)return;
  let changed=false;
  await Promise.allSettled([...ids].map(async id=>{
    const update=await api('/sessions/'+id);
    if((state.busy.has(id) || state.sessions[id]?.busy) && update.updated_at >= state.sessions[id].updated_at){state.sessions[id]=update;changed=true;}
  }));
  if(changed)render();
},1600);

try {
  state.config=await api('/config');
  if(!localStorage.getItem('appbook.settings')){state.settings.model=state.config.model;state.settings.effort=state.config.effort;}
  state.list=await api('/sessions');
  if(state.route!=='home' && !lessons[state.route])state.route='home';
  render();await ensureSession();
}catch(error){$('#app').innerHTML=`<div class="boot">Could not open the appbook.<p>${escape(error.message)}</p><a href="/">Reload</a></div>`;}
