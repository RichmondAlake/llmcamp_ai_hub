/* ======================================================================
   The seven swap pages, one per notebook (01 to 07), all in one shape:
   the verdict first, then today against the decision model, the
   notebook's "where it breaks" examples asked live, the notebook's
   scorecard, a live run over its labelled set, and the takeaways.
   ====================================================================== */

const swaps = { list: null, detail: {}, runs: {}, last: {} };
const VERDICT = { better: { cls: "better", word: "Better", icon: "▲" }, level: { cls: "level", word: "Level", icon: "■" }, worse: { cls: "worse", word: "Worse", icon: "▼" } };

function head(kicker, title, desc) {
  return `<header class="eval-head"><div class="eval-kicker">${kicker}</div><h1 class="eval-title">${title}</h1><p class="eval-desc">${desc}</p></header>`;
}
function cardHead(k, rec, extra = "") {
  return `<h3><span><span class="swatch" style="--c:${COLOR[k] || COLOR.typical}"></span>${esc(rec.label || LABEL[k])}</span><small>${esc(rec.model || "")}${extra}</small></h3>`;
}
function errCard(k, rec) { return `<div class="acard" style="--c:${COLOR[k] || COLOR.typical}">${cardHead(k, rec)}<div class="err">${esc(rec.error)}</div></div>`; }
function verdictPill(v) { const s = VERDICT[v]; return s ? `<span class="pill vp ${s.cls}">${s.icon} ${esc(s.word)}</span>` : pill("not run", "listed"); }
async function swapList() { swaps.list = swaps.list || (await getJSON("/api/swaps")).swaps; return swaps.list; }

// The scorecard as one obvious block: the verdict sentence, then the numbers.
function verdictBanner(meta) {
  const c = meta.scorecard;
  if (!c) return `<div class="verdict none"><div class="vword">Not measured yet</div><div class="vtext">Run <span class="mono">notebooks/${esc(meta.notebook)}.ipynb</span> to record its scorecard.</div></div>`;
  const s = VERDICT[c.verdict] || VERDICT.level;
  const also = Object.entries(c.also || {}).map(([k, v]) => `<span>${esc(k)}: <b>${num(v.today, 2)} → ${num(v.model, 2)}</b> ${verdictPill(v.verdict)}</span>`).join("");
  return `<div class="verdict ${s.cls}">
    <div class="vword">${s.icon} ${esc(s.word)}</div>
    <div class="vtext"><div class="vline">With a decision model, <b>${esc(c.measure)}</b> went from <b>${num(c.today, 2)}</b> (${esc(c.today_label)}) to <b>${num(c.model, 2)}</b>.</div>
      ${also ? `<div class="valso">${also}</div>` : ""}
      <div class="vsrc">Notebook ${esc(meta.notebook.slice(0, 2))} · paired bootstrap over ${int(c.n)} labelled items · ${esc(c.source)}</div></div></div>`;
}
function scorecardTable(meta) {
  const c = meta.scorecard;
  if (!c) return `<div class="empty">No scorecard yet: run notebook ${esc(meta.notebook.slice(0, 2))}.</div>`;
  const rows = [{ name: c.measure, today: num(c.today, 2), model: num(c.model, 2), verdict: c.verdict, main: true },
    ...Object.entries(c.also || {}).map(([k, v]) => ({ name: k, today: num(v.today, 2), model: num(v.model, 2), verdict: v.verdict })),
    ...Object.entries(c.extra || {}).map(([k, [a, b]]) => ({ name: k, today: a, model: b, verdict: null }))];
  return table([{ label: "Measure", html: true, get: (r) => r.main ? `<b>${esc(r.name)}</b>` : esc(r.name) },
    { label: `Today · ${c.today_label}`, num: true, key: "today" }, { label: `Decision model · ${c.model_label}`, num: true, key: "model" },
    { label: "Verdict", html: true, get: (r) => (r.verdict ? verdictPill(r.verdict) : `<span class="dim">—</span>`) }], rows);
}

