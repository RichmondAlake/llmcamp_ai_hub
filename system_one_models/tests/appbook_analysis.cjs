const assert=require('node:assert/strict');
const A=require('../appbook/analysis.js');
const run={expected_arms:['jev'],results:[
 {case_id:'s0',arm:'jev',split:'dev',good:false,accepted:true,seconds:99,cost_usd:99},
 {case_id:'s1',arm:'jev',split:'test',good:true,accepted:false,seconds:1,cost_usd:.1},
 {case_id:'s2',arm:'jev',split:'test',good:false,accepted:false,seconds:3,cost_usd:.3},
 {case_id:'live-summary',arm:'jev',accepted:true,seconds:99,cost_usd:99}]};
let g=A.aggregate(run,'summary')[0];
assert.equal(g.n,2);assert.equal(g.gate_correct,.5);assert.equal(g.bad_acceptance,0);
assert.equal(g.good_rejection,1);assert.equal(g.coverage,0);assert.equal(g.accepted_defect_rate,null);
assert.equal(g.seconds,2);assert.equal(g.p50,2);assert.equal(g.p95,2.9);assert.equal(g.cost,.2);
run.results[1].cost_usd=null;assert.equal(A.aggregate(run,'summary')[0].cost,null);
run.results[1].accepted=null;assert.equal(A.aggregate(run,'summary')[0].n,1);
const ranked=[{label:'a',cost:null},{label:'b',cost:.01},{label:'c',cost:.1}];
assert.deepEqual(A.sort(ranked,'cost',true).map(x=>x.label),['b','c','a']);
assert.deepEqual(A.sort(ranked,'cost',false).map(x=>x.label),['c','b','a']);
assert.equal(A.total([{cost_usd:0},{cost_usd:null}]),null);
const selection={results:[{arm:'catalog_jev',case_id:'t1',kind:'tool',correct:true,precision:null,recall:null,cost_usd:0,seconds:0},
 {arm:'catalog_jev',case_id:'k1',kind:'skill',correct:false,precision:0,recall:0,cost_usd:.1,seconds:1}]};
g=A.aggregate(selection,'selection','tool').find(g=>g.arm==='catalog_jev');
assert.equal(g.correct,1);assert.equal(g.precision,null);assert.equal(g.denominators.precision,0);
assert.equal(A.aggregate({results:[]},'reranking')[0].quality,null);
console.log('PASS: denominators, development/live exclusions, pending rows, unknown cost, percentiles, sorting, tools/skills filters');
