/* ======================================================================
   The reference architecture (notebook 00): the twenty decision points
   of the memory loop, placed by stage, each built point coloured by its
   swap's verdict and linked to the swap page that asks it live.
   ====================================================================== */

const STORES = [
  { key: "session", label: "Session memory", note: "thread, message history" },
  { key: "cache", label: "Semantic cache", note: "answers keyed by meaning" },
  { key: "episodic", label: "Episodic", note: "conversations, summaries" },
  { key: "semantic", label: "Semantic", note: "entities, knowledge, persona" },
  { key: "procedural", label: "Procedural", note: "toolbox, skillbox, workflows" },
  { key: "indexes", label: "Indexes", note: "vector, text, TTL, audit" },
];
const TOUCH = {
  1: ["semantic", "indexes"], 2: ["episodic", "semantic", "procedural"], 3: ["episodic", "semantic", "procedural"],
  4: ["episodic", "semantic"], 5: ["semantic"], 6: ["semantic", "episodic", "indexes"], 7: ["semantic"], 8: ["semantic", "episodic"],
  9: ["semantic", "episodic"], 10: ["episodic", "semantic"], 11: ["semantic", "episodic", "procedural"], 12: ["procedural", "episodic"],
  13: ["session", "episodic", "semantic", "procedural"], 14: ["episodic", "semantic", "procedural"], 15: ["indexes"],
  16: ["semantic", "episodic", "indexes"], 17: ["semantic"], 18: ["semantic", "episodic"], 19: ["procedural"], 20: ["procedural"], cache: ["cache"],
};
const arch = { data: null, sel: 14 };

async function viewArchitecture() {
  setStage(`
    <header class="eval-head">
      <div class="eval-kicker">Notebook 00 · the reference architecture</div>
      <h1 class="eval-title">Twenty decisions in the memory loop, <em>seven swaps measured</em></h1>
      <p class="eval-desc">Every turn crosses small decisions: where a chunk ends, which store to search, whether a cached answer fits, which tool runs. Today each is a similarity score, a threshold, a rule or an LLM prompt. A decision model asks the question directly and answers with a probability. Notebooks 01 to 07 each take one technique, show where today's approach breaks, swap in a decision model, and measure both. Pick a point, or a swap below.</p>
    </header>
    <div id="arch-swaps" class="mb"></div>
    <div id="arch-tiles"></div>
    <div class="arch mb" id="arch-board"><div class="empty">Reading the notebooks' results…</div></div>
    <div id="arch-detail" class="mb"></div>
    ${fold("The reference architecture, as figures", `<img src="/img/reference/p08_reference_architecture.png" alt="The agent memory reference architecture." style="width:100%;border-radius:8px;margin-top:6px"><img src="/img/reference/p16_every_d_is_a_decision.png" alt="Every D is a decision." style="width:100%;border-radius:8px;margin-top:8px"><img src="/img/reference/p25_architecture_with_a_decision_model.png" alt="The same architecture, with a decision model." style="width:100%;border-radius:8px;margin-top:8px"><div class="hint">The Decision on Decision Models, pages 8, 16 and 25 · docs/the-decision-on-decision-models.pdf</div>`, true)}
    ${fold("The diagram from notebook 00", `<img src="/img/00_reference_architecture.png" alt="Reference architecture: a user turn reaches the MemAgent, which talks to the chat LLM and the MemoRizz store, and crosses twenty memory decisions answered by the typical path or a decision model." style="width:100%;border-radius:8px;margin-top:6px">`)}
    ${fold("Index for recall, predicate for precision", `<p>In every swap the first step stays geometric: embeddings, vector search and similarity find the candidates, cheaply and at scale. What changes is the judgement on those candidates. A similarity score answers "how close are these?", which stands in for the question we have. The decision model asks that question directly: does a new topic start here, does this chunk answer the query, can this cached answer serve this query, which memory types does this need, how do these two memories relate, is anything here durable, which tool, if any.</p>`)}`, "#a78bfa");
  try {
    arch.data = await getJSON("/api/architecture");
    renderArch();
  } catch (e) { setHTML("#arch-board", `<div class="empty">${esc(e.message)}</div>`); }
}

