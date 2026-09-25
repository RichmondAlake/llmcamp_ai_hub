"""Offline contract and arithmetic checks, separate from live notebook execution."""
import ast
import json
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab_core import ranking_metrics, token_cost, expected_score, ranked, probability, candidate_texts
from lab_experiments import (
    gate_metrics, select_gate_threshold, sentence_spans, pack_sentences,
    fixed_spans, span_metrics, selection_metrics, CHUNK_DOCUMENTS, CHUNK_QUERIES,
)


class ArithmeticTests(unittest.TestCase):
    def test_precision_uses_requested_slots_and_recall_uses_all_gold(self):
        result=ranking_metrics(['b'],{'a':3,'b':1},3)
        self.assertAlmostEqual(result['precision'],1/3)
        self.assertAlmostEqual(result['recall'],.5)
        self.assertEqual(result['mrr'],1)
        self.assertAlmostEqual(result['ndcg'],1/(7+1/math.log2(3)))

    def test_metrics_do_not_inflate_duplicates_or_empty_gold(self):
        with self.assertRaises(ValueError):ranking_metrics(['a','a'],{'a':3})
        self.assertTrue(all(v is None for v in ranking_metrics(['a'],{}).values()))
        self.assertEqual(ranking_metrics(['x','a'],{'a':3},1)['mrr'],0)

    def test_cached_tokens_are_not_double_billed(self):
        self.assertAlmostEqual(token_cost('gpt-6-luna',1000,100,200),.000132)
        self.assertAlmostEqual(token_cost('jev-1.13.0',1000,900),.000042)
        self.assertAlmostEqual(token_cost('rerank-2.5',1000),.00005)
        self.assertIsNone(token_cost('unknown',1000))
        self.assertIsNone(token_cost('gpt-6-luna',None))
        with self.assertRaises(ValueError):token_cost('gpt-6-luna',10,1,20)
        self.assertAlmostEqual(token_cost('gpt-6-sol',1000,100,100,200),.00292)
        self.assertIsNone(token_cost('gpt-6-sol',300_000))

    def test_score_uses_expected_level_not_confidence(self):
        answer={'probabilities':{'0':.1,'1':.2,'2':.3,'3':.4},'confidence':.99}
        self.assertAlmostEqual(expected_score(answer,4),2/3)
        answer['probabilities']['0']=.5
        with self.assertRaises(ValueError):expected_score(answer,4)

    def test_ties_preserve_order_and_metadata(self):
        source=[{'id':'a','text':'alpha','metadata':{'v':1}},{'id':'b','text':'beta'}]
        self.assertEqual([d['id'] for d in ranked(source,[.5,.5])],['a','b'])
        self.assertEqual(ranked(source,[.1,.9])[1]['metadata'],{'v':1})
        for invalid in [True,float('nan'),float('inf'),1.2,-.1]:
            with self.assertRaises(ValueError):probability(invalid)

    def test_provider_content_has_no_private_labels_or_similarity_scores(self):
        source=[{'id':'a','text':'A correction','distance':.01,
                 'metadata':{'subject':'Mina'},'gold':3,'label':'relevant'}]
        self.assertEqual(candidate_texts(source),[{'id':'a','text':'A correction'}])
        self.assertIn('distance',source[0])  # Provenance remains in the frozen pool.

    def test_reject_all_gate_is_not_reported_as_useful(self):
        result=gate_metrics([{'good':True,'accepted':False},{'good':False,'accepted':False}])
        self.assertEqual(result['bad_acceptance'],0)
        self.assertEqual(result['good_rejection'],1)
        self.assertEqual(result['coverage'],0)
        self.assertIsNone(result['accepted_defect_rate'])

    def test_gate_threshold_never_trains_on_test_rows(self):
        dev=[{'split':'dev','score':.6,'good':False},{'split':'dev','score':.9,'good':True}]
        threshold=select_gate_threshold(dev)
        changed=dev+[{'split':'test','score':.99,'good':False}]*100
        self.assertEqual(select_gate_threshold(changed),threshold)

    def test_chunking_preserves_sources_and_enforces_maximum(self):
        for _,text in CHUNK_DOCUMENTS:
            spans=sentence_spans(text)
            for chunks in [fixed_spans(text),pack_sentences(text,spans,[True]*len(spans))]:
                self.assertEqual(''.join(text[a:b] for a,b in chunks),text)
                self.assertTrue(all(len(text[a:b].split())<=70 for a,b in chunks))
        with self.assertRaises(ValueError):pack_sentences('word '*100,[(0,500)],[True])

    def test_source_overlap_is_counted_once(self):
        query=CHUNK_QUERIES[0];source=dict(CHUNK_DOCUMENTS)[query[2]]
        start=source.index(query[3]);end=start+len(query[3])
        row={'id':'x','text':query[3],'metadata':{'source_id':query[2],'start':start,'end':end}}
        result=span_metrics(query,[row,{**row,'id':'y'}])
        self.assertEqual(result['recall'],1)
        self.assertEqual(result['precision'],1)
        self.assertEqual(result['iou'],1)

    def test_no_match_catalog_requests_require_abstention(self):
        self.assertTrue(selection_metrics([],[])['correct'])
        self.assertTrue(selection_metrics(['tool'],[])['false_activation'])
        self.assertIsNone(selection_metrics([],[])['recall'])


class NotebookContractTests(unittest.TestCase):
    def test_diagrams_are_embedded_and_keys_use_getpass(self):
        for file in ROOT.glob('0[1-6]*.ipynb'):
            nb=json.loads(file.read_text())
            sources=[''.join(c['source']) for c in nb['cells']]
            parts=[s for s in sources if s.startswith('## Part ')]
            self.assertEqual(len(parts),9)
            self.assertFalse(any(s.startswith('### Build `') for s in sources))
            self.assertTrue(any('pd.DataFrame' in s for s in sources))
            self.assertTrue(any('pprint.pprint' in s for s in sources))
            self.assertNotIn('```mermaid','\n'.join(sources))
            self.assertGreaterEqual(sum(bool(c.get('attachments')) for c in nb['cells']),2)
            credentials=[c for c in nb['cells'] if 'credentials' in c.get('metadata',{}).get('tags',[])]
            self.assertEqual(len(credentials),1)
            source=''.join(credentials[0]['source'])
            self.assertIn("getpass(f'Enter {name}: ')",source)
            self.assertIn("os.getenv('S1_USE_ENV_KEYS', '0')",source)
            for cell in nb['cells']:
                for attachment in cell.get('attachments',{}).values():
                    self.assertTrue(attachment['image/png'].startswith('iVBOR'))

    def test_short_self_contained_code_and_descriptive_markdown(self):
        files=list(ROOT.glob('0*.ipynb'))
        self.assertEqual(len(files),7)
        for file in files:
            nb=json.loads(file.read_text())
            markdown=[]
            for cell in nb['cells']:
                source=''.join(cell['source'])
                if cell['cell_type']=='markdown':
                    markdown.append(source)
                    continue
                self.assertLessEqual(len(source.splitlines()),25,(file.name,source[:80]))
                if source.startswith('%'):continue
                tree=ast.parse(source)
                for n in ast.walk(tree):
                    if isinstance(n,ast.ImportFrom):
                        self.assertNotIn((n.module or '').split('.')[0],
                            ['langchain','llama_index','memorizz','lab_core','lab_experiments'])
            self.assertIn('Oracle',' '.join(markdown))
            self.assertGreater(len(' '.join(markdown)),5000)


if __name__=='__main__':unittest.main()
