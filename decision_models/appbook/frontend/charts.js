/* ======================================================================
   Inline-SVG charts: thin marks, one axis, a shared tooltip, a legend on
   every chart. Colours follow the entity (a model keeps its colour).
   ====================================================================== */

function legendHTML(items) {
  return `<div class="legend">${items.map((it) => `<span><i class="${it.kind || ""}" style="--c:${it.color}"></i>${esc(it.label)}</span>`).join("")}</div>`;
}

// One value per gap between sentences: lines per model, gold boundaries as bands, a threshold line.
function gapChart({ series, gold = [], threshold = null, ymax = 1, height = 210, ylabel = "P(new topic)" }) {
  const n = Math.max(...series.map((s) => s.values.length), 1);
  const W = 880, H = height, L = 40, R = 12, T = 10, B = 26;
  const X = (i) => L + ((W - L - R) * i) / Math.max(n - 1, 1);
  const Y = (v) => T + (H - T - B) * (1 - Math.max(0, Math.min(v, ymax)) / ymax);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * ymax);
  const grid = ticks.map((t) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${L - 6}" y="${Y(t) + 3}" font-size="9.5" text-anchor="end">${num(t, ymax < 2 ? 2 : 1)}</text>`).join("");
  const xt = [0, Math.round(n / 4), Math.round(n / 2), Math.round((3 * n) / 4), n - 1].map((i) => `<text x="${X(i)}" y="${H - 8}" font-size="9.5" text-anchor="middle">${i}</text>`).join("");
  const bands = gold.map((g) => `<rect x="${X(g) - 3}" y="${T}" width="6" height="${H - T - B}" fill="${COLOR.gold}" opacity=".22"/>`).join("");
  const lines = series.map((s) => `<polyline fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" points="${s.values.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`).join("");
  const th = threshold == null ? "" : `<line x1="${L}" x2="${W - R}" y1="${Y(threshold)}" y2="${Y(threshold)}" stroke="var(--text)" stroke-dasharray="5 4" stroke-width="1"/>`;
  const hit = Array.from({ length: n }, (_, i) => {
    const vals = series.map((s) => `<span style="color:${s.color}">●</span> ${esc(s.label)} <b>${num(s.values[i], 2)}</b>`).join("<br>");
    return `<rect x="${X(i) - (W - L - R) / n / 2}" y="${T}" width="${(W - L - R) / n}" height="${H - T - B}" fill="transparent" data-tip="${esc(`gap ${i}${gold.includes(i) ? " · gold boundary" : ""}<br>${vals}`)}"/>`;
  }).join("");
  const legend = [...series.map((s) => ({ label: s.label, color: s.color })), { label: "gold topic boundary", color: COLOR.gold, kind: "dot" }];
  if (threshold != null) legend.push({ label: `threshold ${num(threshold, 2)}`, color: "var(--text)", kind: "dash" });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ylabel)} at every gap"><text x="${L}" y="9" font-size="9.5">${esc(ylabel)}</text>${grid}${bands}${lines}${th}${xt}${hit}</svg>${legendHTML(legend)}`;
}

// Horizontal bars, grouped: a heading per group, then one labelled bar per method.
function barChart({ groups, max = 1, fmt = (v) => num(v, 2), width = 620 }) {
  const bh = 13, gap = 5, L = 200, R = 56;
  let y = 4;
  const parts = groups.map((g) => {
    const headY = y + 11;
    y += g.label ? 20 : 0;
    const bars = g.bars.map((b) => {
      const w = Math.max(1, ((width - L - R) * Math.max(0, b.value ?? 0)) / max);
      const name = b.label.length > 30 ? b.label.slice(0, 29) + "…" : b.label;
      const out = `<text x="${L - 8}" y="${y + bh - 3}" font-size="10" text-anchor="end">${esc(name)}</text><rect x="${L}" y="${y}" width="${w}" height="${bh}" rx="3" fill="${b.color}" data-tip="${esc(`${g.label ? g.label + " · " : ""}${b.label}<br><b>${fmt(b.value)}</b>${b.note ? `<br>${b.note}` : ""}`)}"/><text x="${L + w + 6}" y="${y + bh - 3}" font-size="10">${esc(fmt(b.value))}</text>`;
      y += bh + gap;
      return out;
    }).join("");
    y += 10;
    return (g.label ? `<text x="0" y="${headY}" font-size="10.5" font-weight="600" style="fill:var(--text)">${esc(g.label)}</text>` : "") + bars;
  }).join("");
  return `<svg viewBox="0 0 ${width} ${y}" role="img">${parts}</svg>`;
}

