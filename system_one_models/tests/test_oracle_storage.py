"""Optional Docker-Oracle contract test; fixed local vectors make no provider calls."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'appbook'))
import lab_core as core
from database_activity import ActivityStore, ObservedConnection
from database_explorer import DatabaseExplorer
from oracle_storage import OracleStorage


@unittest.skipUnless(os.getenv('RUN_ORACLE_INTEGRATION') == '1', 'Requires local Oracle')
class OracleStorageTests(unittest.TestCase):
    def test_storage_matches_sql_and_remains_inspectable(self):
        core.load_dotenv(ROOT / '.env')
        lab = core.new_lab('storage_contract')
        core.create_tables(lab)
        raw = lab['db']
        collection = lab['run_id'] + '_contract'
        documents = [
            {'id': 'b', 'text': 'Same source — 東京.', 'subject': 'Mina'},
            {'id': 'a', 'text': 'Same source — 東京.', 'subject': 'Mina'},
            {'id': 'c', 'text': 'Unrelated.', 'subject': 'Someone else'},
        ]

        def fixed_vectors(lab, texts, input_type='document'):
            return [([0., 1.] if t == 'Unrelated.' else [1., 0.]) + [0.] * 1022 for t in texts]

        with tempfile.TemporaryDirectory() as folder:
            activity = ActivityStore(Path(folder) / 'activity.sqlite3')
            lab['db'] = ObservedConnection(raw, activity, 'experiment',
                                          lambda: {'run_id': lab['run_id']})
            try:
                with patch('lab_core.embed', fixed_vectors), patch('oracle_storage.embed', fixed_vectors):
                    core.store_documents(lab, collection, documents)
                    expected, _ = core.retrieve(lab, collection, 'query', 2)
                    lab['storage'] = OracleStorage(lab)
                    core.store_documents(lab, collection, documents)
                    actual, _ = core.retrieve(lab, collection, 'query', 2)
                    self.assertEqual(actual, expected)
                    self.assertEqual([r['id'] for r in actual], ['a', 'b'])
                    self.assertEqual(core.retrieve(lab, collection + '_absent', 'query')[0], [])
                    self.assertEqual(lab['calls'], [])
                explorer = DatabaseExplorer(lambda: core.new_lab('explorer_contract')['db'], activity)
                page = explorer.table('S1_VECTORS', run_id=lab['run_id'])
                self.assertEqual(page['total'], 3)
                row = explorer.row('S1_VECTORS', page['rows'][0]['key'])
                self.assertEqual(row['record']['METADATA']['run_id'], lab['run_id'])
                events = activity.changes()['events']
                self.assertTrue(any('S1_VECTORS' in e['tables'] and e['kind'] == 'WRITE'
                                    and e['status'] == 'committed' for e in events))
                self.assertTrue(any('S1_VECTORS' in e['tables'] and e['kind'] == 'READ' for e in events))
            finally:
                with raw.cursor() as cur:
                    cur.execute('DELETE FROM s1_documents WHERE collection = :1', [collection])
                    cur.execute("DELETE FROM s1_vectors WHERE JSON_VALUE(metadata, '$.collection') = :1", [collection])
                raw.commit()
                lab['db'].close()


if __name__ == '__main__':
    unittest.main()
