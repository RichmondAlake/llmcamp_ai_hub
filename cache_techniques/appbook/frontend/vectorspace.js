'use strict';
// Vector-space viewer for the semantic cache page: cached and example questions projected to 3D (PCA), a query
// placed among them, the cache policy's verdict, and a dimension-by-dimension cosine calculation.
const POINT_COLORS={cached:'#52e2bd',expired:'#6f8178',example:'#ad9bff'};
const POINT_LABELS={cached:'Cached question (live)',expired:'Cached question (expired)',example:'Your example'};
const QUERY_EXAMPLES=[
 ['Paraphrase','What is the way to reverse a list in Python?'],
 ['Same words, other topic','Explain semantic caching, focusing on cache identity.'],
 ['Synonym','What are the downsides of prompt caching?'],
 ['Unrelated','What is the capital of France?'],
];

class EmbeddingView{
 constructor(canvas,onSelect){
  this.canvas=canvas;this.ctx=canvas.getContext('2d');this.onSelect=onSelect;
  this.yaw=.4;this.pitch=.25;this.zoom=1;this.points=[];this.query=null;this.selected=null;
  this.resize=new ResizeObserver(()=>this.draw());this.resize.observe(canvas);
  canvas.onpointerdown=e=>{this.drag={x:e.clientX,y:e.clientY,moved:false};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{
   if(this.drag){const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.yaw+=dx*.008;this.pitch+=dy*.008;this.drag={x:e.clientX,y:e.clientY,moved:true};this.draw();}
   else{const r=canvas.getBoundingClientRect(),hit=this.nearest(e.clientX-r.left,e.clientY-r.top);canvas.title=hit?`${POINT_LABELS[hit.kind]}: ${hit.text.slice(0,180)}`:'Drag to rotate. Scroll to zoom. Select a point.';}
  };
  canvas.onpointerup=e=>{if(this.drag&&!this.drag.moved){const r=canvas.getBoundingClientRect(),p=this.nearest(e.clientX-r.left,e.clientY-r.top);if(p){this.selected=p.id;this.onSelect(p);this.draw();}}this.drag=null;};
  canvas.onwheel=e=>{e.preventDefault();this.zoom=Math.min(4,Math.max(.4,this.zoom*Math.exp(-e.deltaY*.001)));this.draw();};
 }
 update(data){this.points=data.points;this.query=data.query;if(!this.points.some(p=>p.id===this.selected))this.selected=this.points[0]?.id;this.draw();const chosen=this.points.find(p=>p.id===this.selected);if(chosen)this.onSelect(chosen);}
 nearest(x,y){return this.screen?.filter(p=>Math.hypot(p.x-x,p.y-y)<15).sort((a,b)=>Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y))[0];}
 draw(){
  const canvas=this.canvas,box=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;
  if(!box.width)return;canvas.width=box.width*dpr;canvas.height=box.height*dpr;
  const ctx=this.ctx;ctx.scale(dpr,dpr);const w=box.width,h=box.height;ctx.clearRect(0,0,w,h);
  const all=[...this.points,...(this.query?[this.query]:[])],extent=Math.max(.3,...all.flatMap(p=>p.position.map(Math.abs)));
  const transform=([a,b,c])=>{const x=a*Math.cos(this.yaw)+c*Math.sin(this.yaw),z=-a*Math.sin(this.yaw)+c*Math.cos(this.yaw),y=b*Math.cos(this.pitch)-z*Math.sin(this.pitch),depth=b*Math.sin(this.pitch)+z*Math.cos(this.pitch),scale=Math.min(w,h)*.32/extent*this.zoom/(1+depth/extent*.13);return{x:w/2+x*scale,y:h/2-y*scale,z:depth};};
  ctx.lineWidth=1;ctx.strokeStyle='#2d473d';ctx.fillStyle='#92a69b';ctx.font='10px system-ui';
  for(let axis=0;axis<3;axis++){const p=[0,0,0],q=[0,0,0];p[axis]=-extent;q[axis]=extent;const a=transform(p),b=transform(q);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.fillText('PC'+(axis+1),b.x+5,b.y);}
  this.screen=this.points.map(p=>({...p,...transform(p.position)})).sort((a,b)=>a.z-b.z);
  const query=this.query?transform(this.query.position):null;
  for(const p of this.screen){
   const chosen=p.id===this.selected;
   if(query&&chosen){ctx.strokeStyle='#b7ff5a88';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(query.x,query.y);ctx.lineTo(p.x,p.y);ctx.stroke();ctx.setLineDash([]);}
   ctx.beginPath();ctx.arc(p.x,p.y,chosen?7:4.5,0,Math.PI*2);ctx.fillStyle=chosen?'#b7ff5a':POINT_COLORS[p.kind]+'cc';ctx.fill();
   if(chosen){ctx.fillStyle='#b7ff5a';ctx.fillText(p.text.slice(0,48)+(p.text.length>48?'…':''),p.x+11,p.y-8);}
  }
  if(query){ctx.fillStyle='#ffcc66';ctx.beginPath();ctx.moveTo(query.x,query.y-9);ctx.lineTo(query.x+8,query.y+6);ctx.lineTo(query.x-8,query.y+6);ctx.closePath();ctx.fill();ctx.fillText('QUERY',query.x+12,query.y+3);}
  if(!this.points.length){ctx.fillStyle='#92a69b';ctx.textAlign='center';ctx.fillText('Load the example set or add your own questions to populate this space.',w/2,h/2);ctx.textAlign='left';}
 }
 destroy(){this.resize.disconnect();}
}

