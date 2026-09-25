"""Educational appbook: standard-library HTTP server, Oracle, plain Python labs."""
import argparse
import io
import json
import os
import subprocess
import sys
import threading
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
import oracledb
from lab_core import new_lab as raw_new_lab, read_lob, create_tables, save_run
from database_activity import ActivityStore, ObservedConnection
from database_explorer import DatabaseExplorer
from oracle_storage import OracleStorage
from lab_experiments import (
    run_reranking, run_summary, run_routing, run_selection, run_chunking,
    run_readers, reader_models,
)

load_dotenv(ROOT/'.env')
os.environ.setdefault('S1_MAX_CALLS','1000')
LABS = json.loads((ROOT/'appbook/lessons.json').read_text(encoding='utf-8'))
for lesson in LABS.values():
    dataset = ROOT/'datasets'/f"{lesson['case_dataset']}.json"
    lesson['max_cases'] = len(json.loads(dataset.read_text(encoding='utf-8')))
METHODS = {'reranking':run_reranking, 'summary':run_summary, 'routing':run_routing,
           'selection':run_selection, 'chunking':run_chunking, 'readers':run_readers}
WORKERS = {}
LOCK = threading.Lock()
ACTIVITY = ActivityStore(ROOT/'.data'/'appbook'/'database-activity.sqlite3')


def new_lab(name, run_id=None):
    lab=raw_new_lab(name,run_id)
    def context():
        return {'run_id':lab['run_id'] if name in LABS else lab.get('observed_run'),
                'lab':name if name in LABS else None,
                'case_id':lab.get('case_id') or None,'arm':lab.get('arm')}
    lab['db']=ObservedConnection(lab['db'],ACTIVITY,
                                'experiment' if name in LABS else 'appbook',context)
    return lab


def explorer_connection():
    return oracledb.connect(user=os.environ['ORACLE_USER'],
        password=os.environ['ORACLE_PASSWORD'],dsn=os.environ['ORACLE_DSN'])


EXPLORER=DatabaseExplorer(explorer_connection,ACTIVITY)


def validate_case_limit(name, value):
    lesson = LABS[name]
    if type(value) is not int or not lesson['min_cases']<=value<=lesson['max_cases']:
        raise ValueError(f"Enter a whole number from {lesson['min_cases']} to "
                         f"{lesson['max_cases']}; each case is a distinct labeled example.")
    if name=='reranking':
        # One ingest + each query's embedding, five hosted rerankers, one CPU
        # reranker and seven reader calls. The ledger also counts local inference.
        calls = 1+14*value
        cap = int(os.environ['S1_MAX_CALLS'])
        if calls>cap:
            raise ValueError(f'{value} questions need {calls} recorded calls; the configured '
                             f'limit is {cap}. Raise S1_MAX_CALLS in .env and restart the appbook, '
                             'or select fewer questions.')
    return value


def run_metadata(name, limit, models):
    arms = {'reranking':['original','voyage','llm','open_source','jev_noul','jev_score','jev_choice'],
        'summary':['no_gate','jev','llm'], 'routing':['always','never','jev_before','jev_after'],
        'selection':['embedding_top1','embedding_jev','catalog_jev'],
        'chunking':['fixed','structure','embedding','jev'], 'readers':models}[name]
    return {'case_limit':limit, 'expected_arms':arms,
        'expected_results':limit*len(arms)+(1 if name=='summary' else 0),
        'expected_scored_cases':limit-4 if name=='summary' else limit,
        'progress':{'stage':'Preparing Oracle sources and models'}}