// Milliseconds on a log scale: one row per item, a dot per method.
function logDots({ rows, methods, width = 640 }) {
  const all = rows.flatMap((r) => methods.map((m) => r[m.key])).filter((v) => v > 0);
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...all, 1)))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...all, 10))));
  const L = 150, R = 20, rowH = 28, H = rows.length * rowH + 30;
  const X = (v) => L + ((width - L - R) * (Math.log10(v) - Math.log10(lo))) / (Math.log10(hi) - Math.log10(lo));
  const ticks = [];
  for (let t = lo; t <= hi; t *= 10) ticks.push(`<line class="grid" x1="${X(t)}" x2="${X(t)}" y1="4" y2="${H - 22}"/><text x="${X(t)}" y="${H - 8}" font-size="9.5" text-anchor="middle">${t >= 1000 ? t / 1000 + " s" : t + " ms"}</text>`);
  const body = rows.map((r, i) => {
    const y = 16 + i * rowH;
    return `<text x="${L - 8}" y="${y + 4}" font-size="10.5" text-anchor="end">${esc(r.label)}</text>` + methods.map((m) => r[m.key] > 0
      ? `<circle cx="${X(r[m.key])}" cy="${y}" r="5.5" fill="${m.color}" stroke="var(--panel)" stroke-width="2" data-tip="${esc(`${r.label} · ${m.label}<br><b>${ms(r[m.key])}</b>`)}"/>` : "").join("");
  }).join("");
  return `<svg viewBox="0 0 ${width} ${H}" role="img">${ticks.join("")}${body}</svg>${legendHTML(methods.map((m) => ({ label: m.label, color: m.color, kind: "dot" })))}`;
}

// Every call in order: one dot per call, its latency on a log scale, coloured by model.
function callStrip({ calls, width = 880 }) {
  if (!calls.length) return '<div class="empty">No timed calls yet.</div>';
  const vals = calls.map((c) => c.ms).filter((v) => v > 0);
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...vals)))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...vals))));
  const L = 48, R = 12, T = 8, B = 24, H = 190;
  const X = (i) => L + ((width - L - R) * i) / Math.max(calls.length - 1, 1);
  const Y = (v) => T + (H - T - B) * (1 - (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo)));
  const ticks = [];
  for (let t = lo; t <= hi; t *= 10) ticks.push(`<line class="grid" x1="${L}" x2="${width - R}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${L - 6}" y="${Y(t) + 3}" font-size="9.5" text-anchor="end">${t >= 1000 ? t / 1000 + "s" : t + "ms"}</text>`);
  const dots = calls.map((c, i) => `<circle cx="${X(i)}" cy="${Y(Math.max(c.ms, lo))}" r="${c.kind === "batch" ? 6 : 4.5}" fill="${c.color}" ${c.kind === "batch" ? 'fill-opacity=".35" stroke="' + c.color + '"' : 'stroke="var(--panel)"'} stroke-width="1.5" data-tip="${esc(`#${c.n} ${c.page}<br>${c.model}${c.kind === "batch" ? ` · ${c.count} requests` : ""}<br><b>${ms(c.ms)}</b> · ${int(c.input_tokens)} tokens · ${usd(c.usd, 7)}`)}"/>`).join("");
  return `<svg viewBox="0 0 ${width} ${H}" role="img">${ticks.join("")}${dots}<text x="${L}" y="${H - 6}" font-size="9.5">first call</text><text x="${width - R}" y="${H - 6}" font-size="9.5" text-anchor="end">latest</text></svg>`;
}