function renderVectorSpace(ticket){
 $('#vector-space').innerHTML=`<section class="panel"><div class="panel-head"><h2>Vector space · what the semantic cache compares</h2><span class="pill" id="vs-count">Loading vectors</span></div>
 <div class="embedding-layout"><div><canvas id="vs-canvas" class="embedding-canvas" aria-label="Interactive 3D projection of stored question embeddings"></canvas>
 <div class="panel-body"><p class="hint">Drag to rotate · scroll to zoom · select a point. This is a 3D PCA view of 384-dimensional MiniLM vectors; every distance and verdict below uses all 384 dimensions.</p>
 <div class="vs-legend">${Object.entries(POINT_LABELS).map(([k,l])=>`<span><i style="background:${POINT_COLORS[k]}"></i>${l}</span>`).join('')}<span><i class="vs-triangle"></i>Query</span></div>
 <label for="vs-query">Try a question</label><input id="vs-query" placeholder="Type a question to see where it lands and whether the cache would reuse an answer">
 <div class="vs-chips">${QUERY_EXAMPLES.map(([label,text])=>`<button class="button secondary small" data-example="${esc(text)}" title="${esc(text)}">${esc(label)}</button>`).join('')}</div>
 <label for="vs-add">Add example questions</label><textarea id="vs-add" rows="2" placeholder="One question per line. Examples are embedded locally: no answer and no model call."></textarea>
 <div class="query-actions"><button class="button secondary small" id="vs-add-button">Embed and add</button><button class="button secondary small" id="vs-load">Load example set</button><button class="button secondary small" id="vs-clear">Clear my examples</button></div></div></div>
 <div class="stack"><section class="panel"><div class="panel-head"><h2>Would the cache reuse an answer?</h2></div><div class="panel-body" id="vs-verdict"><p class="hint">Type a question. The semantic cache's policy runs on the nearest stored questions, closest first: the cosine distance must be within the maximum distance set above, then the reranker must score the pair at or above its minimum. Examples count as cached questions here; they have no stored answer.</p></div></section>
 <section class="panel"><div class="panel-head"><h2>Nearest questions</h2></div><div class="panel-body" id="vs-neighbors"><p class="hint">Loading…</p></div></section>
 <section class="panel"><div class="panel-head"><h2>Distance, dimension by dimension</h2></div><div class="panel-body"><div id="vs-selected" class="memory-preview">Select a point.</div><div class="metric" id="vs-cosine">—</div><p class="hint" id="vs-distance">Type a question to calculate cosine distance.</p>
 <label>Query vector · all 384 dimensions</label><canvas id="vs-query-vector" class="vector-heatmap"></canvas><label>Selected question · all 384 dimensions</label><canvas id="vs-point-vector" class="vector-heatmap"></canvas>
 <label for="vs-dimension">Accumulated dot product · <span id="vs-dimension-label">384 / 384</span></label><input type="range" id="vs-dimension" min="0" max="384" value="384">
 <div class="query-actions"><button class="button secondary small" id="vs-animate">Play calculation</button><span class="pill" id="vs-dot">dot product —</span></div><p class="hint">The animation adds the actual per-dimension products. MiniLM vectors are normalised, so the final dot product equals the cosine similarity.</p></div></section></div></div></section>`;
 let data=null,selected=null,timer=null,frame=null,sequence=0,closed=false;
 const view=new EmbeddingView($('#vs-canvas'),p=>{selected=p;showDistance();});
 const threshold=()=>Number($('#compare-threshold')?.value||0.1);
 function showDistance(){
  if(!selected||closed)return;$('#vs-selected').innerHTML=`<b>${esc(POINT_LABELS[selected.kind])}</b><p>${esc(selected.text)}</p>`;heatmap($('#vs-point-vector'),selected.vector,108);
  if(!data?.query){$('#vs-cosine').textContent='—';return;}
  const q=data.query.vector,v=selected.vector,n=Number($('#vs-dimension').value),dot=q.reduce((s,x,i)=>s+(i<n?x*v[i]:0),0);
  const nq=Math.sqrt(q.reduce((s,x)=>s+x*x,0)),nv=Math.sqrt(v.reduce((s,x)=>s+x*x,0)),cosine=q.reduce((s,x,i)=>s+x*v[i],0)/(nq*nv);
  $('#vs-cosine').textContent=cosine.toFixed(4);$('#vs-distance').textContent=`Cosine distance ${(1-cosine).toFixed(4)} · maximum accepted ${threshold().toFixed(2)} · query norm ${nq.toFixed(4)} · question norm ${nv.toFixed(4)}`;
  $('#vs-dimension-label').textContent=`${n} / ${q.length}`;$('#vs-dot').textContent=`Σ qᵢvᵢ = ${dot.toFixed(5)}`;heatmap($('#vs-query-vector'),q,108);
 }
 function showVerdict(){
  const v=data?.verdict;
  if(!v){$('#vs-verdict').innerHTML=`<p class="hint">Type a question or pick an example above. The policy uses a maximum distance of ${threshold().toFixed(2)} (change it under <b>Cache identity, lifetime and search settings</b> above) and a reranker minimum of 0.</p>`;return;}
  const m=v.matched;
  $('#vs-verdict').innerHTML=`<div class="vs-decision ${v.hit?'hit':'miss'}">${v.hit?'Semantic hit · an answer would be reused':'Miss · Claude would generate a fresh answer'}</div>`+
   (m?`<p>Matched <b>${esc(m.text)}</b> (${esc(POINT_LABELS[m.kind].toLowerCase())}) at distance <b>${m.distance.toFixed(4)}</b> ≤ ${v.threshold.toFixed(2)}, reranker score <b>${m.rerank_score.toFixed(2)}</b> ≥ ${v.rerank_min}.</p>`:'')+
   `<ol class="vs-checked">${v.checked.map(c=>`<li><span class="pill ${c.outcome==='accepted'?'good':''}">${esc(c.outcome)}</span> ${esc(c.text)}</li>`).join('')||'<li>No stored questions to compare.</li>'}</ol><p class="hint">Similarity is not equivalence: a hit on a different question (for example another topic in the same sentence frame) is a false hit, the risk a lower maximum distance guards against.</p>`;
 }
 async function update(extra={}){
  const ticket2=++sequence;const result=await api('/api/vector-space',{query:$('#vs-query').value.trim(),threshold:threshold(),...extra});
  if(closed||ticket!==version||ticket2!==sequence)return;data=result;
  const counts=Object.fromEntries(Object.keys(POINT_LABELS).map(k=>[k,result.points.filter(p=>p.kind===k).length]));
  $('#vs-count').textContent=`${result.points.length} questions · ${result.dimensions}D · ${counts.cached} live, ${counts.expired} expired, ${counts.example} examples`;
  $('#vs-neighbors').innerHTML=result.points.length?result.points.slice(0,8).map((p,i)=>`<button class="neighbor-button" data-id="${esc(p.id)}"><span style="color:${POINT_COLORS[p.kind]}">${i+1}</span><b>${esc(p.text.slice(0,110))}</b><small>${p.cosine_distance!==undefined?p.cosine_distance.toFixed(4):esc(p.kind)}</small></button>`).join(''):'<p class="hint">No stored questions yet. Load the example set, add your own, or run the semantic comparison above.</p>';
  document.querySelectorAll('#vs-neighbors .neighbor-button').forEach(b=>b.onclick=()=>{selected=data.points.find(p=>p.id===b.dataset.id);view.selected=selected.id;view.draw();showDistance();});
  view.update(result);showVerdict();showDistance();refreshExplorer();
 }
 const run=(extra)=>update(extra).catch(e=>toast(e.message));
 $('#vs-query').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>run(),450);};
 document.querySelectorAll('[data-example]').forEach(b=>b.onclick=()=>{$('#vs-query').value=b.dataset.example;run();});
 $('#vs-add-button').onclick=()=>{const lines=$('#vs-add').value.split('\n').map(s=>s.trim()).filter(Boolean);if(!lines.length){toast('Enter one or more questions to add.');return;}busy($('#vs-add-button'),async()=>{await update({add:lines});$('#vs-add').value='';});};
 $('#vs-load').onclick=()=>busy($('#vs-load'),()=>update({load_examples:true}));
 $('#vs-clear').onclick=()=>busy($('#vs-clear'),()=>update({clear:true}));
 $('#vs-dimension').oninput=showDistance;
 $('#compare-threshold')?.addEventListener('change',()=>{if(data?.query)run();});
 $('#vs-animate').onclick=()=>{if(!data?.query){toast('Type a question first.');return;}cancelAnimationFrame(frame);let start=null;const total=data.query.vector.length;function step(t){if(closed)return;start=start??t;$('#vs-dimension').value=Math.min(total,Math.floor((t-start)/6));showDistance();if(Number($('#vs-dimension').value)<total)frame=requestAnimationFrame(step);}frame=requestAnimationFrame(step);};
 cleanup=()=>{closed=true;clearTimeout(timer);cancelAnimationFrame(frame);view.destroy();};
 run();
}
