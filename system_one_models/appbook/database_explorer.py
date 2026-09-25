"""Read-only, paginated exploration of the connected Oracle user's own schema.

Identifiers come from Oracle metadata, values use bind parameters, and there is
no arbitrary SQL endpoint. Catalog polling is deliberately not activity-traced.
"""
import array
import base64
import json
import re
from contextlib import contextmanager
from datetime import date, datetime, timezone

from database_activity import ObservedConnection


DESCRIPTIONS = {
    'S1_DOCUMENTS': 'Source text, provenance and Voyage embedding vectors.',
    'S1_VECTORS': 'Appbook sources and Voyage vectors stored with langchain-oracledb / OracleVS.',
    'S1_RUNS': 'Experiment configuration, progress and the complete call ledger.',
    'S1_RESULTS': 'One saved measurement per run, question and method.',
}


def quoted(identifier):
    return '"'+identifier.replace('"','""')+'"'


def serializable(value):
    if hasattr(value,'read'):
        value=value.read()
    if isinstance(value,(datetime,date)):
        return value.isoformat()
    if isinstance(value,bytes):
        return {'encoding':'base64','data':base64.b64encode(value).decode()}
    if isinstance(value,array.array):
        return value.tolist()
    if isinstance(value,str) and value.lstrip().startswith(('{','[')):
        try:return json.loads(value)
        except ValueError:pass
    return value