def worker(name, run_id, limit, models):
    lab = new_lab(name, run_id)
    try:
        create_tables(lab, documents=False)
        lab['storage'] = OracleStorage(lab)
        save_run(lab,worker_pid=os.getpid(),**run_metadata(name,limit,models))
        kwargs = {'limit': limit}
        if name=='readers':
            kwargs['models'] = models
        METHODS[name](lab, **kwargs)
        save_run(lab, status='completed',active_call=None,progress={'stage':'All results saved'})
    except Exception as exc:
        # Provider errors are intentionally sanitized at the HTTP boundary.
        save_run(lab, status='failed',active_call=None,error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        lab['db'].close()


def query_runs(run_id=None):
    lab = new_lab('appbook')
    lab['observed_run']=run_id
    try:
        with lab['db'].cursor() as cur:
            if run_id:
                cur.execute('SELECT lab, payload FROM s1_runs WHERE run_id=:1', [run_id])
                row = cur.fetchone()
                if row:
                    data = {'id':run_id, 'lab':row[0], **json.loads(read_lob(row[1]))}
                    if data['status']=='running' and data.get('worker_pid'):
                        try:
                            os.kill(data['worker_pid'],0)
                        except ProcessLookupError:
                            data.update(status='interrupted',active_call=None,
                                error='The worker stopped before finishing. Saved measurements remain available.')
                    return data
                return {'id':run_id, 'status':'not_found', 'results':[], 'calls':[]}
            cur.execute('SELECT run_id, lab, created_at, payload FROM s1_runs '
                        'ORDER BY created_at DESC FETCH FIRST 100 ROWS ONLY')
            output = []
            for rid, name, created, raw in cur:
                data = json.loads(read_lob(raw))
                if name in LABS:
                    output.append({'id':rid,'lab':name,'created':created.isoformat(),
                        'status':data['status'], 'rows':len(data.get('results',[]))})
            return output
    finally:
        lab['db'].close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send(self, payload, status=200, content_type='application/json'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed=urlparse(self.path)
        path=parsed.path
        try:
            if path.startswith('/api/database/'):
                return self.database_get(path,parse_qs(parsed.query))
            if path=='/api/lessons':
                return self.send(LABS)
            if path=='/api/status':
                return self.send({'oracle':bool(os.getenv('ORACLE_DSN')),
                    'keys':{k:bool(os.getenv(k)) for k in
                        ['TYPESAFE_API_KEY','VOYAGE_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY']},
                    'models':{k:os.getenv(k) for k in
                        ['JEV_MODEL','VOYAGE_MODEL','VOYAGE_RERANK_MODEL','OPENAI_MODEL']}})
            if path=='/api/models':
                return self.send({'models':reader_models()})
            if path=='/api/runs':
                return self.send({'runs':query_runs()})
            if path.startswith('/api/runs/'):
                rid = path.rsplit('/',1)[-1]
                if len(rid)!=32 or any(c not in '0123456789abcdef' for c in rid):
                    return self.send({'error':'Invalid run ID'},400)
                result=query_runs(rid)
                return self.send(result,404 if result['status']=='not_found' else 200)
            if path.startswith('/api/notebook/'):
                name = path.rsplit('/',1)[-1]
                if name not in LABS:
                    return self.send({'error':'Unknown lesson'},404)
                return self.send((ROOT/LABS[name]['notebook']).read_bytes())
            if path.startswith('/api/notebook-package/'):
                name=path.rsplit('/',1)[-1]
                if name not in LABS:return self.send({'error':'Unknown lesson'},404)
                buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                    archive.write(ROOT/LABS[name]['notebook'],LABS[name]['notebook'])
                    for dataset in LABS[name]['data']:
                        filename='datasets/'+dataset.lower()+'.json'
                        archive.write(ROOT/filename,filename)
                    for filename in ['00_oracle_setup.ipynb','compose.yaml','.env.example','requirements.txt','bootstrap_oracle.py','README.md']:
                        archive.write(ROOT/filename,filename)
                return self.send(buffer.getvalue(),content_type='application/zip')
            static = {'/':'index.html','/app.js':'app.js','/style.css':'style.css',
                      '/analysis.js':'analysis.js','/diagrams.js':'diagrams.js',
                      '/database.js':'database.js','/database.css':'database.css'}
            if path in static:
                file = Path(__file__).parent/static[path]
                mime = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript'}
                return self.send(file.read_bytes(),content_type=mime[file.suffix])
            return self.send({'error':'Not found'},404)
        except Exception as exc:
            self.send({'error':f'{type(exc).__name__}: could not read lab data'},500)

    def database_get(self,path,params):
        def param(name,default=''):
            return params.get(name,[default])[0]
        try:
            if path=='/api/database/catalog':
                return self.send(EXPLORER.catalog())
            if path=='/api/database/activity':
                after=int(param('after','0'))
                if after<0:raise ValueError('Invalid activity cursor')
                return self.send(ACTIVITY.changes(after))
            if path.startswith('/api/database/table/'):
                return self.send(EXPLORER.table(unquote(path.rsplit('/',1)[-1]),
                    offset=int(param('offset','0')),limit=int(param('limit','25')),
                    search=param('search'),run_id=param('run'),sort=param('sort'),
                    direction=param('direction','asc')))
            if path.startswith('/api/database/row/'):
                raw=param('key')
                if len(raw)>5000:raise ValueError('Invalid record key')
                result=EXPLORER.row(unquote(path.rsplit('/',1)[-1]),json.loads(raw))
                return self.send(result,404 if result['record'] is None else 200)
            return self.send({'error':'Unknown database endpoint'},404)
        except (ValueError,TypeError,KeyError):
            return self.send({'error':'Invalid database request. Choose a schema object, valid filters and page bounds.'},400)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://'+self.headers.get('Host',''):
            return self.send({'error':'Use the local appbook origin'},403)
        if self.path!='/api/run':
            return self.send({'error':'Not found'},404)
        try:
            size = int(self.headers.get('Content-Length','0'))
            if not 0<size<5000:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            name = data['lab']
            if name not in LABS:
                raise ValueError('Unknown lesson')
            limit = validate_case_limit(name,data.get('limit',LABS[name]['default_cases']))
            models = data.get('models',[])
            if name=='readers' and (len(models)!=3 or len(set(models))!=3
                                   or not set(models)<=set(reader_models())):
                raise ValueError('Select three different account-visible model IDs')
            with LOCK:
                if any(p.poll() is None for p in WORKERS.values()):
                    return self.send({'error':'A lesson is running; wait for it to finish'},409)
                rid = uuid.uuid4().hex
                queued = new_lab(name,rid)
                try:
                    save_run(queued,status='queued',**run_metadata(name,limit,models))
                finally:
                    queued['db'].close()
                logs = ROOT/'.data'/'appbook'
                logs.mkdir(parents=True,exist_ok=True)
                with (logs/(rid+'.log')).open('w') as log:
                    WORKERS[rid] = subprocess.Popen([sys.executable,__file__,'--worker',name,
                        '--run-id',rid,'--limit',str(limit),'--models',json.dumps(models)],
                        cwd=ROOT,stdout=log,stderr=log,env=dict(os.environ))
            self.send({'id':rid,'status':'queued'},202)
        except (ValueError,KeyError,TypeError) as exc:
            self.send({'error':str(exc)},400)


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8878)
    parser.add_argument('--worker',choices=LABS)
    parser.add_argument('--run-id')
    parser.add_argument('--limit',type=int,default=6)
    parser.add_argument('--models',default='[]')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker,args.run_id,args.limit,json.loads(args.models))
    else:
        lab = new_lab('appbook'); create_tables(lab, documents=False); lab['db'].close()
        print(f'System One appbook: http://127.0.0.1:{args.port}',flush=True)
        ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
