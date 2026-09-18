// Educational copy and local SVGs. No CDN, Mermaid runtime or screenshot required.
export const lessons = {
  summary: {
    number: '01', name: 'Summarisation', short: 'Keep the gist.', color: 'gold', icon: 'compress',
    eyebrow: 'SELECT → COMPRESS → CONTINUE',
    title: 'A smaller context. A selective memory.',
    intro: 'Turn a conversation into a compact summary, then find out which details survived.',
    action: 'Summarise',
    steps: ['Build a conversation', 'Summarise the window', 'Ask what survived'],
    definition: '<strong>Summarisation</strong> replaces a context window with a shorter, model-selected account. The next request receives that account. Information left out is unavailable to this lab’s assistant.',
    mechanics: [
      ['Retain', 'Original messages and tool results are journaled before entering context.'],
      ['Reduce', 'A separate OpenAI call writes a summary of up to 140 words using the visible selection rule.'],
      ['Reuse', 'A new window starts with the summary. Earlier windows remain inspectable by you.'],
      ['Limit', 'This assistant has no archive retrieval tool. Repeated summaries may compound omissions.'],
    ],
    experiment: 'Run the release diagnostic, reduce, then ask for the exact trace marker. The default selection rule deliberately omits markers so the loss is observable.',
  },
  offload: {
    number: '02', name: 'Context offloading', short: 'Keep a way back.', color: 'cyan', icon: 'archive',
    eyebrow: 'SAVE → POINT → RETRIEVE',
    title: 'Move the detail. Keep the address.',
    intro: 'Replace a full window or a tool exchange with a pointer, then recover the original evidence.',
    action: 'Offload context',
    steps: ['Build a conversation', 'Offload the detail', 'Retrieve on demand'],
    definition: '<strong>Context offloading</strong> saves original content outside the active request and leaves a compact pointer plus a synopsis. <strong>Just-in-time retrieval</strong> brings back a bounded excerpt when a question needs it.',
    mechanics: [
      ['Save', 'An immutable snapshot stores the selected API items with a SHA-256 integrity check.'],
      ['Point', 'offload_id locates the snapshot. source_window_id records its origin. tool_call_ids link calls to outputs.'],
      ['Recall', 'The assistant chooses just_in_time_retrieval and receives a paginated excerpt from its own session.'],
      ['Limit', 'Retrieval consumes tokens and an extra model step. A pointer can cost more tokens than a very small source.'],
    ],
    experiment: 'Use the same diagnostic and summary rule as lab 01. After offloading, ask for the marker and open the tool trace to see the retrieval happen.',
  },
  compare: {
    number: '03', name: 'Compare the methods', short: 'Test the trade-off.', color: 'pink', icon: 'compare',
    eyebrow: 'SAME QUESTION → TWO MEMORY POLICIES',
    title: 'One conversation. Two ways to remember.',
    intro: 'Send the same messages to two independent agents. Reduce both, then test a detail the synopsis omitted.',
    action: 'Reduce both',
    steps: ['Send to both agents', 'Reduce both windows', 'Compare recovery'],
    definition: 'The left agent carries a <strong>summary</strong>. The right agent carries a <strong>synopsis and an offload pointer</strong>. Both use the same model, selection rule and diagnostic marker. Their responses may differ because these are independent live runs.',
    mechanics: [
      ['Control', 'One composer sends identical user messages to both branches. Both use the same diagnostic input.'],
      ['Observe', 'Compare measured request tokens, visible seed content, answers and tool calls.'],
      ['Probe', 'Ask for the retry limit, then for the incidental trace marker. Inspect actual evidence instead of scoring fluent prose.'],
      ['Limit', 'This is an interactive experiment, not a controlled model benchmark or a guarantee that any summary will omit a particular fact.'],
    ],
    experiment: 'Run diagnostics in both branches. Reduce both with the default rule. Ask: “What was the exact trace_marker in the original diagnostic result?”',
  },
  notes: {
    number: '04', name: 'Durable notes', short: 'Accumulate knowledge.', color: 'pink', icon: 'notes',
    eyebrow: 'EXTRACT → APPEND → CARRY + SEARCH',
    title: 'Remember the lesson. Preserve the evidence.',
    intro: 'Carry useful knowledge across windows without repeatedly rewriting old notes. Search the originals when a detail is missing.',
    action: 'Write notes & rotate',
    steps: ['Observe original evidence', 'Append typed notes', 'Carry or search'],
    definition: '<strong>Durable notes</strong> are selected facts stored independently of the active context. This implementation appends discrete, evidenced entries. A bounded projection carries notes into a new window; the remaining notes and original windows stay searchable.',
    mechanics: [
      ['Extract', 'The note writer sees fresh original user statements and work-tool outputs. Seed notes, retrieved copies and assistant paraphrases are excluded.'],
      ['Append', 'Requirements, decisions, failed fixes, component behavior and next steps become typed notes. Exact evidence quotes are checked against the source event.'],
      ['Push + pull', 'Carry all entries while they fit; otherwise carry recent full entries and older fixed headlines. Search notes or closed original windows for omissions.'],
      ['Arbitrate', 'Newest user statements take precedence. Older notes remain unchanged; this lab does not automatically merge or invalidate conflicting notes.'],
    ],
    experiment: 'Run the diagnostic in W1 and rotate. Add a staging decision in W2 and rotate again. In W3, ask why the fix failed, then ask for the original marker. Compare the tool traces.',
  },
};

