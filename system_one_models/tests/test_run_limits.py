"""Regression checks for dataset-sized runs; provider and Oracle writes are mocked."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'appbook'), str(ROOT)]
import server
import lab_experiments as experiments


class RunLimitTests(unittest.TestCase):
    def test_capacity_matches_actual_labeled_data(self):
        for lesson in server.LABS.values():
            cases = json.loads((ROOT/'datasets'/f"{lesson['case_dataset']}.json").read_text())
            self.assertEqual(lesson['max_cases'], len(cases))
            self.assertLessEqual(lesson['min_cases'], lesson['default_cases'])
            self.assertLessEqual(lesson['default_cases'], lesson['max_cases'])
        self.assertEqual(server.LABS['reranking']['default_cases'], 6)
        self.assertEqual(server.LABS['reranking']['max_cases'], 40)
        questions = experiments.QUESTIONS
        self.assertEqual(len({q[0] for q in questions}), 40)
        self.assertEqual(len({q[1].casefold() for q in questions}), 40)
        source_ids = {row[0] for row in experiments.DOCUMENTS}
        for _, query, gold, keywords in questions:
            self.assertTrue(query and gold and keywords)
            self.assertLessEqual(set(gold), source_ids)
            self.assertTrue(all(type(grade) is int and 1<=grade<=3 for grade in gold.values()))

    @patch.dict(os.environ, {'S1_MAX_CALLS':'1000'})
    def test_accepts_whole_counts_and_rejects_outside_the_dataset(self):
        for count in [1, 6, 26, 40]:
            self.assertEqual(server.validate_case_limit('reranking', count), count)
        for count in [0, 41, -1, 2.5, True, '40', None]:
            with self.assertRaisesRegex(ValueError, 'whole number from 1 to 40'):
                server.validate_case_limit('reranking', count)
        with self.assertRaisesRegex(ValueError, 'from 6 to 10'):
            server.validate_case_limit('summary', 5)

    def test_request_cap_is_checked_before_a_paid_run_starts(self):
        with patch.dict(os.environ, {'S1_MAX_CALLS':'300'}):
            self.assertEqual(server.validate_case_limit('reranking', 6), 6)
            with self.assertRaisesRegex(ValueError, '561 recorded calls'):
                server.validate_case_limit('reranking', 40)
        with patch.dict(os.environ, {'S1_MAX_CALLS':'561'}):
            self.assertEqual(server.validate_case_limit('reranking', 40), 40)

    @patch.dict(os.environ, {'S1_MAX_CALLS':'1000'})
    def test_http_handler_passes_40_to_worker_and_records_280_expected_rows(self):
        handler = server.Handler.__new__(server.Handler)
        body = json.dumps({'lab':'reranking', 'limit':40}).encode()
        handler.path = '/api/run'
        handler.headers = {'Content-Length':str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.send = Mock()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server, 'ROOT', Path(directory)), \
             patch.object(server, 'WORKERS', {}), \
             patch.object(server, 'new_lab', return_value={'db':Mock()}), \
             patch.object(server, 'save_run') as saved, \
             patch.object(server.subprocess, 'Popen') as spawn:
            handler.do_POST()
        self.assertEqual(handler.send.call_args.args[1], 202)
        args = spawn.call_args.args[0]
        self.assertEqual(args[args.index('--limit')+1], '40')
        self.assertEqual(saved.call_args.kwargs['expected_results'], 280)
        self.assertEqual(saved.call_args.kwargs['expected_scored_cases'], 40)

    def test_reranking_visits_all_40_cases_and_all_seven_methods(self):
        lab = {'run_id':'test', 'results':[]}
        candidates = experiments.memory_documents()[:20]
        with patch.object(experiments, 'store_documents'), \
             patch.object(experiments, 'load_open_reranker', return_value={'load_seconds':0}), \
             patch.object(experiments, 'retrieve', return_value=(candidates, 0)) as retrieve, \
             patch.object(experiments, 'save_run'), \
             patch.object(experiments, 'run_rank_case') as rank:
            experiments.run_reranking(lab, limit=40)
        self.assertEqual(retrieve.call_count, 40)
        pairs = [(c.args[1][0], c.args[3]) for c in rank.call_args_list]
        self.assertEqual(len(pairs), 280)
        self.assertEqual(len(set(pairs)), 280)
        self.assertEqual({case for case, _ in pairs}, {q[0] for q in experiments.QUESTIONS})
        self.assertTrue(all(c.args[2] is candidates for c in rank.call_args_list))


if __name__ == '__main__':
    unittest.main()
