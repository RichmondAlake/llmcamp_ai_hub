'use strict';

function cacheArchitecture(mechanism,features,kind){
 const embeddingOnly=mechanism==='embedding',raw=mechanism==='semantic',live=kind==='live'||mechanism==='tool',rag=mechanism==='unified'||mechanism==='baseline';
 const enabled=mechanism==='unified'?features:mechanism==='baseline'?{}:{[mechanism]:true};
 const components=[],flows=[],runs=[];
 const tiers=[{id:'entry',title:'REQUEST & IDENTITY',note:'Independent sandbox · model · source revision · configuration'},
  {id:'reuse',title:embeddingOnly?'VECTOR GENERATION':'ANSWER REUSE',note:live?'Live research bypasses application answer caches':'Only stable teaching questions are eligible for answer reuse'},
  {id:'evidence',title:'EVIDENCE & TOOLS',note:'Read-only research · collection time survives tool-cache hits'},
  {id:'generate',title:'CONTEXT & GENERATION',note:'Stable reference prefix comes before the changing request and evidence'},
  {id:'result',title:'RESULTS & MEASUREMENT',note:'Observed provider usage · local wall-clock timing · dated API estimates'}];
 const node=(id,name,tier,col,kind,tech,note,icon)=>components.push({id,name,tier,col,kind,tech,note,icon});
 const edge=(id,from,to,label,kind='data')=>{flows.push({id,from,to,label,kind});return id;};
 node('input','Shared request','entry',0,'channel','Cachecraft paired interface','Both lanes receive the same input and request type. Experiments freeze and review the complete workload.','browser');
 node('identity','Cache identity','entry',1,'control','Namespace + revision + TTL','Sandbox, model, source/prefix revision, options and request arguments determine cache identity. A fresh sandbox or revised context starts a new answer namespace.','shield');
 edge('identify','input','identity','Scope the request','request');
 let current='identity',cold=['identify'];
 const hop=(to,label,kind='data',id=null)=>{const flow=edge(id||current+'-'+to,current,to,label,kind);cold.push(flow);current=to;};
 if(embeddingOnly){
  node('embedding','Embedding TTL cache','reuse',0,'store','Text + model + revision + role + 384D','An exact embedding hit returns the saved vector. Query, document and shared-role vectors have independent identities.','vector');
  node('minilm','Local MiniLM encoder','reuse',2,'external','all-MiniLM-L6-v2 · 384 dimensions','A miss runs the open-source Hugging Face encoder locally on the CPU and stores the unit vector. It has no API cost; its compute time is part of request latency.','vector');
  hop('embedding','Exact vector key');hop('minilm','Miss → encode');
 }else{
  if(enabled.normal&&!live){node('normal','Exact answer cache','reuse',0,'store','Oracle True Cache · TTL rows','A matching stable request returns its saved answer without generation. The row is written to the primary and read through True Cache; expiry and context changes cause a miss.','memory');hop('normal','Exact answer key');}
  if(enabled.semantic&&!live){
   node('encoder','Question embedding','reuse',1,'external',enabled.embedding?'Local MiniLM + embedding TTL':'Local MiniLM · encoder run','A semantic lookup needs a query vector. Enabling embedding caching can avoid another encoder run for exactly the same text.','vector');
   node('semantic','Semantic answer cache','reuse',2,'store',raw?'Raw Oracle vector SQL':'OracleSemanticCache · HNSW','Compare only answers in this namespace. A cosine-distance threshold admits a candidate, a local cross-encoder reranker must confirm it, and expiry rejects stale answers. The individual technique uses raw SQL and the unified/experiment paths use langchain-oracledb.','database');
   hop('encoder',enabled.normal?'Answer miss → embed':'Embed question');hop('semantic','HNSW nearest answer');
  }
  if(live){
   if(enabled.tool){node('tool','Tool result TTL cache','evidence',0,'store','Tavily arguments + short TTL','Exact read-only search arguments reuse a timestamped response. Cached evidence is not a new live search, and fresh Claude output is still generated.','timer');hop('tool','Live request · bypass answers');}
   node('tavily','Tavily search','evidence',2,'external','Basic / advanced search','Cache misses call Tavily and retain the original collection time. Reported search credits contribute to the API estimate.','search');hop('tavily',enabled.tool?'Tool miss → search':'Fresh live search');
  }else if(rag){
   node('retrieval','Retrieve reference passages','evidence',0,'store','Oracle AI Database · HNSW','Embed this request and retrieve two authored passages. The same adapter reuses an embedding if its exact cache is enabled. Retrieval has no fabricated passages or user memory.','database');hop('retrieval',enabled.semantic?'Answer miss → retrieve':'Encode → HNSW retrieval');
  }
  node('context','Assemble context','generate',0,'control','Stable prefix + dynamic suffix','The instructions, reference passages and revision form a stable system prefix. The request and selected evidence follow the cache breakpoint.','doc');hop('context','Request + evidence');
  if(enabled.prompt){node('prompt','Provider prompt cache','generate',1,'external','Anthropic explicit breakpoint','Claude reports cache_creation_input_tokens and cache_read_input_tokens. Cache reads avoid reprocessing eligible input; they still produce a fresh answer and incur output cost.','memory');hop('prompt','Stable prefix breakpoint');}
  node('claude','Claude Opus 5.5','generate',2,'model','Raw Anthropic client','Generate a new grounded answer on every non-answer-cache hit. Uncached input, cache writes, cache reads and output are distinct API counters.','model');hop('claude',enabled.prompt?'Read / write prefix → generate':'Process input → generate');
 }
 node('output',embeddingOnly?'Vector output':'Answer output','result',0,'output',embeddingOnly?'Same vector on a cache hit':'Response + decisions','Successful stable answers populate the enabled answer caches. Live research bypasses answer storage. Failed requests preserve known usage and show unknown total cost.','output');hop('output',embeddingOnly?'Store vector · return':'Store eligible answer · return');
 node('usage','Measured usage','result',2,'observe','Timing + tokens + API credits','Compare actual wall-clock latency, reported provider counters and dated API cost estimates. Application hits and provider prompt reads are distinct. Shared and per-lane setup costs remain visible.','ledger');
 cold.push(edge('measure','output','usage','Record observed usage','event'));
 const step=(flow,note)=>({flow,note});
 runs.push({id:'cold',title:'Cold path · cache miss',blurb:'Illustrated execution path. This simulator makes no provider calls; use paired views or Tokenomics for measured results.',steps:cold.map(f=>step(f,flows.find(x=>x.id===f).label))});
 function reuseRun(id,from,title,note){const hit=edge(id+'-return',from,'output','Hit → reuse result');const idx=cold.findIndex(f=>flows.find(x=>x.id===f).to===from);runs.push({id,title,blurb:note,steps:[...cold.slice(0,idx+1).map(f=>step(f,flows.find(x=>x.id===f).label)),step(hit,note),step('measure','A hit can still include lookup or encoder cost.')]});}
 if(embeddingOnly)reuseRun('vector-hit','embedding','Warm embedding · exact hit','Return the stored vector; no encoder or Claude request.');
 if(enabled.normal&&!live&&!embeddingOnly)reuseRun('normal-hit','normal','Warm answer · exact hit','Read through True Cache (primary fallback): the saved answer bypasses embeddings, retrieval and Claude.');
 if(enabled.semantic&&!live&&!embeddingOnly)reuseRun('semantic-hit','semantic','Warm answer · semantic hit','A close question within the distance threshold, confirmed by the reranker, reuses the answer. The query is still embedded locally (compute time, no API cost).');
 if(enabled.tool&&live){const skip=edge('tool-hit','tool','context','Tool hit → timestamped evidence');const idx=cold.findIndex(f=>flows.find(x=>x.id===f).to==='tool'),suffix=cold.slice(cold.findIndex(f=>flows.find(x=>x.id===f).from==='context'));runs.push({id:'tool-hit',title:'Warm tool · fresh answer',blurb:'Reuse search evidence within its short TTL. Preserve collection time; Claude still generates.',steps:[...cold.slice(0,idx+1).map(f=>step(f,'Scoped read-only request')),step(skip,'Bypass Tavily, retain evidence timestamp'),...suffix.map(f=>step(f,flows.find(x=>x.id===f).label))]});}
 if(enabled.prompt&&!embeddingOnly)runs.push({id:'prompt-hit',title:'Warm prefix · fresh output',blurb:'An answer-cache miss can still hit the provider prompt cache. Only the live API counters prove a read.',steps:cold.map(f=>step(f,flows.find(x=>x.id===f).to==='claude'?'Provider reads the stable prefix; dynamic input and fresh output remain billable.':flows.find(x=>x.id===f).label))});
 if(Object.values(enabled).some(Boolean))runs.push({id:'expired',title:'Expired / revised · work again',blurb:'Application TTL or a changed source revision rejects reuse. Provider prefixes use a different identity when the context revision changes.',steps:cold.map(f=>step(f,flows.find(x=>x.id===f).label))});
 const story=STORIES[mechanism],second=story&&runs.find(r=>r.id===story.hit);
 if(second){
  // Two requests on one diagram: the first does the work and stores it, the second reuses it.
  const label=(steps,state)=>steps.map(s=>({...s,state}));
  runs.unshift({id:'story',title:story.title,blurb:story.blurb+' This simulator makes no provider calls.',
   steps:[...label(runs[0].steps,'Request 1 · '+story.first),...label(second.steps,'Request 2 · '+story.second)]});
 }
 return {tiers,components,flows,runs};
}