export const glossary = [
  ['Context window', 'The input items available to the model on its next request. This app’s small input budget makes transitions easy to observe.'],
  ['Session', 'One continuing conversation with a stable identity. A session can span many context windows.'],
  ['Token', 'A unit of model input or output. The displayed input count includes instructions, tool schemas and request formatting.'],
  ['Journal', 'An append-only record of messages, tool calls and results, with their original window and timestamp.'],
  ['Compaction', 'Reducing active context, commonly by replacing earlier messages with a summary. Useful detail can be lost.'],
  ['Offload pointer', 'A compact reference that tells the agent where an original snapshot is stored and how to retrieve it.'],
  ['Provenance', 'The source of a fact: its event ID, window, timestamp and exact supporting evidence.'],
  ['Push + pull', 'Push selected notes into the next request; pull additional evidence through search only when needed.'],
];

const colors = {gold:'#c9a227', cyan:'#22d3ee', pink:'#ff3d8b', muted:'#8b93a3'};
export function architecture(kind = 'notes', compact = false) {
  const prefix = `d-${kind}-${compact ? 'small' : 'large'}`;
  const edge = (d, color='muted', dashed=false) => `<path d="${d}" stroke="${colors[color]}" stroke-width="1.5" fill="none" ${dashed ? 'stroke-dasharray="5 5"' : ''} marker-end="url(#${prefix}-${color})"/>`;
  const label = (x,y,text,color='muted') => `<text x="${x}" y="${y}" fill="${colors[color]}" font-size="10" font-family="Consolas, monospace" text-anchor="middle">${text}</text>`;
  const node = (x,y,w,title,sub,color='muted') => `<g><rect x="${x}" y="${y}" width="${w}" height="70" rx="9" fill="#141821" stroke="${colors[color]}" stroke-opacity=".6"/><circle cx="${x+17}" cy="${y+20}" r="3" fill="${colors[color]}"/><text x="${x+29}" y="${y+24}" fill="#f4f1ea" font-size="13" font-weight="600" font-family="Arial, sans-serif">${title}</text><text x="${x+17}" y="${y+47}" fill="#8b93a3" font-size="10" font-family="Consolas, monospace">${sub}</text></g>`;
  let body;
  if (kind === 'summary') {
    body = node(20,45,170,'W1 · original context','messages + tool outputs') + node(270,45,170,'Summary writer','select ≤ 140 words','gold') + node(520,45,170,'W2 · active context','summary + new question','gold')
      + edge('M190 80H264','gold') + edge('M440 80H514','gold')
      + node(20,195,230,'Original journal','inspectable; no retrieval tool') + edge('M105 115V189')
      + label(480,221,'Omitted details do not enter W2','gold')
      + label(355,20,'SELECTIVE REPLACEMENT','gold');
  } else if (kind === 'offload') {
    body = node(20,45,170,'W1 · original context','full window or tool pair') + node(270,45,170,'Synopsis + pointer','offload_id → snapshot','cyan') + node(520,45,170,'W2 · active context','pointer + new question','cyan')
      + edge('M190 80H264','cyan') + edge('M440 80H514','cyan')
      + node(20,195,230,'Immutable snapshot','original items + SHA-256','cyan')
      + edge('M105 115V189','cyan') + edge('M605 115V230H256','cyan',true)
      + edge('M250 250H675V121','cyan',true)
      + label(436,213,'on demand: retrieve an excerpt','cyan')
      + label(355,20,'REPLACEMENT WITH A RETURN PATH','cyan');
  } else {
    body = node(20,45,175,'Closed windows','W1 · W2 · original events') + node(275,45,170,'Note writer','fresh evidence only','pink') + node(535,45,170,'W3 · active context','carried notes + request','pink')
      + edge('M195 80H269','pink') + edge('M360 115V177','pink')
      + node(275,183,170,'Append-only notes','old entries unchanged','pink')
      + edge('M445 218H495V80H529','pink') + label(502,151,'carry','pink')
      + edge('M585 115V149H370V177','pink',true) + label(459,139,'search_notes','pink')
      + node(20,183,175,'Searchable journal','exact source evidence','cyan')
      + edge('M107 115V177','cyan') + edge('M625 115V290H107V259','cyan',true)
      + label(375,280,'search_session: recover original evidence','cyan')
      + label(355,20,'SELECTED KNOWLEDGE + RECOVERABLE EVIDENCE','pink');
  }
  return `<svg class="architecture" viewBox="0 0 730 315" role="img" aria-label="${kind === 'notes' ? 'Fresh original events become append-only notes carried to W3; missing evidence is searched in original windows' : kind === 'summary' ? 'Original context becomes a summary in the next window; omitted details have no retrieval path' : 'Original context is saved and replaced with a synopsis and pointer; retrieval restores excerpts'}"><defs>${Object.entries(colors).map(([name,color])=>`<marker id="${prefix}-${name}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7" fill="${color}"/></marker>`).join('')}</defs>${body}</svg>`;
}

export const starter = 'Mina owns Release Cedar. The retry limit is 4. Run the clock diagnostic once and briefly explain why the proposed fix failed. Keep the incidental trace marker in the original evidence; do not repeat it in your answer.';
export const probes = {
  retained: 'Who owns the release, what is the retry limit, and why did the clock fix fail?',
  marker: 'What was the exact trace_marker in the original diagnostic result? If it is unavailable, say so rather than guessing.',
  correction: 'Update from Mina: the retry limit is now 6. Which limit applies now?',
  staging: 'New decision: run staging validation before rollout. The owner and retry limit are unchanged. Acknowledge briefly.',
};