// Rates against one x (a threshold): lines, fixed reference values as dashed lines, an optional marker.
function lineChart({ x, series, markers = [], vline = null, xlabel = "", ylabel = "", width = 760, height = 240 }) {
  const L = 44, R = 14, T = 12, B = 34, xmin = Math.min(...x), xmax = Math.max(...x);
  const X = (v) => L + ((width - L - R) * (v - xmin)) / (xmax - xmin || 1);
  const Y = (v) => T + (height - T - B) * (1 - Math.max(0, Math.min(1, v)));
  const grid = [0, 0.25, 0.5, 0.75, 1].map((t) => `<line class="grid" x1="${L}" x2="${width - R}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${L - 6}" y="${Y(t) + 3}" font-size="9.5" text-anchor="end">${num(t, 2)}</text>`).join("");
  const xt = x.filter((_, i) => i % 4 === 0).map((v) => `<text x="${X(v)}" y="${height - 18}" font-size="9.5" text-anchor="middle">${num(v, 2)}</text>`).join("");
  const lines = series.map((s) => `<polyline fill="none" stroke="${s.color}" stroke-width="2" points="${s.values.map((v, i) => `${X(x[i]).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>` +
    s.values.map((v, i) => `<circle cx="${X(x[i])}" cy="${Y(v)}" r="3.5" fill="${s.color}" stroke="var(--panel)" stroke-width="1.5" data-tip="${esc(`${s.label}<br>threshold ${num(x[i], 3)}: <b>${pct(v, 0)}</b>`)}"/>`).join("")).join("");
  const marks = markers.map((m) => `<line x1="${L}" x2="${width - R}" y1="${Y(m.value)}" y2="${Y(m.value)}" stroke="${m.color}" stroke-width="2" stroke-dasharray="6 4" data-tip="${esc(`${m.label}: <b>${pct(m.value, 0)}</b>`)}"/>`).join("");
  const vl = vline ? `<line x1="${X(vline.x)}" x2="${X(vline.x)}" y1="${T}" y2="${height - B}" stroke="var(--text)" stroke-dasharray="2 3"/><text x="${X(vline.x) + 4}" y="${T + 10}" font-size="9.5">${esc(vline.label)}</text>` : "";
  const legend = [...series.map((s) => ({ label: s.label, color: s.color })), ...markers.map((m) => ({ label: m.label, color: m.color, kind: "dash" }))];
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(ylabel)} by ${esc(xlabel)}">${grid}${vl}${lines}${marks}${xt}<text x="${(width + L) / 2}" y="${height - 3}" font-size="10" text-anchor="middle">${esc(xlabel)}</text></svg>${legendHTML(legend)}`;
}

// One row of dots per group on one shared axis.
function dotStrip({ groups, line = null, lineLabel = "", color, xlabel = "", width = 760 }) {
  const names = Object.keys(groups), rowH = 30, L = 110, R = 16, T = 8, H = names.length * rowH + 40;
  const all = names.flatMap((n) => groups[n]), lo = Math.floor(Math.min(...all, line ?? 1) * 10) / 10, hi = 1;
  const X = (v) => L + ((width - L - R) * (v - lo)) / (hi - lo);
  const ticks = []; for (let t = lo; t <= hi + 1e-9; t += 0.1) ticks.push(`<line class="grid" x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H - 30}"/><text x="${X(t)}" y="${H - 16}" font-size="9.5" text-anchor="middle">${num(t, 1)}</text>`);
  const rows = names.map((n, i) => { const y = T + 14 + i * rowH; return `<text x="${L - 8}" y="${y + 4}" font-size="10.5" text-anchor="end" style="fill:var(--text)">${esc(n)}</text>` +
    groups[n].map((v, j) => `<circle cx="${X(v)}" cy="${y + ((j % 3) - 1) * 5}" r="5" fill="${color}" stroke="var(--panel)" stroke-width="1.5" data-tip="${esc(`${n}: <b>${num(v, 3)}</b>`)}"/>`).join(""); }).join("");
  const ln = line != null ? `<line x1="${X(line)}" x2="${X(line)}" y1="${T}" y2="${H - 30}" stroke="var(--text)" stroke-dasharray="5 4"/><text x="${X(line) - 4}" y="${T + 9}" font-size="9.5" text-anchor="end">${esc(lineLabel)}</text>` : "";
  return `<svg viewBox="0 0 ${width} ${H}" role="img" aria-label="${esc(xlabel)} by group">${ticks.join("")}${ln}${rows}<text x="${(width + L) / 2}" y="${H - 2}" font-size="10" text-anchor="middle">${esc(xlabel)}</text></svg>`;
}

// The text as bars: the real topics on top, then one bar per chunker with a gap at each cut.
function chunkMap({ length, topics, rows, width = 860 }) {
  const L = 150, R = 12, T = 8, bh = 26, gap = 10, H = T + (rows.length + 1) * (bh + gap) + 24;
  const X = (v) => L + ((width - L - R) * v) / length;
  const edges = [...topics.map((t) => t[0]), length];
  const top = topics.map(([s, label], i) => `<rect x="${X(s)}" y="${T}" width="${Math.max(1, X(edges[i + 1]) - X(s) - 2)}" height="${bh}" rx="3" fill="${i % 2 ? "var(--line-2)" : "var(--line)"}"/><text x="${(X(s) + X(edges[i + 1])) / 2}" y="${T + bh / 2 + 3}" font-size="9" text-anchor="middle" style="fill:var(--text)">${esc(label.split(" ").pop())}</text>`).join("");
  const bars = rows.map((r, ri) => {
    const y = T + (ri + 1) * (bh + gap), cuts = [0, ...r.cuts.slice().sort((a, b) => a - b), length];
    return `<text x="${L - 8}" y="${y + bh / 2 + 4}" font-size="10.5" text-anchor="end" style="fill:var(--text)">${esc(r.name)}</text>` +
      cuts.slice(0, -1).map((a, i) => `<rect x="${X(a)}" y="${y}" width="${Math.max(1, X(cuts[i + 1]) - X(a) - 2)}" height="${bh}" rx="3" fill="${r.color}" opacity="${i % 2 ? 0.55 : 0.9}"/>`).join("");
  }).join("");
  const lines = topics.slice(1).map(([s, label]) => `<line x1="${X(s) - 1}" x2="${X(s) - 1}" y1="${T - 2}" y2="${H - 22}" stroke="${COLOR.gold}" stroke-width="1.5" stroke-dasharray="4 3" data-tip="${esc(`real topic change: ${label}`)}"/>`).join("");
  return `<svg viewBox="0 0 ${width} ${H}" role="img" aria-label="Where each chunker cut the text">${top}<text x="${L - 8}" y="${T + bh / 2 + 4}" font-size="10.5" text-anchor="end" style="fill:var(--text)">real topics</text>${bars}${lines}</svg>${legendHTML([{ label: "real topic change", color: COLOR.gold, kind: "dash" }, ...rows.map((r) => ({ label: r.name, color: r.color }))])}`;
}