function renderArch() {
  const d = arch.data;
  const count = (v) => d.swaps.filter((s) => s.verdict === v).length;
  setHTML("#arch-swaps", `<div class="swap-strip">${d.swaps.map((s) => `<a class="swap-chip ${esc(s.verdict || "none")}" href="#/${s.id}"><span class="n">${s.n}</span><span class="t">${esc(s.title)}</span>${verdictPill(s.verdict)}</a>`).join("")}</div>`);
  setHTML("#arch-tiles", `<div class="tiles five">
    ${tile("decision points", "20", "Retain 8 · Refine 4 · Recall 6 · Reuse 2")}
    ${tile("swaps built", "7", `${d.built} of the 20 points, plus the semantic cache`)}
    ${tile("better", count("better"), "on the notebook's main measure")}
    ${tile("level", count("level"), "within noise on the main measure")}
    ${tile("worse", count("worse"), "paired bootstrap, 95%")}
  </div>`);
  const pointBtn = (p) => {
    const v = p.card?.verdict, oc = v ? OUTCOME[v]?.c : null;
    const tipText = `${p.n} · ${p.name}<br>${p.question}<br>${p.status === "built" ? `swap ${p.swap}: <b>${v || "not run"}</b>` : "listed only"}`;
    return `<button class="dp ${p.status === "listed" ? "listed" : ""} ${arch.sel === p.n ? "sel" : ""}" data-n="${p.n}" data-tip="${esc(tipText)}" style="--sc:${STAGE_COLOR[p.r]};${oc ? `--oc:${oc}` : ""}"><span class="n">${p.n}</span><span>${esc(p.name)}</span><span class="o"></span></button>`;
  };
  const stages = d.stages.map((s) => {
    const pts = d.points.filter((p) => p.r === s.name);
    const extra = s.name === "Recall" ? (() => { const x = d.extra, oc = x.card?.verdict ? OUTCOME[x.card.verdict]?.c : null;
      return `<button class="dp ${arch.sel === "cache" ? "sel" : ""}" data-n="cache" data-tip="${esc(`Semantic cache · in front of recall<br>${x.question}<br>swap 3: <b>${x.card?.verdict || "not run"}</b>`)}" style="--sc:${STAGE_COLOR.Recall};${oc ? `--oc:${oc}` : ""}"><span class="n">C</span><span>Cache hit?</span><span class="o"></span></button>`; })() : "";
    return `<div class="stage" style="--sc:${STAGE_COLOR[s.name]}"><div class="stage-h"><b>${esc(s.name)}</b><small>${pts.length} points</small></div><p>${esc(s.description)}</p>${extra}${pts.map(pointBtn).join("")}</div>`;
  }).join("");
  const m = state.health?.models || {};
  const models = ORDER.map((k) => `<div class="mrow"><span class="swatch" style="--c:${COLOR[k]}"></span>${esc(LABEL[k])} <span class="dim">· ${esc(m[k]?.available === false ? "no key" : (k === "local" ? m[k]?.state || "" : m[k]?.model || ""))}</span></div>`).join("");
  setHTML("#arch-board", `
    <div class="arch-main">
      <div class="arch-row"><div class="node user">User, app<small>message in, reply out</small></div></div>
      <div class="link"></div>
      <div class="arch-row"><div class="node agent">Agent harness<small>MemAgent · MemoRizz 0.17 · runs the turn, calls tools</small></div><div class="node llm">LLM<small>${esc(state.health?.typical?.chat_model || "gpt-4o-mini")} · writes the reply</small></div></div>
      <div class="link">memory manager: write path, read path, background</div>
      <div class="stages">${stages}</div>
      <div class="outcome-legend"><span><i style="--oc:var(--ok)"></i>better</span><span><i style="--oc:var(--text-3)"></i>level</span><span><i style="--oc:var(--bad)"></i>worse</span><span style="opacity:.7">dashed: listed, not built</span></div>
      <div class="link">answered by</div>
      <div class="lanes" id="arch-lanes"></div>
      <div class="link">reading and writing</div>
      <div class="store-col" id="arch-stores">
        <div class="store-h"><h5>Memory database / filesystem</h5><small>MemoRizz FileSystemProvider · memory_store/</small></div>
        ${STORES.map((s) => `<div class="mem" data-store="${s.key}">${esc(s.label)}<small>${esc(s.note)}</small></div>`).join("")}
        <div class="models-col"><h5>Decision models</h5>${models}</div>
      </div>
    </div>`);
  $$("#arch-board .dp").forEach((b) => b.addEventListener("click", () => { arch.sel = b.dataset.n === "cache" ? "cache" : Number(b.dataset.n); renderArch(); }));
  bindTips($("#arch-board"));
  renderArchDetail();
}

