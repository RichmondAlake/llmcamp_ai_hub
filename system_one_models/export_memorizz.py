"""Export the latest completed Oracle reranking run for real Memorizz replication."""
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
from lab_core import new_lab, read_lob

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT/'datasets/questions.json').read_text(encoding='utf-8'))


def export():
    load_dotenv(ROOT/'.env')
    lab = new_lab('export')
    source = None
    with lab['db'].cursor() as cur:
        cur.execute("SELECT run_id, payload FROM s1_runs WHERE lab='reranking' ORDER BY created_at DESC")
        for rid,payload in cur:
            candidate = json.loads(read_lob(payload))
            if candidate['status']=='completed' and candidate.get('candidate_snapshots'):
                source,run_id = candidate,rid
                break
    lab['db'].close()
    if source is None:
        raise ValueError('Run notebook 01 successfully before exporting candidates.')
    cases = []
    for cid,question,gold,keywords in QUESTIONS:
        rows = source['candidate_snapshots'].get(cid)
        if rows:
            cases.append({'case_id':cid,'question':question,'gold':gold,
                'required_keywords':keywords,'candidates':[
                    {'source_id':d['id'],'content':d['text'],'metadata':d['metadata'],
                     '_retrieval':{'cosine_distance':d['distance'],'initial_rank':i+1}}
                    for i,d in enumerate(rows)]})
    encoded=json.dumps(cases,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
    output={'format':'system-one-oracle-v1','cases':cases,
        'fingerprint':hashlib.sha256(encoded).hexdigest(),
        'provenance':{'oracle_run_id':run_id,'database':'Docker Oracle AI Database 26ai',
            'embedding_model':source['models']['voyage'],'dimension':1024,
            'retrieval':'Exact Oracle VECTOR_DISTANCE cosine; stable source ID tie-break',
            'source_kind':'authored synthetic teaching corpus',
            'original_embedding_calls':[c for c in source['calls'] if c['lane'].startswith('embedding')],
            'notebook':'01_reranking.ipynb','exported_from':'Oracle s1_runs'}}
    destination=ROOT/'artifacts'/'memorizz'
    destination.mkdir(parents=True,exist_ok=True)
    snapshot=destination/'oracle_candidates.json'
    snapshot.write_text(json.dumps(output,indent=2,ensure_ascii=False))
    reader={'provider':'openai','model':'gpt-6-luna',
        'options':{'max_completion_tokens':1200,'reasoning_effort':'none'}}
    rerankers=[{'provider':'none','label':'Original Oracle order'},
        {'provider':'voyage','model':'rerank-2.5','label':'Voyage dedicated reranker'},
        {'provider':'llm','llm_provider':'openai','model':'gpt-6-luna','label':'GPT-6 Luna reranker',
         'options':{'max_completion_tokens':1200,'reasoning_effort':'none'}},
        {'provider':'cross_encoder','model':'cross-encoder/ms-marco-MiniLM-L-6-v2','label':'Open-source MiniLM'}]
    rerankers += [{'provider':'jev','model':'jev-1.13.0','jev_method':method,
                  'label':'Jev '+method.title()} for method in ['noul','score','choice']]
    config={'name':'System One lesson · Oracle / Voyage · 7 reranking methods',
        'experiment_type':'reranker','dataset':'custom','data_path':str(snapshot),
        'candidate_snapshot_path':str(snapshot),'embedding_model':'voyage-4',
        'limit':len(cases),'readers':[reader],'rerankers':rerankers,'judge':reader,
        'top_k':3,'candidate_pool_size':20,'max_cost_usd':5,'max_seconds':1800}
    (destination/'reranking_config.json').write_text(json.dumps(config,indent=2))
    print(f'Exported {len(cases)} frozen Oracle pools to {snapshot}')
    return config


if __name__=='__main__':
    export()