// The "miss, then hit" run for each mechanism on its own: which run supplies the second request, and what to say.
const STORIES={
 normal:{hit:'normal-hit',title:'Miss, then exact hit · the same question twice',first:'miss: generate, write to the primary',second:'exact hit served by True Cache',
  blurb:'The first request misses, Claude generates, and the answer is written to the primary. True Cache follows the primary through redo apply, so the identical second request is answered from True Cache with no model call.'},
 embedding:{hit:'vector-hit',title:'Miss, then vector hit · the same text twice',first:'miss: run the local encoder',second:'vector hit, no encoder run',
  blurb:'The first request runs the local MiniLM encoder and stores the vector under its identity (text, model, revision, role, dimensions). The second identical text returns the stored vector without running the encoder.'},
 semantic:{hit:'semantic-hit',title:'Miss, then semantic hit · a question, then its paraphrase',first:'miss: embed, search, generate, store',second:'paraphrase: distance and reranker accept',
  blurb:'The first question misses, Claude answers, and the answer is stored with its vector in Oracle. A paraphrase is embedded, found by the HNSW search within the distance threshold, confirmed by the reranker, and served without a model call.'},
 prompt:{hit:'prompt-hit',title:'Write, then read the prefix · two different questions',first:'provider writes the stable prefix',second:'provider reads the prefix, fresh output',
  blurb:'Prompt caching never skips the model. The first request writes the stable prefix to the provider cache; the second, with a different question, reads it back. Claude still generates a fresh answer and output tokens are still billed.'},
 tool:{hit:'tool-hit',title:'Miss, then tool hit · the same search twice',first:'miss: call Tavily, store the result',second:'tool hit: reuse timestamped evidence',
  blurb:'The first live request calls Tavily and stores the read-only result with its collection time. The identical second search reuses that evidence within its short TTL; Claude still writes a fresh answer from it.'},
};
const ISOLATED=Object.keys(STORIES);

