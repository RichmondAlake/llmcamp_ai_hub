/* Pure arithmetic shared by the browser and offline checks. */
(function(root){
 const finite=v=>typeof v==='number'&&Number.isFinite(v);
 const numeric=v=>typeof v==='boolean'?Number(v):v;
 const mean=xs=>xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;
 const validMean=xs=>mean(xs.map(numeric).filter(finite));
 const completeMean=xs=>xs.length&&xs.every(finite)?mean(xs):null;
 const ratio=(count,total)=>total?count/total:null;
 const total=calls=>calls.every(c=>finite(c.cost_usd))?calls.reduce((s,c)=>s+c.cost_usd,0):null;
 function quantile(xs,p){
   if(!xs.length||!xs.every(finite))return null;
   const a=[...xs].sort((x,y)=>x-y),i=(a.length-1)*p,j=Math.floor(i);
   return a[j]+(a[Math.ceil(i)]-a[j])*(i-j);
 }
 const titles={original:'Original order',voyage:'Voyage reranker',llm:'OpenAI',open_source:'Local MiniLM',
   jev_noul:'Jev · Noul',jev_score:'Jev · Score',jev_choice:'Jev · Choice',jev:'Jev',no_gate:'Accept all',
   always:'Always search',never:'Never search',jev_before:'Jev before search',jev_after:'Jev after search',
   embedding_top1:'Embedding top-1',embedding_jev:'Shortlist + Jev',catalog_jev:'Full catalog + Jev',
   fixed:'Fixed windows',structure:'Sentence packing',embedding:'Embedding boundaries'};
 const armOrder={reranking:['original','voyage','llm','open_source','jev_noul','jev_score','jev_choice'],
   summary:['no_gate','jev','llm'],routing:['always','never','jev_before','jev_after'],
   selection:['embedding_top1','embedding_jev','catalog_jev'],chunking:['fixed','structure','embedding','jev']};
 const scopes={
   reranking:'Reranker only. Shared embedding/search and the downstream reader are excluded here; they remain in the total run cost.',
   summary:'Verifier only, on test examples. Development calibration, source archiving and the unlabeled live-summary demonstration remain in total run cost.',
   routing:'Complete query path: routing, any query embedding and Oracle search, and the OpenAI reader. One-time source ingestion is excluded.',
   selection:'Selector only. Shared query embedding and Oracle retrieval are excluded. Full-catalog Jev does not need retrieval at inference; compare full paths separately before deployment.',
   chunking:'Query path: embedding, Oracle retrieval, context packing and OpenAI reader. Chunk construction and indexing are separate one-time costs.',
   readers:'Reader only. Each model receives the same five memories. Shared embedding and Oracle retrieval are excluded.',
 };
 const def=(key,label,help,direction='higher',format='score')=>({key,label,help,direction,format});
 const common={
  n:def('n','Cases','Number of completed, eligible case–method rows in this table. Summary calibration and the unlabeled demonstration are excluded.','none','integer'),
  seconds:def('seconds','Mean latency','Arithmetic mean of client-observed seconds in the stated measurement scope. Protocol v2 excludes ledger writes. Network time is included.','lower','seconds'),
  p50:def('p50','p50 latency','Median case latency, using linear interpolation. Half the observed cases were no slower than this value.','lower','seconds'),
  p95:def('p95','p95 latency','95th percentile of case latency, using linear interpolation. Very unstable with a handful of examples; not a production service-level estimate.','lower','seconds'),
  cost:def('cost','Mean API cost','Mean USD per eligible case in the stated scope. Provider token usage × recorded list prices. Any missing cost makes the mean unknown. Credits and local compute are excluded.','lower','usd'),
 };
 const catalog={
  reranking:[
   def('ndcg','nDCG@3','Graded ranking quality: Σ(2^grade−1)/log₂(rank+1), divided by the ideal top-three gain across all gold memories. Grades 1/2/3 are background/partial/direct evidence; 1 is ideal.'),
   def('precision','Precision@3','Labeled relevant memories in the first three slots ÷ 3. Any grade > 0 counts. Empty slots count against precision; one relevant document gives a maximum of 1/3.'),
   def('recall','Recall@3','Distinct labeled relevant memories found in the first three ÷ all labeled relevant memories, including those missing from the candidate pool. This is fractional recall, not Hit@3.'),
   def('mrr','MRR@3','Mean reciprocal rank of the first relevant result within the first three. Rank 1 → 1; rank 2 → 1/2; rank 3 → 1/3; no hit → 0. It does not measure complete evidence coverage.'),
   def('candidate_recall','Candidate recall','Fraction of all labeled relevant memories present in the frozen 20-candidate pool, before reranking. A reranker cannot recover an absent memory.'),
  ],
  summary:[
   def('gate_correct','Correct decisions','(Accepted good summaries + rejected bad summaries) ÷ labeled test summaries. Uses a threshold fixed on development data; not a calibrated confidence.'),
   def('bad_acceptance','Bad accepted','Bad summaries accepted ÷ all bad test summaries. Lower is better. Rejecting everything also scores zero here, so inspect coverage and good rejections.','lower'),
   def('good_rejection','Good rejected','Good summaries rejected ÷ all good test summaries. Lower is better. This is the useful-memory loss caused by the gate.','lower'),
   def('accepted_defect_rate','Accepted defects','Bad summaries accepted ÷ all accepted test summaries. Undefined if the gate accepts nothing.','lower'),
   def('coverage','Coverage','Accepted test summaries ÷ all test summaries. Automatic throughput; higher alone does not mean better quality.','none'),
  ],
  routing:[
   def('route_correct','Route agreement','Used-memory decisions matching authored expected-use labels ÷ cases. Agreement does not prove a causal improvement in answers.'),
   def('searched','Search rate','Cases that actually searched Oracle ÷ cases. A post-search rejection still counts as a search.','none'),
   def('used_memory','Injection rate','Cases that supplied memory evidence to the reader ÷ cases.','none'),
   def('answer_check','Lexical check','Answers containing every required keyword ÷ cases with an answer. An incorrect answer can pass; human supported-correctness review is still required.','none'),
  ],
  selection:[
   def('correct','Exact selection','Selected ID set exactly equals the expected set ÷ cases. Includes correct abstention when no item is applicable.'),
   def('false_activation','Wrong activation','Cases selecting at least one non-gold capability ÷ cases. This includes selecting a tool or skill when none applies.','lower'),
   def('precision','Selection precision','Per-case correct selected IDs ÷ selected IDs, averaged only over cases with a selection. Abstentions have undefined precision; inspect exact selection too.'),
   def('recall','Selection recall','Per-case correct selected IDs ÷ expected IDs, averaged only over cases with an expected capability. No-match cases are excluded from this denominator.'),
   def('candidate_recall','Candidate recall','Expected IDs in the inspected pool ÷ expected IDs, averaged only over positive cases. Full-catalog and shortlist arms have different pools.'),
  ],
  chunking:[
   def('recall','Source-word recall','Unique gold source-word positions recovered ÷ all positions in the labeled excerpt. Retrieval uses at most 70 whitespace-delimited words; this is not tokenizer-token recall.'),
   def('precision','Source-word precision','Unique retrieved word positions inside the gold excerpt ÷ all unique retrieved source-word positions. Useful but unlabeled alternative passages count as non-gold.'),
   def('iou','Source-word IoU','Intersection of gold and retrieved source-word positions ÷ their union. Duplicate overlap is counted once.'),
   def('retrieved_words','Context words','Mean words passed to the reader under the 70-word budget. Whole chunks that do not fit are skipped.','none','number'),
  ],
  readers:[def('answer_check','Lexical check','Answers containing every required keyword ÷ answers. “Not Bath” can pass the Bath check. This is a diagnostic, not factual answer accuracy.','none')],
 };
 function primary(lab){return catalog[lab][0];}
 function metrics(lab){return [common.n,...catalog[lab],common.seconds,common.p50,common.p95,common.cost];}
 function rowValue(row,key){return key==='gate_correct'?(typeof row.accepted==='boolean'?Number(row.accepted===row.good):null):numeric(row[key]);}
 function aggregate(data,lab,kind='all'){
   const rows=(data.results||[]).filter(r=>r.case_id!=='live-summary'&&
     (lab!=='summary'||(r.split==='test'&&typeof r.accepted==='boolean'))&&
     (lab!=='selection'||kind==='all'||r.kind===kind));
   const arms=[...new Set([...(data.expected_arms||armOrder[lab]||data.reader_models||[]),...rows.map(r=>r.arm)])];
   return arms.map(arm=>{
     const found=rows.filter(r=>r.arm===arm),g={arm,label:titles[arm]||arm,rows:found,n:found.length,denominators:{}};
     for(const m of catalog[lab]){
       const values=found.map(r=>rowValue(r,m.key)).filter(finite);
       g[m.key]=mean(values);g.denominators[m.key]=values.length;
     }
     if(lab==='summary'){
       const bad=found.filter(r=>!r.good),good=found.filter(r=>r.good),accepted=found.filter(r=>r.accepted);
       g.bad_acceptance=ratio(bad.filter(r=>r.accepted).length,bad.length);
       g.good_rejection=ratio(good.filter(r=>!r.accepted).length,good.length);
       g.accepted_defect_rate=ratio(accepted.filter(r=>!r.good).length,accepted.length);
       g.coverage=ratio(accepted.length,found.length);
       Object.assign(g.denominators,{bad_acceptance:bad.length,good_rejection:good.length,accepted_defect_rate:accepted.length,coverage:found.length});
     }
     const times=found.map(r=>lab==='reranking'?r.rerank_seconds:r.seconds);
     g.seconds=completeMean(times);g.p50=quantile(times,.5);g.p95=quantile(times,.95);
     g.cost=completeMean(found.map(r=>lab==='reranking'?r.rerank_cost_usd:r.cost_usd));
     g.quality=g[primary(lab).key];return g;
   });
 }
 function sort(groups,key,ascending=true){
   return [...groups].sort((a,b)=>{
     const x=a[key],y=b[key];if(x==null)return y==null?0:1;if(y==null)return -1;
     return (typeof x==='string'?x.localeCompare(y):x-y)*(ascending?1:-1);
   });
 }
 function model(arm,data){
   const m=data.models||{};
   if(arm==='voyage')return m.rerank||'See call ledger';
   if(arm==='llm')return m.openai||'See call ledger';
   if(arm.startsWith('jev')||arm.endsWith('_jev'))return m.jev||'See call ledger';
   if(arm==='open_source')return 'ms-marco-MiniLM-L-6-v2 · CPU';
   if(['original','embedding_top1','embedding'].includes(arm))return m.voyage||'See call ledger';
   return arm.startsWith('gpt-')||arm.startsWith('claude-')?'Reader model':'Python policy';
 }
 root.LabAnalysis={aggregate,sort,metrics,catalog,primary,scopes,titles,model,rowValue,mean:validMean,total,quantile};
 if(typeof module!=='undefined')module.exports=root.LabAnalysis;
})(globalThis);
