'use strict';
// Read-only Oracle data explorer: a drawer under every page listing the app's tables, their rows and a row inspector.
// Vectors arrive summarised (dimensions, first values, norm); the full row is shown in the inspector.
let explorerTable=null;

function recordTable(rows){
 if(!rows?.length)return '<p class="hint">No rows yet. Run a comparison or add examples to populate this table.</p>';
 const columns=Object.keys(rows[0]),cell=v=>v===null||v===undefined?'':typeof v==='object'?(v.vector?`${v.vector} · norm ${v.norm}`:JSON.stringify(v)):String(v);
 return `<table><thead><tr>${columns.map(c=>`<th>${esc(c.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(c=>`<td>${esc(cell(r[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

async function loadTables(){
 const tables=await api('/api/tables');
 $('#table-list').innerHTML=tables.map(t=>`<button class="table-button${t.name===explorerTable?' active':''}" data-table="${esc(t.name)}" title="${esc(t.description)}">${esc(t.name)}<small>${t.count}</small>${t.source==='Oracle True Cache'?'<em>via True Cache</em>':''}</button>`).join('');
 $('#table-count').textContent=`${tables.length} tables · ${tables.reduce((n,t)=>n+t.count,0)} rows`;
 document.querySelectorAll('[data-table]').forEach(b=>b.onclick=()=>loadTable(b.dataset.table).catch(e=>toast(e.message)));
 if(explorerTable)await loadTable(explorerTable);
}

async function loadTable(name){
 explorerTable=name;const data=await api('/api/tables/'+name);
 document.querySelectorAll('[data-table]').forEach(b=>b.classList.toggle('active',b.dataset.table===name));
 $('#table-head').innerHTML=`<b>${esc(name)}</b><span>${esc(data.description)} · newest ${data.limit} rows</span>`;
 $('#table-grid').innerHTML=recordTable(data.rows);
 $('#row-inspector').textContent=data.rows.length?'Select a row to inspect it.':'';
 $('#table-grid').querySelectorAll('tbody tr').forEach((tr,i)=>tr.onclick=()=>{$('#table-grid').querySelectorAll('tr.selected').forEach(r=>r.classList.remove('selected'));tr.classList.add('selected');$('#row-inspector').textContent=JSON.stringify(data.rows[i],null,2);});
}

// Called after measured comparisons and vector-space changes, so an open drawer shows the rows they wrote.
function refreshExplorer(){if(!$('#explorer-body')?.hidden)loadTables().catch(e=>toast(e.message));}

$('#explorer-toggle').onclick=async()=>{
 const body=$('#explorer-body');body.hidden=!body.hidden;$('#explorer-toggle').setAttribute('aria-expanded',String(!body.hidden));
 if(!body.hidden)try{await loadTables();}catch(e){toast(e.message);}
};