class DatabaseExplorer:
    def __init__(self,connect,activity):
        self.connect=connect;self.activity=activity

    @contextmanager
    def connection(self):
        db=self.connect()
        try:
            with db.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
            yield db
        finally:db.close()

    def objects(self,db):
        with db.cursor() as cur:
            cur.execute("""
                SELECT table_name, 'TABLE' FROM user_tables
                WHERE nested = 'NO' AND dropped = 'NO'
                UNION ALL
                SELECT view_name, 'VIEW' FROM user_views
                ORDER BY 1
            """)
            return {name:kind for name,kind in cur}

    def describe(self,db,name):
        objects=self.objects(db)
        if name not in objects:raise ValueError('Choose a table or view from this schema')
        with db.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, nullable
                FROM user_tab_columns
                WHERE table_name = :name
                ORDER BY column_id
            """,name=name)
            columns=[{'name':n,'type':t,'nullable':v=='Y'} for n,t,v in cur]
            cur.execute("""
                SELECT cols.column_name
                FROM user_constraints cons
                JOIN user_cons_columns cols ON cols.constraint_name = cons.constraint_name
                WHERE cons.table_name = :name AND cons.constraint_type = 'P'
                ORDER BY cols.position
            """,name=name)
            pk=[row[0] for row in cur]
        for c in columns:
            c['primary_key']=c['name'] in pk
            c['sortable']=c['type'] not in {'CLOB','NCLOB','BLOB','LONG','VECTOR','XMLTYPE','JSON'}
        return {'name':name,'kind':objects[name],'columns':columns,'primary_key':pk,
                'description':DESCRIPTIONS.get(name,'Database object in the connected schema.')}

    def catalog(self):
        with self.connection() as db,db.cursor() as cur:
            cur.execute("SELECT USER, SYS_CONTEXT('USERENV','CON_NAME') FROM dual")
            schema,pdb=cur.fetchone()
            objects=[]
            for name in self.objects(db):
                item=self.describe(db,name)
                # These small teaching tables support exact counts, not optimizer estimates.
                cur.execute('SELECT COUNT(*) FROM '+quoted(name))
                item['rows']=cur.fetchone()[0];objects.append(item)
        return {'schema':schema,'pdb':pdb,'objects':objects,
            'as_of':datetime.now(timezone.utc).isoformat(),
            'scope':'Tables and views owned by the connected Oracle schema; committed rows only.'}

    def filters(self,info,search,run_id):
        terms=[];binds={};names={c['name'] for c in info['columns']}
        if search:
            if len(search)>200:raise ValueError('Search is limited to 200 characters')
            columns=[]
            for c in info['columns']:
                col=quoted(c['name'])
                if c['type'] in {'VARCHAR2','NVARCHAR2','CHAR','NCHAR'}:
                    columns.append(f'INSTR(LOWER({col}), :search) > 0')
                elif c['type'] in {'CLOB','NCLOB'}:
                    columns.append(f'DBMS_LOB.INSTR(LOWER({col}), :search) > 0')
            if not columns:raise ValueError('This object has no searchable text columns')
            terms.append('('+' OR '.join(columns)+')');binds['search']=search.lower()
        if run_id:
            if not re.fullmatch('[0-9a-f]{32}',run_id):raise ValueError('Invalid run ID')
            if 'RUN_ID' in names:
                terms.append('"RUN_ID" = :run_id');binds['run_id']=run_id
            elif info['name']=='S1_DOCUMENTS':
                terms.append('SUBSTR("COLLECTION", 1, 33) = :collection_prefix')
                binds['collection_prefix']=run_id+'_'
            elif info['name']=='S1_VECTORS':
                terms.append('JSON_VALUE("METADATA", \'$.run_id\') = :run_id')
                binds['run_id']=run_id
            else:raise ValueError('This object has no experiment-run association')
        return (' WHERE '+' AND '.join(terms) if terms else ''),binds

    def table(self,name,offset=0,limit=25,search='',run_id='',sort='',direction='asc'):
        if not 0<=offset<=10000000 or not 1<=limit<=100:raise ValueError('Invalid page bounds')
        if direction not in {'asc','desc'}:raise ValueError('Invalid sort direction')
        with self.connection() as raw:
            info=self.describe(raw,name);where,binds=self.filters(info,search,run_id)
            allowed={c['name'] for c in info['columns'] if c['sortable']}
            if sort and sort not in allowed:raise ValueError('Choose a sortable column')
            keys=info['primary_key']
            order=([quoted(sort)+' '+direction.upper()+' NULLS LAST'] if sort else [])
            order += [quoted(k)+' ASC' for k in keys if k!=sort]
            if not order and info['kind']=='TABLE':order=['ROWID']
            if not order:order=[quoted(c) for c in sorted(allowed)[:3]]
            if not order:raise ValueError('This view has no sortable columns for pagination')
            expressions=[]
            for c in info['columns']:
                col=quoted(c['name'])
                expressions.append(f'DBMS_LOB.SUBSTR({col}, 240, 1)' if c['type'] in {'CLOB','NCLOB'} else col)
            use_rowid=not keys and info['kind']=='TABLE'
            if use_rowid:expressions.append('ROWIDTOCHAR(ROWID)')
            db=ObservedConnection(raw,self.activity,'explorer',lambda:{'run_id':run_id or None})
            with db.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM '+quoted(name)+where,binds)
                total=cur.fetchone()[0]
                query='SELECT '+', '.join(expressions)+' FROM '+quoted(name)+where
                query+=' ORDER BY '+', '.join(order)+' OFFSET :page_offset ROWS FETCH NEXT :page_limit ROWS ONLY'
                cur.execute(query,{**binds,'page_offset':offset,'page_limit':limit})
                rows=[]
                for values in cur:
                    cells={}
                    for c,v in zip(info['columns'],values):
                        if isinstance(v,array.array):
                            cells[c['name']]={'preview':f'{len(v):,} dimensions · '+str(list(v[:4])),
                                'truncated':True,'kind':'vector'}
                        else:
                            v=serializable(v)
                            clipped=isinstance(v,str) and len(v)>240 and c['name'] not in keys
                            cells[c['name']]={'preview':v[:240] if clipped else v,
                                'truncated':clipped or (c['type'] in {'CLOB','NCLOB'} and isinstance(v,str) and len(v)>=240),
                                'kind':c['type'].lower()}
                    key={k:values[[c['name'] for c in info['columns']].index(k)] for k in keys}
                    key={k:v.hex() if isinstance(v,bytes) else serializable(v) for k,v in key.items()}
                    if use_rowid:key={'__rowid__':values[-1]}
                    rows.append({'key':key or None,'cells':cells})
        return {**info,'rows':rows,'total':total,'offset':offset,'limit':limit,
            'has_more':offset+len(rows)<total,'search':search,'run_id':run_id,
            'as_of':datetime.now(timezone.utc).isoformat(),
            'note':'Text and vector previews are shortened. Open a record to inspect its full value.'}

    def row(self,name,key):
        if not isinstance(key,dict) or not key:raise ValueError('Choose a record key')
        with self.connection() as raw:
            info=self.describe(raw,name)
            expected=set(info['primary_key']) or ({'__rowid__'} if info['kind']=='TABLE' else set())
            if not expected or set(key)!=expected:raise ValueError('Invalid record key')
            if any(not isinstance(v,(str,int,float)) or len(str(v))>1000 for v in key.values()):
                raise ValueError('Invalid key value')
            terms=[];binds={}
            for i,(col,val) in enumerate(key.items()):
                name_sql='ROWID' if col=='__rowid__' else quoted(col)
                if any(c['name']==col and c['type']=='RAW' for c in info['columns']):
                    val=bytes.fromhex(val)
                terms.append(name_sql+f' = :key_{i}');binds[f'key_{i}']=val
            db=ObservedConnection(raw,self.activity,'explorer')
            with db.cursor() as cur:
                cur.execute('SELECT '+', '.join(quoted(c['name']) for c in info['columns'])+
                            ' FROM '+quoted(name)+' WHERE '+' AND '.join(terms),binds)
                values=cur.fetchone()
                record=None if values is None else {c['name']:serializable(v) for c,v in zip(info['columns'],values)}
        return {'table':name,'key':key,'record':record,'as_of':datetime.now(timezone.utc).isoformat()}