function methodCard(m) {
  const color = m.color || COLOR.typical;
  const today = m.key.startsWith("typical");
  const title = `<h3><span><span class="swatch" style="--c:${color}"></span>${esc(m.label)}</span><small>${today ? "today" : esc(m.model || "")}</small></h3>`;
  if (m.error) return `<div class="acard" style="--c:${color}">${title}<div class="err">${esc(m.error)}</div></div>`;
  const mark = m.right === true ? `<span class="pill right">✓ right</span>` : m.right === false ? `<span class="pill wrong">✗ wrong</span>` : "";
  const lines = (m.lines || []).map((l) => `<div class="mline ${l.ok === true ? "ok" : l.ok === false ? "no" : ""}"><i>${l.ok === true ? "✓" : l.ok === false ? "✗" : "·"}</i><span>${esc(l.text)}</span></div>`).join("");
  const metaLine = `<div class="meta"><span><b>${ms(m.ms)}</b></span>${m.input_tokens != null ? `<span><b>${int(m.input_tokens)}</b> input tokens</span>` : ""}${m.usd != null ? `<span><b>${usd(m.usd, 7)}</b>${m.key === "local" ? " at Liquid's rate" : ""}</span>` : ""}</div>`;
  return `<div class="acard ${m.right === true ? "is-right" : m.right === false ? "is-wrong" : ""}" style="--c:${color}">${title}<div class="answer-row"><span class="big">${esc(m.answer)}</span>${mark}</div>${lines}${metaLine}</div>`;
}

function noteFold(n) {
  const paras = (n.text || []).map((t) => `<p style="margin:6px 0">${esc(t)}</p>`).join("");
  const rows = n.rows ? table(n.columns.map((c, i) => ({ label: c, wrap: true, get: (r) => r[i] })), n.rows) : "";
  return fold(n.title, `${paras}${rows}${n.after ? `<p style="margin:8px 0 0">${esc(n.after)}</p>` : ""}`);
}
function inputBox(meta) {
  if (meta.input === "pair") return `<div class="pair"><label class="field">Stored memory<input class="input" id="sw-stored" maxlength="1000"/></label><label class="field">New memory<input class="input" id="sw-new" maxlength="1000"/></label></div>`;
  if (meta.input === "page") return `<label class="field">Text<textarea class="input" id="sw-text" style="min-height:170px"></textarea></label>`;
  return `<label class="field">${esc({ query: "Query", turn: "Turn" }[meta.input] || "Input")}<input class="input" id="sw-text" maxlength="1000"/></label>`;
}
function setInput(meta, value) {
  if (meta.input === "pair") { $("#sw-stored").value = value.stored; $("#sw-new").value = value.new; }
  else $("#sw-text").value = value;
}
function readInput(meta) {
  if (meta.input === "pair") return { stored: $("#sw-stored").value, new: $("#sw-new").value };
  return { text: $("#sw-text").value };
}

async function viewSwap(id) {
  setStage(`<div id="sw-body"><div class="empty">Loading…</div></div>`, "#2dd4bf");
  let meta;
  try { meta = swaps.detail[id] = await getJSON(`/api/swaps/${id}`); } catch (e) { setHTML("#sw-body", `<div class="empty">${esc(e.message)}</div>`); return; }
  const nb = meta.notebook.slice(0, 2);
  const examples = meta.examples.map((ex, i) => `<button class="btn btn-sm ex" data-i="${i}" title="${esc(typeof ex.input === "string" ? ex.input : ex.label)}">${esc(ex.label.length > 70 ? ex.label.slice(0, 68) + "…" : ex.label)}</button>`).join("");
  const opts = availableModels().map((k) => `<option value="${k}">${esc(LABEL[k])}</option>`).join("");
  setHTML("#sw-body", `
    ${head(`Swap ${meta.n} of 7 · ${esc(meta.stage)} · notebook ${nb}`, `${esc(meta.title)}: <em>${esc(meta.subtitle)}</em>`, esc(meta.when))}
    ${verdictBanner(meta)}
    <div class="swap-grid mb">
      <div class="swap-col today"><div class="swap-k">Today</div><p>${esc(meta.today)}</p></div>
      <div class="swap-col dm"><div class="swap-k">With a decision model</div><p>${esc(meta.model)}</p></div>
      <div class="swap-col judge"><div class="swap-k">How the notebook judged it</div><p>${esc(meta.judge)}</p></div>
    </div>
    ${fold("The technique and the swap, as figures", `${(meta.figures || []).map((f) => `<img src="${esc(f.src)}" alt="Page ${f.page} of The Decision on Decision Models." style="width:100%;border-radius:8px;margin-top:8px"><div class="hint">The Decision on Decision Models, page ${f.page} · docs/the-decision-on-decision-models.pdf</div>`).join("")}
      <div class="q" style="margin-top:14px">The flow, as notebook ${nb} builds it</div><img src="/img/${esc(meta.notebook)}.png" alt="Today and with a decision model, as two flows." style="width:100%;border-radius:8px;margin-top:6px">`, true)}
    ${meta.question ? fold("The question the decision model is asked, word for word", json(meta.question)) : ""}
    ${(meta.notes || []).map(noteFold).join("")}
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Where it breaks · try it live</span><span class="hint">today (${esc(meta.today_short || "")}) and every chosen decision model, on the same input</span></div><div class="panel-body">
      ${chooser("sw-models")}
      <div class="examples">${examples}</div>
      ${inputBox(meta)}
      <div class="row" style="margin-top:10px"><button class="btn btn-accent" id="sw-run">Run ${esc(meta.today_short || "today")} vs the decision models</button><span class="runline" id="sw-line"></span></div>
      <div id="sw-out"></div></div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Which is better? · the notebook's scorecard</span><span class="hint">saved by notebook ${nb}, not rerun here</span></div><div class="panel-body">
      ${scorecardTable(meta)}<div id="sw-chart"></div></div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Run the labelled set live</span><span class="hint">the notebook's labels, one decision model</span></div><div class="panel-body">
      <div class="row"><select id="sw-set-model">${opts}</select><button class="btn" id="sw-set-run">Run the whole set</button><span class="runline" id="sw-set-line"></span></div>
      <div class="progress" id="sw-set-bar" hidden><i></i></div><div id="sw-set-out"></div></div></div>
    <div class="takeaways"><h4>📌 Takeaways</h4><ul>${meta.takeaways.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div>`);
  bindChooser("sw-models");
  $$("#sw-body .ex").forEach((b) => b.addEventListener("click", () => { setInput(meta, meta.examples[Number(b.dataset.i)].input); runTry(meta); }));
  setInput(meta, meta.examples[0].input);
  $("#sw-run").addEventListener("click", () => runTry(meta));
  $("#sw-set-run").addEventListener("click", () => runSet(meta));
  if (swaps.last[id]) renderTry(meta, swaps.last[id]);
  if (swaps.runs[id]) renderSet(meta);
  drawSwapChart(meta);
}