function renderArchitecture(ticket){
 let player=null,isolated=null;cleanup=()=>player?.reset();
 $('#stage').innerHTML=hero('REFERENCE ARCHITECTURE · INTERACTIVE','Follow the request. <em>See what gets skipped.</em>','Select the cache technique or stack, inspect each component, and step through cold, warm or expired paths, or play one mechanism in isolation. The diagram changes to match the live interfaces and experiment configurations.')+`<section class="panel arch-controls"><div class="panel-body"><div class="cache-controls"><div><label for="architecture-kind">Architecture</label><select id="architecture-kind">${Object.entries(INFO).map(([key,item])=>`<option value="${key}" ${key==='unified'?'selected':''}>${item.name}</option>`).join('')}<option value="baseline">Uncached experiment baseline</option></select></div><div id="architecture-request-field"><label for="architecture-request">Request path</label><select id="architecture-request"><option value="explanation">Stable educational question</option><option value="live">Live Tavily research</option></select></div></div><div class="arch-options" id="architecture-options">${featureControls('architecture-feature')}</div><p class="hint" id="architecture-isolation" hidden></p></div></section><div id="architecture-diagram"></div>`;
 // In the unified view the run menu also offers each mechanism alone: choosing one redraws that mechanism's own
 // topology (the same components as its paired interface) and selects its "miss, then hit" run.
 function draw(select){
  if(ticket!==version)return;player?.reset();
  const kind=$('#architecture-kind').value,unified=kind==='unified',path=$('#architecture-request').value,features=readFeatures($('#architecture-options'));
  if(!unified)isolated=null;
  $('#architecture-options').hidden=!unified||!!isolated;$('#architecture-request-field').hidden=['embedding','tool'].includes(kind)||!!isolated;
  const note=$('#architecture-isolation');note.hidden=!isolated;
  if(isolated)note.innerHTML=`Showing the <b>${INFO[isolated].name.toLowerCase()}</b> on its own: the components and paths of its paired interface, without the rest of the stack. Choose a <b>Full stack</b> run to return.`;
  const menu=[];
  if(unified)menu.push(...ISOLATED.filter(m=>m!==isolated).map(m=>({value:'iso:'+m,label:INFO[m].name+' · in isolation',group:'Each mechanism in isolation'})));
  if(isolated)menu.push(...cacheArchitecture(kind,features,path).runs.map(r=>({value:'full:'+r.id,label:r.title,group:'Full stack'})));
  const spec=isolated?cacheArchitecture(isolated,{},isolated==='tool'?'live':'explanation'):cacheArchitecture(kind,features,path);
  player=RefArch.render($('#architecture-diagram'),spec,{menu,select:select||(isolated?'story':undefined),
   runGroup:isolated?INFO[isolated].name+' · in isolation':'Full stack',
   onMenu:value=>{const [type,id]=value.split(':');isolated=type==='iso'?id:null;draw(type==='iso'?'story':id);}});
 }
 $('#architecture-kind').onchange=()=>draw();$('#architecture-request').onchange=()=>draw();$('#architecture-options').onchange=()=>{localStorage.setItem('cache-features',JSON.stringify(readFeatures($('#architecture-options'))));draw();};draw();
}
