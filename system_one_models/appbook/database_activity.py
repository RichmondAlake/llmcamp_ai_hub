"""Observe appbook SQL and transaction boundaries without changing Oracle data.

The bounded journal is local SQLite, shared by the HTTP server and worker processes.
It is application instrumentation, not Oracle auditing or a redo-log reader. Bind
values, source text, credentials and result contents are never written to the journal.
"""
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class ActivityStore:
    def __init__(self, path, retention=12000):
        self.path=Path(path);self.retention=retention;self.error=None
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS activity (sequence INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'event_id TEXT NOT NULL, payload TEXT NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=2)
        try:
            with db:
                yield db
        finally:
            db.close()

    def publish(self, event):
        event={**event,'updated_at':datetime.now(timezone.utc).isoformat()}
        try:
            with self.connect() as db:
                cur=db.execute('INSERT INTO activity(event_id,payload) VALUES (?,?)',
                               [event['event_id'],json.dumps(event,allow_nan=False)])
                sequence=cur.lastrowid
                if sequence%100==0:
                    db.execute('DELETE FROM activity WHERE sequence <= ?',[sequence-self.retention])
            self.error=None
        except (sqlite3.Error,OSError,ValueError) as exc:
            # Observability must not turn a successfully committed write into a failed experiment.
            self.error=type(exc).__name__

    def changes(self, after=0, limit=500):
        with self.connect() as db:
            first,last=db.execute('SELECT MIN(sequence),MAX(sequence) FROM activity').fetchone()
            if after==0:
                rows=db.execute('SELECT sequence,payload FROM activity ORDER BY sequence DESC LIMIT ?',
                                [limit]).fetchall()[::-1]
            else:
                rows=db.execute('SELECT sequence,payload FROM activity WHERE sequence>? '
                                'ORDER BY sequence LIMIT ?',[after,limit]).fetchall()
        events=[{**json.loads(raw),'sequence':seq} for seq,raw in rows]
        return {'events':events,'cursor':rows[-1][0] if rows else after,
            'has_more':bool(rows and last>rows[-1][0]),
            'history_gap':bool(after and first and after<first-1),
            'retained_from':first,'journal_error':self.error,
            'scope':'Appbook and experiment-worker SQL; other database clients are not traced.'}


def statement_info(sql):
    safe=re.sub(r"'(?:''|[^'])*'",'?',sql or '')
    safe=re.sub(r'/\*.*?\*/|--[^\n]*',' ',safe,flags=re.S)
    safe=' '.join(safe.split())
    first=safe.split(' ',1)[0].upper() if safe else 'UNKNOWN'
    kind=('READ' if first in {'SELECT','WITH'} else 'WRITE' if first in
          {'INSERT','UPDATE','DELETE','MERGE'} else 'DDL' if first in
          {'CREATE','ALTER','DROP','TRUNCATE'} else first)
    pattern=r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+("[^"]+"|[A-Za-z][\w$#]*)'
    tables=sorted({m.strip('"').upper() for m in re.findall(pattern,safe,re.I)
                   if m.upper() not in {'DUAL','SET'}})
    return kind,safe[:2500],tables


class ObservedConnection:
    def __init__(self, connection, store, source, context=None):
        self.raw=connection;self.store=store;self.source=source
        self.context=context or (lambda:{})
        self.connection_id=uuid.uuid4().hex[:12]
        self.transaction_id=None;self.pending=[];self.touched=set()

    def __getattr__(self,name):return getattr(self.raw,name)
    @property
    def __class__(self):return self.raw.__class__
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    @property
    def autocommit(self):return self.raw.autocommit
    @autocommit.setter
    def autocommit(self,value):self.raw.autocommit=value
    def cursor(self,*args,**kwargs):return ObservedCursor(self,self.raw.cursor(*args,**kwargs))

    def event(self,kind,sql='',tables=None):
        event={'event_id':uuid.uuid4().hex,'started_at':datetime.now(timezone.utc).isoformat(),
            'kind':kind,'sql':sql,'tables':tables or [],'source':self.source,
            'connection_id':self.connection_id,'transaction_id':self.transaction_id,
            'status':'running','rows':None,'duration_ms':0,'process_id':os.getpid(),**self.context()}
        self.store.publish(event)
        return event

    def finish_transaction(self,status):
        for event in self.pending:
            event['status']=status;self.store.publish(event)
        self.transaction_id=None;self.pending=[];self.touched=set()

    def boundary(self,method,status,description=None):
        event=self.event(method.upper(),description or method.upper(),sorted(self.touched))
        started=time.perf_counter()
        try:
            getattr(self.raw,method)()
            event['status']=status
        except Exception as exc:
            event.update(status='failed',error=type(exc).__name__)
            raise
        finally:
            event['duration_ms']=(time.perf_counter()-started)*1000
            self.store.publish(event)
        self.finish_transaction(status)

    def commit(self):self.boundary('commit','committed')
    def rollback(self):self.boundary('rollback','rolled_back')
    def close(self):
        # Oracle rolls back uncommitted changes on close. Do not introduce a new
        # rollback call: instrumentation must preserve the caller's operations.
        event=self.event('ROLLBACK','Implicit rollback on connection close',sorted(self.touched)) if self.transaction_id else None
        started=time.perf_counter()
        try:
            self.raw.close()
        except Exception as exc:
            if event:event.update(status='failed',error=type(exc).__name__)
            raise
        else:
            if event:event.update(status='rolled_back',boundary='connection_close')
        finally:
            if event:
                event['duration_ms']=(time.perf_counter()-started)*1000
                self.store.publish(event)
        if event:self.finish_transaction('rolled_back')


class ObservedCursor:
    def __init__(self,connection,cursor):
        self.connection=connection;self.raw=cursor;self.current=None
    def __getattr__(self,name):return getattr(self.raw,name)
    @property
    def outputtypehandler(self):return self.raw.outputtypehandler
    @outputtypehandler.setter
    def outputtypehandler(self,value):self.raw.outputtypehandler=value
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def __iter__(self):return self
    def __next__(self):
        started=time.perf_counter()
        done=False
        try:return next(self.raw)
        except StopIteration:
            done=True;raise
        except Exception as exc:
            self.failed(exc);done=True;raise
        finally:
            self.add_time(started)
            if done:self.flush()
    def failed(self,exc):
        if self.current:self.current.update(status='failed',error=type(exc).__name__)
    def add_time(self,started):
        if self.current:self.current['duration_ms']+=(time.perf_counter()-started)*1000
    def flush(self):
        if self.current and self.current['kind']=='READ':
            if self.current['status']!='failed':self.current['rows']=max(0,self.raw.rowcount)
            self.connection.store.publish(self.current)
    def close(self):
        self.flush();self.raw.close()

    def execute(self,sql,*args,**kwargs):return self.perform('execute',sql,*args,**kwargs)
    def executemany(self,sql,*args,**kwargs):return self.perform('executemany',sql,*args,**kwargs)
    def perform(self,method,sql,*args,**kwargs):
        self.flush();kind,safe,tables=statement_info(sql);conn=self.connection
        if kind=='WRITE' and not conn.transaction_id:conn.transaction_id=uuid.uuid4().hex[:12]
        prior_transaction=conn.transaction_id if kind=='DDL' else None
        event=conn.event(kind,safe,tables);self.current=event;started=time.perf_counter()
        try:
            getattr(self.raw,method)(sql,*args,**kwargs)
            event.update(status='pending_commit' if kind=='WRITE' else 'completed',
                         rows=max(0,self.raw.rowcount) if kind=='WRITE' else None)
            if kind=='WRITE':
                conn.pending.append(event);conn.touched.update(tables)
        except Exception as exc:
            code=getattr(exc.args[0],'code',None) if exc.args else None
            event.update(status='already_exists' if code==955 else 'failed',
                         error=f'ORA-{code:05d}' if isinstance(code,int) else type(exc).__name__)
            raise
        finally:
            self.add_time(started);conn.store.publish(event)
            if prior_transaction:
                # Oracle DDL can commit before it executes. On an arbitrary
                # failure we cannot infer whether Oracle reached that boundary.
                status='implicit_commit' if event['status'] in {'completed','already_exists'} else 'outcome_unknown'
                boundary=conn.event('COMMIT','Oracle DDL implicit boundary',sorted(conn.touched))
                boundary.update(status=status,duration_ms=None,boundary='ddl')
                conn.store.publish(boundary);conn.finish_transaction(status)
        if kind=='WRITE' and conn.raw.autocommit:
            boundary=conn.event('COMMIT','Autocommit after successful statement',sorted(conn.touched))
            boundary.update(status='autocommitted',duration_ms=None,boundary='autocommit')
            conn.store.publish(boundary);conn.finish_transaction('autocommitted')
        return self

    def fetch(self,method,*args):
        started=time.perf_counter()
        try:return getattr(self.raw,method)(*args)
        except Exception as exc:
            self.failed(exc);raise
        finally:self.add_time(started);self.flush()
    def fetchone(self):return self.fetch('fetchone')
    def fetchall(self):return self.fetch('fetchall')
    def fetchmany(self,*args):return self.fetch('fetchmany',*args)