async function runTry(meta) {
  const body = { ...readInput(meta), backends: chosen() };
  $("#sw-run").disabled = true;
  const local = chosen().includes("local") && state.health?.models?.local?.state !== "loaded";
  setHTML("#sw-line", `Asking${local ? " (loading d1 first, about 20 s)" : ""}…`);
  try {
    const d = await postJSON(`/api/swaps/${meta.id}/try`, body);
    swaps.last[meta.id] = d;
    renderTry(meta, d);
    setHTML("#sw-line", "");
    refreshCtx(); refreshHealth();
  } catch (e) { setHTML("#sw-line", `<span style="color:var(--bad)">${esc(e.message)}</span>`); }
  finally { $("#sw-run").disabled = false; }
}

function renderTry(meta, d) {
  const cards = d.methods.map(methodCard).join("");
  let extra = "";
  if (d.gaps) {
    const models = Object.keys(d.gaps[0]?.p || {});
    extra = `<div class="q" style="margin-top:14px">Every gap: the similarity today's chunker cut on, and each model's P(new topic)</div>` + table([
      { label: "Gap", num: true, key: "i" }, { label: "End of the sentence before", wrap: true, key: "before" }, { label: "Start of the sentence after", wrap: true, key: "after" },
      { label: "Similarity", num: true, get: (g) => num(g.similarity, 3) },
      ...models.map((k) => ({ label: `P · ${LABEL[k]}`, num: true, html: true, get: (g) => (g.p[k] == null ? "—" : `<span class="${g.p[k] >= 0.5 ? "cut" : ""}">${num(g.p[k], 2)}</span>`) })),
      { label: "Real section change", html: true, get: (g) => (g.real ? pill("yes", "right") : "") }], d.gaps)
      + howto(["Today's chunker cuts at the lowest similarities in the text, whatever they are.", "A decision model cuts where P is at least 0.5 (in bold)."]);
  }
  setHTML("#sw-out", `${d.truth ? `<div class="truth">${esc(d.truth)}</div>` : ""}<div class="answers">${cards}</div>${extra}`);
}

async function runSet(meta) {
  const backend = $("#sw-set-model").value, bar = $("#sw-set-bar");
  bar.hidden = false; $("i", bar).style.width = "0%"; $("#sw-set-run").disabled = true;
  setHTML("#sw-set-line", `${esc(LABEL[backend])}: starting${backend === "local" && state.health?.models?.local?.state !== "loaded" ? " (loading d1 first)" : ""}…`);
  try {
    const result = await postStream(`/api/swaps/${meta.id}/run`, { backend }, (p) => {
      if (p.stage) { setHTML("#sw-set-line", `${esc(LABEL[backend])}: ${esc(p.stage)}…`); return; }
      $("i", bar).style.width = `${(100 * p.done) / p.total}%`;
      setHTML("#sw-set-line", `${esc(LABEL[backend])}: ${p.done} of ${p.total} requests`);
    });
    swaps.runs[meta.id] = swaps.runs[meta.id] || {};
    swaps.runs[meta.id][backend] = result;
    setHTML("#sw-set-line", "");
    renderSet(meta);
    refreshCtx(); refreshHealth();
  } catch (e) { setHTML("#sw-set-line", `<span style="color:var(--bad)">${esc(e.message)}</span>`); }
  finally { $("#sw-set-run").disabled = false; bar.hidden = true; }
}

