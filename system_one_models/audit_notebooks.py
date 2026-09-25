"""Independent checks of the executed notebooks, Oracle records and cost arithmetic."""
import ast
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path

import nbformat
from dotenv import load_dotenv
from lab_core import new_lab, read_lob

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
EXPECTED={'reranking':42,'summary':31,'routing':32,'selection':24,'chunking':24,'readers':18}


def close(a,b):
    assert math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-11),(a,b)


def billed(call,prices):
    if call['provider']=='local':return Decimal(0)
    usage=call['usage']
    if call['provider']=='voyage':assert usage['total_tokens']==call['input_tokens']
    elif call['provider']=='anthropic':
        assert usage['input_tokens']+usage.get('cache_read_input_tokens',0)==call['input_tokens']
    else:assert usage['input_tokens']==call['input_tokens']
    rate=prices[call['model']]
    reads=call.get('cached_tokens',0);writes=call.get('cache_write_tokens',0)
    regular=call['input_tokens']-reads-writes
    assert min(regular,reads,writes,call['output_tokens'])>=0
    return (Decimal(regular)*Decimal(str(rate['input']))+Decimal(reads)*Decimal(str(rate['cached']))+
        Decimal(writes)*Decimal(str(rate.get('write',0)))+
        Decimal(call['output_tokens'])*Decimal(str(rate['output'])))/Decimal(1_000_000)


def check_ranks(rows):
    for row in rows:
        chosen=row['selected_ids'];gold=row['gold'];positive={k for k,v in gold.items() if v>0}
        assert len(chosen)==len(set(chosen))==3
        assert set(chosen)<=set(row['candidate_ids'])
        hits=sum(i in positive for i in chosen)
        close(row['precision'],hits/3);close(row['recall'],hits/len(positive))
        close(row['mrr'],next((1/r for r,i in enumerate(chosen,1) if i in positive),0))
        observed=sum((2**gold.get(i,0)-1)/math.log2(rank+1) for rank,i in enumerate(chosen,1))
        ideal=sum((2**v-1)/math.log2(rank+1) for rank,v in enumerate(sorted(gold.values(),reverse=True)[:3],1))
        close(row['ndcg'],observed/ideal)
    for case in {r['case_id'] for r in rows}:
        assert len({r['candidates_hash'] for r in rows if r['case_id']==case})==1


def check_summary(data):
    rows=data['results'];dev=[r for r in rows if r.get('split')=='dev' and r['arm']=='jev']
    test=[r for r in rows if r.get('split')=='test']
    assert len(dev)==4 and len(test)==18
    assert not {r['source'] for r in dev}&{r['source'] for r in test}
    candidates=[(sum(5*(r['score']>=t and not r['good'])+(r['score']<t and r['good']) for r in dev),t)
                for t in [.5,.65,.8,.9,.95]]
    threshold=min(candidates)[1];close(threshold,data['gate_threshold'])
    for row in test:
        if row['arm']=='jev':assert row['accepted']==(row['score']>=threshold)
    assert len([r for r in rows if r['case_id']=='live-summary'])==1


def run():
    report={'status':'passed','notebooks':{},'oracle':{}}
    db=new_lab('notebook-audit')
    for file in sorted(ROOT.glob('0*.ipynb')):
        nb=nbformat.read(file,as_version=4);run_id=None;executed=0;output_count=0;code_text=[]
        for cell in nb.cells:
            if cell.cell_type!='code':continue
            assert len(cell.source.splitlines())<=25
            code_text.append(cell.source)
            if 'install' not in cell.metadata.get('tags',[]):
                assert cell.execution_count is not None,(file.name,cell.source[:80])
                executed+=1
            for out in cell.get('outputs',[]):
                assert out.output_type!='error',(file.name,out)
                output_count+=1
                if 'lab = new_lab(' in cell.source and out.output_type=='stream':
                    run_id=ast.literal_eval(out.text.strip())['run_id']
        assert output_count>0
        report['notebooks'][file.name]={'executed_cells':executed,'output_blocks':output_count,
            'code_sha256':hashlib.sha256('\n'.join(code_text).encode()).hexdigest(),'run_id':run_id}
        if not run_id:continue
        with db['db'].cursor() as cur:
            cur.execute('SELECT lab, payload FROM s1_runs WHERE run_id=:1',[run_id])
            name,raw=cur.fetchone();data=json.loads(read_lob(raw))
        assert data['status']=='completed' and data['protocol_version'] in {2,3}
        rows=data['results'];assert len(rows)==EXPECTED[name]
        assert len({(r['case_id'],r['arm']) for r in rows})==len(rows)
        costs=[]
        for call in data['calls']:
            assert call['status']=='completed' and call['seconds']>=0
            expected=billed(call,data['prices']);close(expected,call['cost_usd']);costs.append(expected)
        if name=='reranking':check_ranks(rows)
        if name=='summary':check_summary(data)
        if name in {'reranking','selection','readers'}:
            assert all(c.get('arm') is None for c in data['calls'] if c['lane'].startswith('embedding'))
        for row in rows:
            if row['case_id']=='live-summary':continue
            calls=[c for c in data['calls'] if c['arm']==row['arm'] and c['case_id']==row['case_id']]
            if name=='reranking':calls=[c for c in calls if c['lane']=='reranker']
            if name=='chunking':calls=[c for c in calls if c['lane'] in {'embedding_query','reader'}]
            field='rerank_cost_usd' if name=='reranking' else 'cost_usd'
            close(row[field],sum(c['cost_usd'] for c in calls))
        report['oracle'][name]={'id':run_id,'rows':len(rows),'calls':len(costs),
            'cost_usd':float(sum(costs)),'usage_and_cost_verified':True}
    db['db'].close()
    assert len(report['notebooks'])==7 and len(report['oracle'])==6
    target=ROOT/'artifacts/validated/notebook-audit.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':run()
