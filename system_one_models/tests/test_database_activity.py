"""Transaction instrumentation must never change the underlying DB operations."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'appbook'))
from database_activity import ActivityStore, ObservedConnection, statement_info


class Cursor:
    def __init__(self,db):self.db=db;self.rowcount=0;self.values=iter([(1,),(2,)])
    def execute(self,sql,*args,**kwargs):
        self.db.calls.append(('execute',sql));self.rowcount=0 if sql.startswith('SELECT') else 1
        if 'FAIL' in sql:raise RuntimeError('Do not log private bind values')
    executemany=execute
    def __next__(self):
        row=next(self.values);self.rowcount+=1;return row
    def fetchall(self):self.rowcount=2;return [(1,),(2,)]
    def fetchone(self):return next(self)
    def close(self):self.db.calls.append(('cursor.close',))


class Connection:
    def __init__(self):self.calls=[];self.autocommit=False
    def cursor(self):return Cursor(self)
    def commit(self):self.calls.append(('commit',))
    def rollback(self):self.calls.append(('rollback',))
    def close(self):self.calls.append(('close',))


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=ActivityStore(Path(self.temp.name)/'events.sqlite3')
        self.raw=Connection();self.db=ObservedConnection(self.raw,self.store,'experiment',lambda:{'run_id':'test'})
    def tearDown(self):self.temp.cleanup()
    def latest(self):return list({e['event_id']:e for e in self.store.changes()['events']}.values())

    def test_uncommitted_write_and_commit_share_transaction(self):
        with self.db.cursor() as cur:cur.execute('INSERT INTO s1_results VALUES (:private)',private='SECRET_BIND')
        event=self.latest()[0];self.assertEqual(event['status'],'pending_commit');self.assertEqual(event['rows'],1)
        self.db.commit();events=self.latest()
        self.assertEqual({e['transaction_id'] for e in events},{event['transaction_id']})
        self.assertEqual({e['status'] for e in events},{'committed'})
        self.assertEqual(sum(c==('commit',) for c in self.raw.calls),1)
        self.assertNotIn('SECRET_BIND',json.dumps(self.store.changes()))

    def test_oracle_integration_recognizes_connection_and_forwards_lob_handler(self):
        self.assertIsInstance(self.db, Connection)
        handler=lambda *args: None
        with self.db.cursor() as cur:
            cur.outputtypehandler=handler
            self.assertIs(cur.raw.outputtypehandler,handler)

    def test_close_does_not_introduce_explicit_rollback(self):
        self.db.cursor().execute('UPDATE s1_runs SET payload = :payload',payload='private')
        self.db.close()
        self.assertNotIn(('rollback',),self.raw.calls)
        self.assertEqual(self.raw.calls[-1],('close',))
        self.assertTrue(all(e['status']=='rolled_back' for e in self.latest()))

    def test_ddl_does_not_introduce_an_extra_commit_call(self):
        cur=self.db.cursor();cur.execute('UPDATE s1_runs SET payload = :payload',payload='private')
        cur.execute('CREATE TABLE example (id NUMBER)')
        self.assertNotIn(('commit',),self.raw.calls)
        self.assertEqual(next(e for e in self.latest() if e['kind']=='WRITE')['status'],'implicit_commit')

    def test_failed_statement_is_visible_and_does_not_claim_commit(self):
        with self.assertRaises(RuntimeError):self.db.cursor().execute('INSERT INTO FAIL VALUES (:secret)',secret='SECRET')
        event=self.latest()[0];self.assertEqual(event['status'],'failed')
        self.assertNotIn('SECRET',json.dumps(self.store.changes()))

    def test_fetch_counts_and_incremental_revisions(self):
        start=self.store.changes()['cursor']
        with self.db.cursor() as cur:
            cur.execute('SELECT run_id FROM s1_runs');self.assertEqual(list(cur),[(1,),(2,)])
        changes=self.store.changes(after=start);event=self.latest()[0]
        self.assertEqual(event['rows'],2);self.assertGreaterEqual(event['duration_ms'],0)
        self.assertEqual(self.store.changes(after=changes['cursor'])['events'],[])

    def test_autocommit_and_rollback_outcomes(self):
        self.db.autocommit=True;self.db.cursor().execute('INSERT INTO s1_results VALUES (:x)',x=1)
        self.assertEqual({e['status'] for e in self.latest()},{'autocommitted'})
        self.assertNotIn(('commit',),self.raw.calls)
        self.db.autocommit=False;self.db.cursor().execute('DELETE FROM s1_runs WHERE run_id=:x',x=1)
        self.db.rollback();self.assertEqual(self.raw.calls[-1],('rollback',))

    def test_sql_redacts_literals_and_handles_merge(self):
        kind,sql,tables=statement_info("MERGE INTO s1_results USING (SELECT 'secret' FROM dual) s ON (1=0) WHEN MATCHED THEN UPDATE SET payload=:p")
        self.assertEqual(kind,'WRITE');self.assertNotIn('secret',sql);self.assertEqual(tables,['S1_RESULTS'])
        self.assertNotIn('private',statement_info("SELECT 'private--literal' FROM s1_runs")[1])


if __name__=='__main__':unittest.main()
