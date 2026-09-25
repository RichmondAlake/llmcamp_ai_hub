"""Check standalone notebook dependencies and their shared data without paid calls."""
import ast
import builtins
import json
import os
import symtable
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'.data/matplotlib'))
import lab_experiments

LESSONS = json.loads((ROOT/'appbook/lessons.json').read_text())


def text(cell):
    return ''.join(cell['source'])


def unused_definitions(cells):
    """Find helpers unreachable from executable cells, without rewriting a notebook."""
    def names(node):
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    definitions, roots = {}, set()
    for cell in cells:
        if cell['cell_type'] != 'code':
            continue
        source = '\n'.join(line for line in text(cell).splitlines() if not line.lstrip().startswith(('%', '!')))
        for node in ast.parse(source).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                definitions[node.name] = node
            else:
                roots |= names(node)
    reached, queue = set(), list(roots)
    while queue:
        name = queue.pop()
        if name not in reached:
            reached.add(name)
            if name in definitions:
                queue.extend(names(definitions[name]))
    return set(definitions)-reached


class NotebookIntegrityTests(unittest.TestCase):
    def test_notebooks_and_appbook_load_the_same_fixtures(self):
        for lesson in LESSONS.values():
            nb = json.loads((ROOT/lesson['notebook']).read_text())
            scope = {'json': json, 'Path': lambda name: ROOT/name}
            for cell in nb['cells']:
                if cell['cell_type'] == 'code' and 'data' in cell.get('metadata', {}).get('tags', []):
                    exec(text(cell), scope)
            for name in lesson['data']:
                self.assertEqual(scope[name], getattr(lab_experiments, name))

    def test_all_functions_have_their_global_dependencies(self):
        for lesson in LESSONS.values():
            name = lesson['notebook']
            nb = json.loads((ROOT/name).read_text())
            definitions = [c for c in nb['cells'] if c['cell_type'] == 'code'
                           and 'definition' in c.get('metadata', {}).get('tags', [])]
            scope = {}
            for cell in definitions:
                exec(compile(text(cell), name, 'exec'), scope)
            scope.update({key: getattr(lab_experiments, key) for key in lesson['data']})
            available = set(scope)|set(vars(builtins))
            for cell in definitions:
                for function in symtable.symtable(text(cell), name, 'exec').get_children():
                    missing = {s.get_name() for s in function.get_symbols()
                               if s.is_global() and s.is_referenced()}-available
                    self.assertFalse(missing, (name, function.get_name(), missing))
            self.assertFalse(unused_definitions(nb['cells']), name)

    def test_learning_path_rubric_and_relevant_credentials(self):
        for lesson in LESSONS.values():
            nb = json.loads((ROOT/lesson['notebook']).read_text())
            sources = [text(c) for c in nb['cells']]
            self.assertEqual(sum(s.startswith('## Part ') and '⭐' in s.splitlines()[0] for s in sources), 5)
            self.assertEqual(sum('**⭐ Guided learning path**' in s for s in sources), 1)
            self.assertNotIn('webinar', '\n'.join(sources).lower())
            if lesson['lab'] == 'reranking':
                self.assertIn('normalized ranking score is `0.75`', '\n'.join(sources))
            keys = next(text(c) for c in nb['cells'] if 'credentials' in c.get('metadata', {}).get('tags', []))
            if lesson['lab'] == 'readers':
                self.assertNotIn('TYPESAFE_API_KEY', keys)
            if lesson['lab'] == 'selection':
                self.assertNotIn('OPENAI_API_KEY', keys)


if __name__ == '__main__':
    unittest.main()