function renderArchDetail() {
  const d = arch.data;
  const isCache = arch.sel === "cache";
  const p = isCache ? { n: "C", r: "Recall", name: "Semantic cache", question: d.extra.question, typical: "cosine similarity to the closest cached question, above a threshold (about 0.9)",
    d1_primitive: "Noul over the new question and the cached answer", notebook: "03", page: "cache", status: "built", card: d.extra.card, swap: 3, swap_title: "Semantic cache" }
    : d.points.find((x) => x.n === arch.sel);
  const sc = STAGE_COLOR[p.r];
  $$("#arch-stores .mem").forEach((el) => { el.classList.toggle("hot", (TOUCH[isCache ? "cache" : p.n] || []).includes(el.dataset.store)); el.style.setProperty("--sc", sc); });
  setHTML("#arch-lanes", `
    <div class="lane typ"><h5><span class="swatch" style="--c:${COLOR.typical}"></span>Today</h5><div>${esc(p.typical)}</div></div>
    <div class="lane dm"><h5><span class="swatch" style="--c:${COLOR.local}"></span>Decision model</h5><div>${esc(p.d1_primitive)}</div></div>`);
  let evidence = `<div class="note">Listed so the inventory is complete. Notebook 00 names how it is done today and the primitive that would fit; no notebook builds it.</div>`;
  if (p.status === "built") {
    const c = p.card;
    evidence = c ? `<div class="verdict mini ${esc(c.verdict)}"><div class="vword">${VERDICT[c.verdict]?.icon || ""} ${esc(VERDICT[c.verdict]?.word || "")}</div><div class="vtext"><div class="vline">Swap ${p.swap} · ${esc(p.swap_title)}: <b>${esc(c.measure)}</b> ${num(c.today, 2)} (${esc(c.today_label)}) → <b>${num(c.model, 2)}</b></div>${Object.entries(c.also || {}).map(([k, v]) => `<span class="vchip">${esc(k)} ${num(v.today, 2)} → ${num(v.model, 2)} ${verdictPill(v.verdict)}</span>`).join("")}</div></div>`
      : `<div class="note">Notebook ${esc(p.notebook)} has not been run yet.</div>`;
  }
  setHTML("#arch-detail", `<div class="detail" style="--sc:${sc}">
    <h3><span class="dp" style="--sc:${sc};width:auto;display:inline-grid;grid-template-columns:22px;margin:0;padding:0;border:0;background:none"><span class="n">${p.n}</span></span>${esc(p.name)} ${pill(p.r, "")} ${p.status === "built" ? verdictPill(p.card?.verdict) : pill("listed only", "listed")}</h3>
    <div class="qline">${esc(p.question)}</div>
    <dl class="kvs"><dt>Today</dt><dd>${esc(p.typical)}</dd><dt>Decision model</dt><dd>${esc(p.d1_primitive)}</dd><dt>Notebook</dt><dd>${esc(p.notebook)}</dd>
      ${p.page ? `<dt>Live</dt><dd><a class="btn btn-accent btn-sm" href="#/${p.page}" style="--accent:${sc}">Open swap ${p.swap}: ${esc(p.swap_title)} →</a></dd>` : ""}</dl>
    <div style="margin-top:14px">${evidence}</div></div>`);
  bindTips($("#arch-detail"));
}