function renderSet(meta) {
  const runs = swaps.runs[meta.id] || {};
  const c = meta.scorecard;
  const rows = ORDER.filter((k) => runs[k]).map((k) => ({ k, ...runs[k] }));
  let out = table([{ label: "Model", html: true, get: (r) => `<span class="swatch" style="--c:${COLOR[r.k]}"></span>${esc(r.label)}` },
    { label: rows[0]?.measure || "score", num: true, get: (r) => num(r.score, 3) }, { label: "Detail", wrap: true, key: "detail" },
    { label: "Requests", num: true, get: (r) => int(r.requests) }, { label: "Seconds", num: true, get: (r) => num(r.seconds, 1) },
    { label: "$", num: true, get: (r) => usd(r.usd, 5) }], rows);
  if (c && rows.length && rows[0].measure === c.measure) out += `<div class="note">The notebook's scorecard on the same measure: today ${num(c.today, 3)}, d1 ${num(c.model, 3)}. Hosted models can differ from run to run.</div>`;
  else if (c) out += `<div class="note">This run scores the decision itself (${esc(rows[0]?.measure || "")}); the notebook's main measure is ${esc(c.measure)}, which needs the full path (retrieval or an LLM call) behind the decision.</div>`;
  const withMap = rows.find((r) => r.map);
  if (withMap) {
    const m = withMap.map;
    const mapRows = [];
    if (m.today_cuts) mapRows.push({ name: "semantic p95 (today)", color: COLOR.typical, cuts: m.today_cuts });
    rows.filter((r) => r.map).forEach((r) => mapRows.push({ name: r.label, color: COLOR[r.k], cuts: r.map.cuts }));
    out += `<div class="chart-box" style="margin-top:12px"><h4><span>Where each chunker cut the transcript</span><span>dashed lines: real topic changes</span></h4>${chunkMap({ length: m.length, topics: m.topics, rows: mapRows })}</div>`;
  }
  setHTML("#sw-set-out", out);
  bindTips($("#sw-set-out"));
}

async function drawSwapChart(meta) {
  try {
    if (meta.id === "cache") {
      const d = await getJSON("/api/swaps/cache/trap");
      const c = meta.scorecard;
      const markers = [];
      if (c) {
        if (c.also?.["paraphrases served"]) markers.push({ label: "decision model: paraphrases served", color: COLOR.local, value: c.also["paraphrases served"].model });
        const wrong = Number((c.extra?.["wrong answers served"] || [])[1]);
        if (!isNaN(wrong)) markers.push({ label: "decision model: wrong answers served", color: COLOR.gold, value: wrong / d.unservable });
      }
      setHTML("#sw-chart", `<div class="chart-box" style="margin-top:12px"><h4><span>The threshold trap: every cosine threshold trades one failure for the other</span><span>notebook 03, recomputed from embeddings</span></h4>${lineChart({
        x: d.thresholds, series: [{ label: "cosine: paraphrases served (higher is better)", color: COLOR.typical, values: d.paraphrases_served },
          { label: "cosine: wrong answers served (lower is better)", color: COLOR.openai, values: d.wrong_answers_served }],
        markers, vline: { x: 0.9, label: "typical 0.9" }, xlabel: "cosine threshold", ylabel: "share of queries" })}</div>`);
    } else if (meta.id === "consolidation") {
      const d = await getJSON("/api/swaps/consolidation/dots");
      setHTML("#sw-chart", `<div class="chart-box" style="margin-top:12px"><h4><span>Cosine similarity of each labelled pair, by its true relation</span><span>notebook 05, recomputed</span></h4>${dotStrip({ groups: d.groups, line: d.line, lineLabel: "cut-off 0.95", color: COLOR.typical, xlabel: "cosine similarity" })}<div class="note">Same, refines and contradicts overlap: all three are about the same thing. No line separates them.</div></div>`);
    } else return;
    bindTips($("#sw-chart"));
  } catch (e) { setHTML("#sw-chart", `<div class="note">${esc(e.message)}</div>`); }
}
