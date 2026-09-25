/* An Oracle browser and an observed-event journal, never simulated activity. */
(()=>{
 'use strict';
 const el=id=>document.getElementById(id);
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const dock=el('db-dock'),resize=el('db-resize'),events=new Map(),pulses=new Map();
 let preferences={};try{preferences=JSON.parse(localStorage.getItem('s1-database-dock')||'{}');}catch{}
 const state={open:false,height:Number(preferences.height)||430,paused:false,tab:'data',table:preferences.table||'S1_DOCUMENTS',
  offset:0,limit:25,search:'',sort:'',direction:'asc',run:null,sourceTable:'S1_DOCUMENTS',runScope:'all',source:'work',kind:'all',catalog:null,cursor:0,
  initialized:false,busy:false,timer:null,lastCatalog:0,lastRows:0,dataToken:0,dirty:true,detail:null,detailToken:0};
 const clock=iso=>new Date(iso).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
 const statusText=s=>({pending_commit:'Awaiting commit',committed:'Committed',rolled_back:'Rolled back',autocommitted:'Autocommitted',
  implicit_commit:'Implicit commit',outcome_unknown:'Outcome unknown',already_exists:'Already exists',completed:'Completed',running:'Running',failed:'Failed'}[s]||s);
 function save(){try{localStorage.setItem('s1-database-dock',JSON.stringify({open:state.open,height:state.height,table:state.table}));}catch{}}
 function limits(){const max=Math.floor(innerHeight*.82);return {min:Math.min(300,max),max};}
 function layout(){
  const {min,max}=limits();state.height=Math.max(min,Math.min(max,state.height));
  dock.style.setProperty('--db-height',state.height+'px');document.documentElement.style.setProperty('--db-visible',(state.open?state.height:60)+'px');
  resize.setAttribute('aria-valuemin',min);resize.setAttribute('aria-valuemax',max);resize.setAttribute('aria-valuenow',Math.round(state.height));
  resize.setAttribute('aria-valuetext',state.open?`${Math.round(state.height)} pixels high`:'Collapsed');
 }
 function indicator(text,live=false){el('db-connection').textContent=text;el('db-connection').classList.toggle('is-live',live);}
 function showError(error){el('db-error').textContent=error?.message||String(error);el('db-error').hidden=false;indicator('Retrying…');}
 async function request(path){const response=await fetch(path,{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'Database request failed');return data;}
 function setOpen(open){
  state.open=open;dock.classList.toggle('is-open',open);el('db-body').hidden=!open;
  el('db-toggle').setAttribute('aria-expanded',String(open));el('db-chevron').textContent=open?'⌄':'⌃';
  if(!open){closeDetail();clearTimeout(state.timer);state.dataToken++;indicator('Collapsed');}
  layout();save();if(open)cycle(true);
 }
 el('db-toggle').onclick=()=>setOpen(!state.open);
 let drag=null;
 resize.addEventListener('pointerdown',e=>{
  if(e.button!==0)return;e.preventDefault();drag={y:e.clientY,height:state.open?state.height:60,moved:false};
  resize.setPointerCapture(e.pointerId);document.body.classList.add('db-resizing');
 });
 resize.addEventListener('pointermove',e=>{
  if(!drag)return;const delta=drag.y-e.clientY;if(Math.abs(delta)<3&&!drag.moved)return;
  drag.moved=true;if(!state.open)setOpen(true);state.height=drag.height+delta;layout();
 });
 function endDrag(){drag=null;document.body.classList.remove('db-resizing');save();}
 resize.addEventListener('pointerup',endDrag);resize.addEventListener('pointercancel',endDrag);resize.addEventListener('lostpointercapture',endDrag);
 resize.addEventListener('keydown',e=>{
  if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;e.preventDefault();if(!state.open)setOpen(true);
  state.height=e.key==='Home'?limits().min:e.key==='End'?limits().max:state.height+(e.key==='ArrowUp'?24:-24);layout();save();
 });
 window.addEventListener('resize',layout);
 function setTab(name){
  state.tab=name;document.querySelectorAll('[data-db-tab]').forEach(b=>{const active=b.dataset.dbTab===name;b.setAttribute('aria-selected',active);b.tabIndex=active?0:-1;});
  for(const id of ['data','activity','transactions'])el('db-'+id).hidden=id!==name;
  if(name==='data'&&(state.dirty||Date.now()-state.lastRows>5000))readRows().catch(showError);
  renderActivity();
 }
 document.querySelectorAll('[data-db-tab]').forEach((b,i,buttons)=>{
  b.onclick=()=>setTab(b.dataset.dbTab);b.tabIndex=i? -1:0;
  b.onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const next=buttons[(i+(e.key==='ArrowRight'?1:buttons.length-1))%buttons.length];next.click();next.focus();};
 });
 el('db-pause').onclick=()=>{
  state.paused=!state.paused;el('db-pause').textContent=state.paused?'Resume live':'Pause live';el('db-pause').setAttribute('aria-pressed',state.paused);
  clearTimeout(state.timer);indicator(state.paused?'Paused':'Live',!state.paused);if(!state.paused)cycle(true);
 };
 el('db-refresh').onclick=()=>cycle(true);
 document.addEventListener('visibilitychange',()=>{clearTimeout(state.timer);if(!document.hidden&&state.open&&!state.paused)cycle(true);});
 document.addEventListener('appbook:run',e=>{
  const run=e.detail?.id||null,sourceTable=e.detail?.sourceTable||'S1_DOCUMENTS';
  if(state.run===run&&state.sourceTable===sourceTable)return;state.run=run;state.sourceTable=sourceTable;
  const option=el('db-run-scope').querySelector('[value=selected]');option.disabled=!run;option.textContent=run?'Selected run · '+run.slice(0,8):'Selected experiment';
  if(state.runScope==='selected'){
   state.offset=0;state.dirty=true;
   if(['S1_DOCUMENTS','S1_VECTORS'].includes(state.table)){state.table=sourceTable;state.sort='';renderObjects();}
   if(!run){state.runScope='all';el('db-run-scope').value='all';}
   if(state.open)readRows().catch(showError);
  }
 });
 function selectTable(name){
  if(state.table===name&&state.catalog)return;
  state.table=name;state.offset=0;state.sort='';state.direction='asc';state.search='';state.dataToken++;state.dirty=true;
  el('db-search').value='';closeDetail();save();renderObjects();readRows().catch(showError);
 }
 function renderObjects(){
  if(!state.catalog)return;el('db-object-count').textContent=state.catalog.objects.length;
  el('db-object-list').replaceChildren(...state.catalog.objects.map(obj=>{
   const button=make('button',undefined,'db-object');button.dataset.table=obj.name;button.setAttribute('aria-current',obj.name===state.table);
   button.title=obj.description;button.append(make('span',(obj.kind==='VIEW'?'▤ ':'▦ ')+obj.name,'db-object-name'));
   const meta=make('span',undefined,'db-object-meta');meta.append(make('span',obj.kind==='TABLE'?'Table':'View'),make('span',obj.rows.toLocaleString()+' rows'));
   button.append(meta,make('span','No new activity','db-object-event'));button.onclick=()=>selectTable(obj.name);return button;
  }));applyPulses();
 }
 function applyPulses(){
  document.querySelectorAll('.db-object').forEach(b=>{
   const pulse=pulses.get(b.dataset.table),fresh=pulse&&pulse.until>Date.now();
   if(fresh)b.dataset.activity=pulse.kind;else delete b.dataset.activity;
   b.querySelector('.db-object-event').textContent=pulse?`${pulse.kind==='failed'?'Failed':pulse.kind.toLowerCase()} · ${clock(pulse.at)}`:'No new activity';
  });
 }
 async function readCatalog(){
  const data=await request('/api/database/catalog');if(!state.open)return;
  state.catalog=data;state.lastCatalog=Date.now();el('db-identity').textContent=`${data.schema} / ${data.pdb} · ${data.objects.length} objects`;
  if(!data.objects.some(o=>o.name===state.table)){state.table=data.objects[0]?.name||'';state.offset=0;state.sort='';state.dirty=true;}
  renderObjects();
 }
 const runFilter=()=>state.runScope==='selected'?state.run||'':'';
 async function readRows(){
  if(!state.open||!state.table||!state.catalog)return;
  const token=++state.dataToken,params=new URLSearchParams({offset:state.offset,limit:state.limit,search:state.search,run:runFilter(),sort:state.sort,direction:state.direction});
  const data=await request('/api/database/table/'+encodeURIComponent(state.table)+'?'+params);
  if(token!==state.dataToken||!state.open)return;
  if(data.total>0&&state.offset>=data.total){state.offset=Math.floor((data.total-1)/state.limit)*state.limit;return readRows();}
  state.lastRows=Date.now();state.dirty=false;renderRows(data);
  el('db-updated').textContent='Updated '+clock(data.as_of);
 }
 function renderRows(data){
  el('db-table-name').textContent=data.name;el('db-table-description').textContent=data.description;
  const grid=el('db-grid'),top=grid.scrollTop,left=grid.scrollLeft,focused=grid.contains(document.activeElement)?document.activeElement:null,
   focusColumn=focused?.dataset.column,focusRecord=focused?.getAttribute('aria-label'),table=make('table'),head=make('thead'),hr=make('tr');
  hr.append(make('th','Open'));
  data.columns.forEach(col=>{
   const th=make('th'),button=make('button',(col.primary_key?'⌑ ':'')+col.name+(state.sort===col.name?(state.direction==='asc'?' ↑':' ↓'):''));
   button.disabled=!col.sortable;button.title=col.sortable?'Sort by '+col.name:'Open a record to inspect this value';button.dataset.column=col.name;
   th.setAttribute('aria-sort',state.sort===col.name?(state.direction==='asc'?'ascending':'descending'):'none');
   button.onclick=()=>{state.direction=state.sort===col.name&&state.direction==='asc'?'desc':'asc';state.sort=col.name;state.offset=0;readRows().catch(showError);};
   th.append(button,make('span',col.type+(col.primary_key?' · primary key':''),'db-col-type'));hr.append(th);
  });head.append(hr);table.append(head);const body=make('tbody');
  data.rows.forEach((row,i)=>{
   const tr=make('tr'),index=make('td'),open=make('button','↗');open.disabled=!row.key;open.setAttribute('aria-label',`Inspect record ${data.offset+i+1} in ${data.name}`);
   open.title=row.key?'Inspect full record':'This view has no stable record key';open.onclick=()=>openRecord(data.name,row.key,open);index.append(open);tr.append(index);
   data.columns.forEach(col=>{
    const cell=row.cells[col.name],v=cell.preview,txt=v===null?'NULL':typeof v==='object'?JSON.stringify(v):String(v);
    const td=make('td',txt+(cell.truncated?' …':''),v===null?'db-null':cell.truncated?'db-truncated':'');
    td.title=cell.truncated?'Preview only. Open the record for the full value.':txt;tr.append(td);
   });body.append(tr);
  });table.append(body);grid.replaceChildren(table);
  if(!data.rows.length)grid.append(make('p',data.search||data.run_id?'No rows match these filters. Clear the search or select All experiments.':'This object has no committed rows yet.','db-empty'));
  grid.scrollTop=top;grid.scrollLeft=left;
  if(focusColumn)grid.querySelector(`[data-column="${CSS.escape(focusColumn)}"]`)?.focus({preventScroll:true});
  else if(focusRecord)grid.querySelector(`[aria-label="${CSS.escape(focusRecord)}"]`)?.focus({preventScroll:true});
  el('db-row-range').textContent=data.total?`${data.offset+1}–${data.offset+data.rows.length} of ${data.total.toLocaleString()} rows`:'0 rows';
  el('db-previous').disabled=data.offset===0;el('db-next').disabled=!data.has_more;
 }
 let searchTimer;
 el('db-search').oninput=()=>{clearTimeout(searchTimer);state.dataToken++;searchTimer=setTimeout(()=>{state.search=el('db-search').value.trim();state.offset=0;readRows().catch(showError);},350);};
 el('db-limit').onchange=()=>{state.limit=Number(el('db-limit').value);state.offset=0;readRows().catch(showError);};
 el('db-run-scope').onchange=()=>{
  state.runScope=el('db-run-scope').value;state.offset=0;
  if(state.runScope==='selected'&&['S1_DOCUMENTS','S1_VECTORS'].includes(state.table)){
   state.table=state.sourceTable;state.sort='';renderObjects();
  }
  readRows().catch(showError);
 };
 el('db-previous').onclick=()=>{state.offset=Math.max(0,state.offset-state.limit);readRows().catch(showError);};
 el('db-next').onclick=()=>{state.offset+=state.limit;readRows().catch(showError);};
 let detailOpener=null;
 async function openRecord(name,key,opener){
  const token=++state.detailToken;detailOpener=opener;state.detail=null;el('db-detail-download').disabled=true;
  el('db-detail-title').textContent=name+' / full record';el('db-detail-content').textContent='Reading this record from Oracle…';el('db-detail').hidden=false;el('db-detail-close').focus();
  try{
   const data=await request('/api/database/row/'+encodeURIComponent(name)+'?'+new URLSearchParams({key:JSON.stringify(key)}));
   if(token!==state.detailToken)return;state.detail=data;el('db-detail-content').textContent=JSON.stringify(data.record,null,2);el('db-detail-download').disabled=false;
   el('db-detail-note').textContent=`Read ${clock(data.as_of)} · Full stored record, including vectors and JSON. Reopen to refresh.`;
  }catch(error){if(token===state.detailToken)el('db-detail-content').textContent=error.message;}
 }
 function closeDetail(){state.detailToken++;el('db-detail').hidden=true;state.detail=null;if(detailOpener?.isConnected&&state.open)detailOpener.focus();detailOpener=null;}
 el('db-detail-close').onclick=closeDetail;
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('db-detail').hidden){e.preventDefault();closeDetail();}});
 el('db-detail-download').onclick=()=>{
  if(!state.detail)return;const url=URL.createObjectURL(new Blob([JSON.stringify(state.detail,null,2)],{type:'application/json'})),a=make('a');
  a.href=url;a.download=state.detail.table.toLowerCase()+'-record.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 const sourceMatches=e=>state.source==='all'||(state.source==='experiment'?e.source==='experiment':e.source!=='explorer');
 const orderedEvents=()=>[...events.values()].sort((a,b)=>b.started_at.localeCompare(a.started_at)||b.sequence-a.sequence);
 const filteredEvents=()=>orderedEvents().filter(e=>sourceMatches(e)&&(state.kind==='all'||(state.kind==='failed'?e.status==='failed':e.kind===state.kind)));
 function opBadge(kind){const n=make('span',kind,'db-op');n.dataset.kind=kind;return n;}
 function statusBadge(status){const n=make('span',statusText(status),'db-status');n.dataset.status=status;return n;}
 function detailsContainer(event,id){
  const details=make('details');details.dataset.event=id;const summary=make('summary');summary.append(make('span',clock(event.started_at),'db-event-time'));
  return {details,summary};
 }
 function replaceLogs(container,items){
  const opened=new Set([...container.querySelectorAll('details[open]')].map(n=>n.dataset.event)),scroll=container.scrollTop,height=container.scrollHeight;
  items.forEach(n=>{if(opened.has(n.dataset.event))n.open=true;});container.replaceChildren(...items);
  container.scrollTop=scroll<5?0:Math.max(0,scroll+container.scrollHeight-height);
 }
 function renderActivity(){
  const selected=filteredEvents();el('db-event-count').textContent=selected.length.toLocaleString();
  if(state.tab==='activity'){
   const items=selected.slice(0,300).map(e=>{
    const {details,summary}=detailsContainer(e,e.event_id);summary.append(opBadge(e.kind),make('span',e.tables?.join(', ')||'Connection'),statusBadge(e.status),
     make('span',e.duration_ms==null?'Included in SQL':e.duration_ms.toFixed(1)+' ms','db-duration'));
    summary.title='Expand to inspect SQL and provenance';const content=make('div',undefined,'db-event-detail');
    content.append(make('p',`Source: ${e.source} · ${e.rows==null?'Row count not available':`${e.rows} rows ${e.kind==='READ'?'fetched':'affected'}`} · Client connection: ${e.connection_id}`),
     make('p',`Run: ${e.run_id||'—'} · Question: ${e.case_id||'—'} · Method: ${e.arm||'—'} · Client transaction: ${e.transaction_id||'none'}`));
    if(e.error)content.append(make('p','Error: '+e.error));content.append(make('pre',e.sql||e.kind));details.append(summary,content);return details;
   });replaceLogs(el('db-events'),items.length?items:[make('p','No matching activity has been observed. Run an experiment to see its reads, writes and commits. Historical notebook runs remain browsable as data.','db-empty')]);
  }
  if(state.tab==='transactions')renderTransactions();
 }
 function renderTransactions(){
  const groups=new Map();for(const e of orderedEvents().filter(e=>e.transaction_id&&e.source!=='explorer')){
   if(!groups.has(e.transaction_id))groups.set(e.transaction_id,[]);groups.get(e.transaction_id).push(e);
  }
  const items=[...groups].slice(0,150).map(([id,steps])=>{
   steps.sort((a,b)=>a.started_at.localeCompare(b.started_at));const latest=steps.at(-1),writes=steps.filter(e=>e.kind==='WRITE');
   const tables=[...new Set(steps.flatMap(e=>e.tables||[]))],{details,summary}=detailsContainer(latest,id);
   summary.append(opBadge('TXN'),make('span',`${id} · ${writes.length} writes`,'db-transaction-heading'),statusBadge(latest.status),make('span',tables.join(', '),'db-duration'));
   const content=make('div',undefined,'db-event-detail');content.append(make('p',`Run: ${latest.run_id||'—'} · Tables: ${tables.join(', ')||'none'} · Recent observed operations:`));
   steps.forEach(e=>content.append(make('div',`${clock(e.started_at)} · ${e.kind} · ${e.tables?.join(', ')||'connection'} · ${statusText(e.status)}${e.rows==null?'':` · ${e.rows} rows`}`,'db-transaction-step')));
   details.append(summary,content);return details;
  });replaceLogs(el('db-transaction-list'),items.length?items:[make('p','No writes have been observed yet. A live experiment will show which writes become visible together when its connection commits.','db-empty')]);
 }
 el('db-source').onchange=()=>{state.source=el('db-source').value;renderActivity();};
 el('db-kind').onchange=()=>{state.kind=el('db-kind').value;renderActivity();};
 async function readActivity(){
  const data=await request('/api/database/activity?after='+state.cursor);if(!state.open)return;
  const shouldHighlight=state.initialized;state.cursor=data.cursor;
  data.events.forEach(e=>{
   events.set(e.event_id,e);
   if(shouldHighlight&&sourceMatches(e)){
    for(const table of e.tables||[]){
     const previous=pulses.get(table);
     if(e.kind==='READ'&&previous?.kind!=='READ'&&previous?.until>Date.now())continue;
     pulses.set(table,{kind:e.status==='failed'?'failed':e.kind,at:e.updated_at,until:Date.now()+2300});
    }
    if(e.tables?.includes(state.table)&&['COMMIT','WRITE','ROLLBACK'].includes(e.kind))state.dirty=true;
   }
  });state.initialized=true;
  if(events.size>1200){const keep=new Set(orderedEvents().slice(0,1000).map(e=>e.event_id));for(const id of events.keys())if(!keep.has(id))events.delete(id);}
  if(data.history_gap)el('db-log-note').textContent='Older events expired from the bounded journal. Showing retained activity.';
  if(data.journal_error)throw Error('The activity journal is temporarily unavailable. Oracle data remains browsable.');
  if(data.events.length)renderActivity();applyPulses();return data.has_more;
 }
 async function cycle(force=false){
  clearTimeout(state.timer);if(!state.open||document.hidden)return;
  if(state.busy){if(force)state.dirty=true;return;}
  if(state.paused&&!force)return;state.busy=true;let more=false;
  try{
   if(force||!state.catalog||Date.now()-state.lastCatalog>5000)await readCatalog();
   more=await readActivity();
   if(state.tab==='data'&&el('db-detail').hidden&&(force||state.dirty||Date.now()-state.lastRows>5000))await readRows();
   el('db-error').hidden=true;
   if(state.open)indicator(state.paused?'Paused':'Live · 1 s',!state.paused);
  }catch(error){if(state.open)showError(error);}
  finally{state.busy=false;if(state.open&&!state.paused&&!document.hidden)state.timer=setTimeout(()=>cycle(),more?50:1000);}
 }
 layout();if(preferences.open)setOpen(true);
})();
