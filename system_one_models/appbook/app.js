/* The UI presents real Oracle records. It never creates model results. */
const $=id=>document.getElementById(id), A=LabAnalysis;
const palette=['#486c50','#ac7735','#369c9a','#bc668e','#7a79ac','#ba6b49','#879245'];
const names={reranking:'Reranking',summary:'Summary quality',routing:'Memory routing',selection:'Tools & skills',chunking:'Semantic chunking',readers:'Memory readers'};
let lessons,current='reranking',selectedRun,pollTimer,busy=false,loadingModels=false,loadingLesson=false,runRequest=0,lessonRequest=0,modelSettings={};
let qualityMetric='ndcg',sortKey='label',sortAscending=true,lastRender='',catalogKind='all';
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function markdown(text){
 return escape(text).split('\n\n').map(p=>{
  if(p.startsWith('|')){
   const rows=p.split('\n').filter(line=>line.startsWith('|')).map(line=>line.slice(1,-1).split('|').map(c=>c.trim()));
   return '<div class="table-wrap"><table><thead><tr>'+rows[0].map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(2).map(row=>'<tr>'+row.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  }
  return '<p>'+p.replace(/^### (.*)$/gm,'<h3>$1</h3>').replace(/^##? (.*)$/gm,'<h2>$1</h2>')
  .replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>')
  .replace(/\[([^\]]+)\]\((https:\/\/[^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1 ↗</a>')+'</p>';
 }).join('');
}
async function api(path,options){const r=await fetch(path,options),data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const num=(v,n=3)=>finite(v)?v.toFixed(n):'—';
const usd=v=>finite(v)?'$'+v.toFixed(6):'Unknown';
function fmt(value,format='score'){
 if(!finite(value))return '—';
 if(format==='usd')return usd(value);if(format==='seconds')return num(value)+' s';
 if(format==='integer')return value.toLocaleString();if(format==='number')return num(value,1);
 return num(value);
}
function tab(name){
 const params=new URLSearchParams({lab:current,tab:name});if(selectedRun)params.set('run',selectedRun.id);
 history.replaceState(null,'','?'+params);
 document.querySelectorAll('.tab-panel').forEach(p=>p.hidden=p.id!==name);
 document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',b.dataset.tab===name));
 if(name==='build')loadNotebook().catch(showError);
}
function showError(e){$('error').textContent=e.message;}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
function helpButton(text,labelText){
 const b=node('button','ⓘ','metric-help');b.type='button';b.setAttribute('aria-label','Definition: '+labelText);b.title=text;
 b.onmouseenter=()=>showHelp(b,text);b.onfocus=()=>showHelp(b,text);b.onclick=()=>showHelp(b,text);
 b.onmouseleave=hideHelp;b.onblur=hideHelp;return b;
}
function showHelp(el,text){
 const tip=$('metric-tooltip');tip.textContent=text;tip.hidden=false;el.setAttribute('aria-describedby','metric-tooltip');
 const r=el.getBoundingClientRect(),w=Math.min(340,window.innerWidth-24);
 tip.style.width=w+'px';tip.style.left=Math.max(12,Math.min(r.left,window.innerWidth-w-12))+'px';
 const h=tip.getBoundingClientRect().height;tip.style.top=(r.bottom+h+14<innerHeight?r.bottom+8:Math.max(12,r.top-h-8))+'px';
}
function hideHelp(){$('metric-tooltip').hidden=true;}
document.addEventListener('keydown',e=>{if(e.key==='Escape')hideHelp();});
window.addEventListener('scroll',hideHelp,{passive:true});
async function choose(name,requestedRun,selectedTab='learn'){
 const generation=++lessonRequest;current=name;clearTimeout(pollTimer);selectedRun=null;lastRender='';loadingLesson=true;busy=false;runRequest++;
 document.dispatchEvent(new CustomEvent('appbook:run',{detail:{id:null,lab:name}}));
 qualityMetric=A.primary(name).key;sortKey='label';sortAscending=true;catalogKind='all';
 const lesson=lessons[name];
 const m=modelSettings;
 $('models').textContent=`Embeddings: ${m.VOYAGE_MODEL||'voyage-4'} · `+(name==='readers'?'Reader models: select the three models below.':
  `Jev: ${m.JEV_MODEL||'jev-1.13.0'}${name==='selection'?'':` · OpenAI: ${m.OPENAI_MODEL||'gpt-6-luna'}`}${name==='reranking'?` · Voyage reranker: ${m.VOYAGE_RERANK_MODEL||'rerank-2.5'}`:''}`);
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.lab===name));
 $('chapter-number').textContent=`LAB ${String(Object.keys(lessons).indexOf(name)+1).padStart(2,'0')} / SYSTEM ONE MODELS`;
 $('title').textContent=lesson.title;$('story').textContent=lesson.story;$('question').textContent=lesson.question;
 $('method').innerHTML=markdown(lesson.method);$('interpret').innerHTML=markdown(lesson.interpret);renderGuides(lesson);
 $('exercises').replaceChildren(...lesson.exercises.map(e=>node('li',e)));
 $('case-count').value=lesson.default_cases;$('case-count').max=lesson.max_cases;$('case-count').min=lesson.min_cases;
 $('case-count').removeAttribute('aria-invalid');
 $('case-range').textContent=`${lesson.min_cases}–${lesson.max_cases} available · Default: ${lesson.default_cases}`;
 updateRunPlan();
 $('case-label').textContent=name==='summary'?'Examples (includes 4 development)':'Questions';
 $('run-explanation').textContent=name==='summary'?'Four development examples calibrate the gate. Remaining examples form the scored test. A final generated-summary demonstration is shown separately.':'Runs real provider calls against local Oracle. Every completed result updates the charts; live calls incur usage.';
 $('reader-models').hidden=name!=='readers';loadingModels=name==='readers';
 $('catalog-filter').hidden=name!=='selection';$('catalog-kind').value='all';
 $('quality-metric').replaceChildren(...A.catalog[name].filter(m=>m.format==='score').map(m=>{const o=node('option',m.label);o.value=m.key;return o;}));
 $('quality-metric').value=qualityMetric;
 $('results').hidden=true;$('results-empty').hidden=false;$('error').textContent='';$('download-results').disabled=true;
 $('download-notebook').href='/api/notebook-package/'+name;$('download-notebook').download=lesson.notebook.replace('.ipynb','-lesson.zip');$('notebook-cells').replaceChildren();$('run').disabled=true;
 tab(['learn','build','experiment'].includes(selectedTab)?selectedTab:'learn');
 try{await refreshHistory(requestedRun);}catch(e){if(generation===lessonRequest)showError(e);}
 if(generation!==lessonRequest)return;
 if(name==='readers'){
  try{
   const data=await api('/api/models');if(generation!==lessonRequest)return;
   for(const id of ['reader-a','reader-b','reader-c']){
    $(id).replaceChildren(node('option','Select an available model…'));$(id).firstChild.value='';
    data.models.filter(m=>/^(claude-|gpt-(?:5\.6|6)-(?:sol|luna))/.test(m)).forEach(m=>{const o=node('option',m);o.value=m;$(id).append(o);});
    $(id).value={'reader-a':'claude-opus-5-5','reader-b':'gpt-6-sol','reader-c':'gpt-6-luna'}[id];
   }
  }catch(e){if(generation===lessonRequest)showError(e);}
 }
 if(generation===lessonRequest){loadingModels=false;loadingLesson=false;$('run').disabled=busy;}
}
async function loadNotebook(){
 const name=current;if($('notebook-cells').children.length)return;
 const nb=await api('/api/notebook/'+name);if(name!==current)return;
 nb.cells.forEach((cell,i)=>{
  const wrapper=node('article',undefined,'notebook-cell '+cell.cell_type),source=Array.isArray(cell.source)?cell.source.join(''):cell.source;
  if(cell.cell_type==='code'){
   wrapper.append(node('span','CELL '+(i+1),'cell-label'),node('pre',source));
   if(cell.outputs?.length)wrapper.append(notebookOutput(cell.outputs));
  }
  else if(cell.attachments){
   const heading=source.match(/^### (.+)/m);if(heading)wrapper.append(node('h3',heading[1]));
   for(const [name,attachment] of Object.entries(cell.attachments)){
    const img=node('img');img.alt=heading?.[1]||name;img.src='data:image/png;base64,'+attachment['image/png'];img.className='notebook-diagram';wrapper.append(img);
   }
   wrapper.append(node('p',source.split('\n\n').slice(2).join('\n\n')));
  }else wrapper.innerHTML=markdown(source);
  $('notebook-cells').append(wrapper);
 });
}
function notebookOutput(outputs){
 const block=node('div',undefined,'notebook-output');block.append(node('span','SAVED EXECUTED OUTPUT','cell-label'));
 outputs.forEach(out=>{
  const data=out.data||{};
  if(data['image/png']){
   const img=node('img');img.alt='Chart from the saved notebook execution';img.src='data:image/png;base64,'+data['image/png'];img.className='notebook-output-image';block.append(img);
  }else if(data['text/markdown']){
   const content=node('div',undefined,'prose');content.innerHTML=markdown([].concat(data['text/markdown']).join(''));block.append(content);
  }else if(data['text/html']){
   const html=Array.isArray(data['text/html'])?data['text/html'].join(''):data['text/html'];
   const parsed=new DOMParser().parseFromString(html,'text/html'),source=parsed.querySelector('table');
   if(source){
    // Recreate plain cells; never execute provider or notebook HTML/scripts.
    const table=node('table');source.querySelectorAll('tr').forEach(row=>{
     const tr=node('tr');row.querySelectorAll('th,td').forEach(c=>tr.append(node(c.tagName.toLowerCase(),c.textContent)));table.append(tr);
    });const scroll=node('div',undefined,'table-wrap output-scroll');scroll.append(table);block.append(scroll);
   }else if(data['text/plain'])block.append(node('pre',[].concat(data['text/plain']).join('')));
  }else if(out.text||data['text/plain'])block.append(node('pre',[].concat(out.text||data['text/plain']).join('')));
 });return block;
}
async function refreshHistory(preferred){
 const name=current,generation=lessonRequest,data=await api('/api/runs');if(name!==current||generation!==lessonRequest)return;
 const rows=data.runs.filter(r=>r.lab===name),wanted=preferred||selectedRun?.id;
 $('history').replaceChildren();
 for(const r of rows){const o=node('option',`${r.created.slice(0,19).replace('T',' ')} · ${r.status} · ${r.rows} rows · ${r.id.slice(0,8)}`);o.value=r.id;$('history').append(o);}
 if(!rows.length&&!wanted){const o=node('option','No saved Oracle runs yet');o.value='';$('history').append(o);return;}
 await openRun(wanted||rows[0].id);
}
function syncHistory(data){
 let option=[...$('history').options].find(o=>o.value===data.id);
 if(!option){option=node('option');option.value=data.id;$('history').prepend(option);}
 option.textContent=`${data.status} · ${(data.results||[]).length} result rows · ${data.id.slice(0,8)}${['queued','running'].includes(data.status)?' · LIVE':''}`;
 $('history').value=data.id;
}
$('history').onchange=()=>openRun($('history').value);
$('refresh').onclick=()=>refreshHistory().catch(showError);
function updateRunPlan(){
 const count=Number($('case-count').value),lesson=lessons[current];
 const valid=Number.isInteger(count)&&count>=lesson.min_cases&&count<=lesson.max_cases;
 $('run-plan').hidden=!valid||!['reranking','readers'].includes(current);
 if(!$('run-plan').hidden){
  const methods=current==='reranking'?7:3;
  $('run-plan').textContent=`${count} questions × ${methods} methods = ${count*methods} result rows.`+
   (current==='reranking'?` ${1+14*count} recorded calls, including ${count} local inference calls.`:'');
 }
}
$('case-count').oninput=()=>{$('case-count').removeAttribute('aria-invalid');$('error').textContent='';updateRunPlan();};
$('run').onclick=async()=>{
 const name=current;$('error').textContent='';$('run').disabled=true;
 try{
  const body={lab:name,limit:Number($('case-count').value)};
  if(!Number.isInteger(body.limit)||body.limit<Number($('case-count').min)||body.limit>Number($('case-count').max)){
   $('case-count').setAttribute('aria-invalid','true');$('case-count').focus();
   throw Error(`Enter a whole number from ${$('case-count').min} to ${$('case-count').max}. Each question uses a distinct labeled example.`);
  }
  if(name==='readers')body.models=[$('reader-a').value,$('reader-b').value,$('reader-c').value];
  const result=await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(name!==current)return;busy=true;await openRun(result.id);
 }catch(e){showError(e);$('run').disabled=busy;}
};
async function openRun(id){
 clearTimeout(pollTimer);const lab=current,requestId=++runRequest;
 try{
  const data=await api('/api/runs/'+id);if(lab!==current||requestId!==runRequest)return;
  if(data.lab&&data.lab!==current)throw Error('That saved run belongs to another lesson.');
  selectedRun=data;syncHistory(data);
  document.dispatchEvent(new CustomEvent('appbook:run',{detail:{id:data.id,lab:data.lab,
   sourceTable:data.storage_backend?'S1_VECTORS':'S1_DOCUMENTS'}}));
  const signature=JSON.stringify([data.id,data.status,data.updated_at,data.results,data.calls,data.active_call]);
  if(signature!==lastRender){render(data);lastRender=signature;}
  busy=['running','queued'].includes(data.status);$('run').disabled=busy||loadingModels||loadingLesson;
  const params=new URLSearchParams(location.search);params.set('run',id);history.replaceState(null,'','?'+params);
  if(busy)pollTimer=setTimeout(()=>openRun(id),800);
 }catch(e){showError(e);if(busy&&lab===current&&requestId===runRequest)pollTimer=setTimeout(()=>openRun(id),2000);}
}
const SVG='http://www.w3.org/2000/svg';
function svgEl(tag,attrs,text){const n=document.createElementNS(SVG,tag);Object.entries(attrs||{}).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;}
function label(s,x,y,text,attrs={}){s.append(svgEl('text',{x,y,...attrs},text));}
function canvas(target,text,height=310){const s=svgEl('svg',{viewBox:`0 0 520 ${height}`,role:'img','aria-label':text});$(target).replaceChildren(s);return s;}
function qualityChart(groups,metric){
 const height=Math.max(240,groups.length*40+65),s=canvas('quality-chart',metric.help,height),bottom=height-30;
 [0,.25,.5,.75,1].forEach(t=>{const x=166+t*290;s.append(svgEl('line',{x1:x,x2:x,y1:12,y2:bottom,stroke:'#e1e5d8'}));label(s,x,bottom+19,t.toFixed(2),{'text-anchor':'middle'});});
 groups.forEach((g,i)=>{
  const y=22+i*40,v=g[metric.key];label(s,155,y+9,g.label,{'text-anchor':'end','font-size':11});
  if(!finite(v)){label(s,172,y+9,g.n?'Undefined denominator':'Waiting for results',{'font-size':10});return;}
  const bar=svgEl('rect',{x:166,y:y-6,width:v*290,height:23,fill:palette[i%7],rx:3});
  bar.append(svgEl('title',{},`${g.label}: ${num(v)}, denominator ${g.denominators[metric.key]??g.n}`));s.append(bar);
  label(s,465,y+9,num(v),{'font-size':11});
 });
 $('quality-chart').dataset.rows=groups.reduce((s,g)=>s+g.n,0);
}
function economicsChart(groups){
 const s=canvas('economics-chart','Mean measured latency versus mean list-price API cost',300),valid=groups.filter(g=>finite(g.seconds)&&finite(g.cost));
 if(!valid.length){label(s,30,90,'Waiting for completed timing and cost measurements.');return;}
 const maxX=Math.max(.01,...valid.map(g=>g.seconds))*1.25,maxY=Math.max(.0000001,...valid.map(g=>g.cost))*1.25;
 [0,.25,.5,.75,1].forEach(t=>{const y=225-t*185,x=85+t*370;
  s.append(svgEl('line',{x1:85,x2:455,y1:y,y2:y,stroke:'#e1e5d8'}));label(s,77,y+4,'$'+(t*maxY).toFixed(6),{'text-anchor':'end','font-size':9});label(s,x,247,(t*maxX).toFixed(2),{'text-anchor':'middle'});
 });
 label(s,270,275,'Mean seconds per case (scope below)',{'text-anchor':'middle'});
 groups.forEach((g,i)=>{
  if(!finite(g.seconds)||!finite(g.cost))return;const x=85+g.seconds/maxX*370,y=225-g.cost/maxY*185;
  const c=svgEl('circle',{cx:x,cy:y,r:7,fill:palette[i%7],stroke:'#fff','stroke-width':2});
  c.append(svgEl('title',{},`${g.label}: ${num(g.seconds)}s · ${usd(g.cost)} · ${g.n} cases`));s.append(c);
  label(s,x+9,y-9,g.label,{'font-size':10});
 });
}
function trendChart(groups,metric){
 const s=canvas('trend-chart',`${metric.label} by case in dataset order`,255),ids=[...new Set(groups.flatMap(g=>g.rows.map(r=>r.case_id)))].sort();
 [0,.5,1].forEach(t=>{const y=180-t*145;s.append(svgEl('line',{x1:45,x2:500,y1:y,y2:y,stroke:'#e1e5d8'}));label(s,35,y+4,String(t),{'text-anchor':'end'});});
 ids.forEach((id,i)=>label(s,55+i*430/Math.max(1,ids.length-1),202,id,{'text-anchor':'middle','font-size':9}));
 groups.forEach((g,i)=>{
  const rows=g.rows.filter(r=>finite(A.rowValue(r,metric.key))).sort((a,b)=>a.case_id.localeCompare(b.case_id));
  const points=rows.map(r=>[55+ids.indexOf(r.case_id)*430/Math.max(1,ids.length-1),180-145*A.rowValue(r,metric.key)]);
  s.append(svgEl('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:palette[i%7],'stroke-width':2,opacity:.65}));
  points.forEach(([x,y],j)=>{const c=svgEl('circle',{cx:x,cy:y,r:3,fill:palette[i%7]});c.append(svgEl('title',{},`${g.label} · ${rows[j].case_id} · ${num(A.rowValue(rows[j],metric.key))}`));s.append(c);});
 });
 label(s,260,230,'Dataset order, not time. Missing cases have no invented score.',{'text-anchor':'middle','font-size':10});
 const legend=node('div',undefined,'legend');groups.forEach((g,i)=>{const e=node('span',g.label);e.style.setProperty('--color',palette[i%7]);legend.append(e);});$('trend-chart').append(legend);
}
function table(groups,data){
 const focused=document.activeElement?.dataset.sort;
 const t=node('table'),thead=node('thead'),head=node('tr'),cols=[{key:'label',label:'Method',format:'text'},...A.metrics(current)];
 t.append(node('caption','Method comparison · click a column name to sort; ⓘ explains the denominator.'));
 cols.forEach(m=>{
  const th=node('th');th.scope='col';th.setAttribute('aria-sort',sortKey===m.key?(sortAscending?'ascending':'descending'):'none');
  const b=node('button',m.label+(sortKey===m.key?(sortAscending?' ↑':' ↓'):' ↕'),'sort-button');b.dataset.sort=m.key;
  b.onclick=()=>{sortAscending=sortKey===m.key?!sortAscending:true;sortKey=m.key;table(groups,data);};th.append(b);
  if(m.help)th.append(helpButton(m.help,m.label));head.append(th);
 });
 thead.append(head);t.append(thead);const body=node('tbody');
 A.sort(groups,sortKey,sortAscending).forEach(g=>{
  const tr=node('tr');tr.dataset.arm=g.arm;
  cols.forEach(m=>{
   const td=node('td');if(m.key==='label'){td.append(node('strong',g.label),node('small',A.model(g.arm,data),'model-id'));}
   else {td.textContent=fmt(g[m.key],m.format);td.dataset.value=g[m.key]??'';if(m.help)td.title=m.help+(g.denominators[m.key]!=null?` Denominator in this row: ${g.denominators[m.key]}.`:'');}
   tr.append(td);
  });body.append(tr);
 });
 t.append(body);$('aggregate-table').replaceChildren(t);
 if(focused)$('aggregate-table').querySelector(`[data-sort="${focused}"]`)?.focus({preventScroll:true});
}
function glossary(){
 $('metric-glossary').replaceChildren(...A.metrics(current).filter(m=>m.help).map(m=>{const d=node('div');d.append(node('dt',m.label),node('dd',m.help));return d;}));
}
function renderCharts(data){
 const groups=A.aggregate(data,current,catalogKind),metric=A.catalog[current].find(m=>m.key===qualityMetric)||A.primary(current);
 $('quality-title').replaceChildren(document.createTextNode(metric.label+' '),helpButton(metric.help,metric.label));
 $('metric-direction').textContent=metric.direction==='higher'?'Higher is better':metric.direction==='lower'?'Lower is better':'Read with the other metrics';
 qualityChart(groups,metric);economicsChart(groups);table(groups,data);
 // Gate aggregate rates have no per-row field; show correctness for that line chart.
 const trendMetric=['bad_acceptance','good_rejection','accepted_defect_rate','coverage'].includes(metric.key)?A.primary(current):metric;
 $('trend-title').textContent=trendMetric.label+' · per case';trendChart(groups,trendMetric);glossary();
 $('measurement-scope').textContent=A.scopes[current];
 $('sample-note').textContent=(['queued','running'].includes(data.status)?'Live, partial results. Methods may have different sample counts. ':'')+
   (current==='summary'?'Quality includes test rows only; four development examples and the generated-summary demo are excluded. ':'')+
   'Means weight each eligible case equally. A dash means not available or an undefined denominator, never zero.';
}
function render(data){
 $('results').hidden=false;$('results-empty').hidden=true;$('download-results').disabled=false;
 const calls=data.calls||[],rows=data.results||[],running=['queued','running'].includes(data.status);
 $('status-line').textContent=`${data.status.toUpperCase()} / Oracle run ${data.id}`;$('error').textContent=data.error||'';
 const active=data.active_call,phase=data.progress?.stage;
 $('live-stage').textContent=active?`${phase||'Evaluating'} · ${active.case_id||'source setup'} · ${A.titles[active.arm]||active.arm||'shared'} · ${active.model} / ${active.lane}`:
   (phase||(running?'Waiting for the next measured result…':'Saved results loaded'));
 $('live-indicator').textContent=running?'● Live · updates every 0.8 s':'● Saved Oracle results';$('live-indicator').classList.toggle('is-live',running);
 $('last-updated').textContent=data.updated_at?'Saved '+new Date(data.updated_at).toLocaleTimeString():'';
 const input=calls.every(c=>finite(c.input_tokens))?calls.reduce((s,c)=>s+c.input_tokens,0):null;
 const completed=calls.filter(c=>c.status==='completed').length;
 const stats=[['Result rows',`${rows.length}${data.expected_results?' / '+data.expected_results:''}`,'One case × method; ranking may precede its reader'],
  ['Total API estimate',usd(A.total(calls)),'All recorded calls, including shared setup'],['Input tokens',input==null?'Unknown':input.toLocaleString(),'Provider usage + separately identified local work'],
  ['Completed calls',`${completed} / ${calls.length+(active?1:0)}`,active?'One request is currently in flight':'Failures remain in the ledger']];
 $('stats').replaceChildren(...stats.map(([name,value,note])=>{const d=node('div',undefined,'stat');d.append(node('span',name),node('strong',value),node('span',note));return d;}));
 $('protocol-note').textContent=((data.protocol_version||1)>=3?'Protocol v3 · OpenAI defaults to GPT-6 Luna with reasoning disabled; reader comparison retains medium effort. Reranking readers receive source IDs and text only. Shared costs and ledger writes remain separate.':
  (data.protocol_version||1)===2?'Protocol v2 · Same document content for rerankers; shared calls labeled separately; ledger writes excluded from decision latency.':
  'Historical protocol v1 · Real saved measurements. Jev/OpenAI rerankers also saw retrieval metadata; shared calls may carry the previous method label; decision timing includes ledger writes. Do not pool these results with v2.')+' Storage: '+(data.storage_backend||'python-oracledb / explicit SQL')+'.';
 const models=data.models||{};
 const used=[...new Set(calls.map(c=>`${c.provider}: ${c.model}`))];
 $('run-models').textContent=used.length?'Models with recorded calls · '+used.join(' · '):'Models appear here when their first call is recorded.';
 const voyage=calls.filter(c=>c.provider==='voyage'),cost=A.total(voyage),tok=voyage.reduce((s,c)=>s+(c.input_tokens||0),0);
 $('voyage-usage').textContent=`This run: ${voyage.length} recorded Voyage calls, ${tok.toLocaleString()} provider-reported input tokens, ${usd(cost)} list-price estimate. Embedding and reranking tokens use their respective saved prices. See every call below.`;
 renderCharts(data);
 const opened=new Set([...$('case-results').querySelectorAll('details[open]')].map(d=>d.dataset.key));
 $('case-results').replaceChildren(...rows.map(r=>{
  const detail=node('details'),summary=node('summary');detail.dataset.key=r.case_id+'/'+r.arm;detail.open=opened.has(detail.dataset.key);
  summary.append(node('span',A.titles[r.arm]||r.arm,'method-tag'),document.createTextNode(`${r.case_id} · ${r.question||r.defect||'Generated summary · human review required'}${r.split?' · '+r.split:''}`));detail.append(summary);
  const selected=(data.candidate_snapshots?.[r.case_id]||[]).filter(d=>r.selected_ids?.includes(d.id));
  detail.append(node('pre',JSON.stringify({...r,...(selected.length?{selected_evidence:selected}:{})},null,2)));return detail;
 }));
 $('ledger').textContent=JSON.stringify({price_date:data.price_date,prices:data.prices,local_load_seconds:data.local_load_seconds,calls},null,2);
}
$('quality-metric').onchange=()=>{qualityMetric=$('quality-metric').value;if(selectedRun)renderCharts(selectedRun);};
$('catalog-kind').onchange=()=>{catalogKind=$('catalog-kind').value;if(selectedRun)renderCharts(selectedRun);};
$('download-results').onclick=()=>{
 const url=URL.createObjectURL(new Blob([JSON.stringify(selectedRun,null,2)],{type:'application/json'}));
 const a=node('a');a.href=url;a.download=`system-one-${current}-${selectedRun.id}.json`;a.click();URL.revokeObjectURL(url);
};
(async()=>{
 try{
  lessons=await api('/api/lessons');
  Object.keys(lessons).forEach((name,i)=>{const b=node('button');b.dataset.lab=name;b.append(node('span',String(i+1).padStart(2,'0'),'num'),node('span',names[name]));b.onclick=()=>choose(name);$('chapters').append(b);});
  const status=await api('/api/status');$('connection').textContent=status.oracle?'Oracle configured · local lab':'Oracle needs configuration';
  modelSettings=status.models;
  const params=new URLSearchParams(location.search),name=params.get('lab'),requestedTab=params.get('tab');
  await choose(Object.hasOwn(lessons,name)?name:current,params.get('run'),requestedTab);
 }catch(e){$('connection').textContent='Connection needs attention';showError(e);}
})();
