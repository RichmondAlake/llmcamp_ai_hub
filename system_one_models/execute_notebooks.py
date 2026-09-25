"""Execute the actual notebook cells against live providers and Docker Oracle.

Install requirements first. This runner skips only installation cells, preserves
outputs in artifacts/executed, and records expected model-availability blocks.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parent


def execute(path):
    notebook = nbformat.read(path, as_version=4)
    destination = ROOT / 'artifacts' / 'executed' / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    for cell in notebook.cells:
        # A fresh execution supersedes an earlier offline conclusion refresh.
        cell.metadata.pop('result_provenance', None)
        if 'install' in cell.metadata.get('tags', []):
            cell.metadata['tags'].append('skip-execution')
    client = NotebookClient(notebook, timeout=900, kernel_name='system-one',
                            resources={'metadata': {'path': str(ROOT)}})
    client.on_cell_complete = lambda cell, cell_index, **kw: print(
        f'{path.stem}: cell {cell_index + 1}/{len(notebook.cells)}', flush=True)
    outcome = {'notebook': path.name, 'status': 'completed'}
    try:
        client.execute()
    except CellExecutionError as exc:
        outcome = {'notebook': path.name, 'status': 'failed', 'error': str(exc)}
        if path.name.startswith('06_') and 'Unavailable requested models:' in str(exc):
            outcome['status'] = 'availability_blocked'
    finally:
        nbformat.write(notebook, destination)
        if outcome['status']=='completed':
            # Leave actual outputs in the notebook the learner opens, as requested.
            for cell in notebook.cells:
                tags=cell.metadata.get('tags',[])
                cell.metadata['tags']=[t for t in tags if t!='skip-execution']
            nbformat.write(notebook,path)
    return outcome


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('numbers', nargs='*', default=['01','02','03','04','05','06'])
    args = parser.parse_args()
    kernel_root = ROOT / '.data' / 'jupyter'
    kernel_dir = kernel_root / 'kernels' / 'system-one'
    kernel_dir.mkdir(parents=True, exist_ok=True)
    (kernel_dir/'kernel.json').write_text(json.dumps({
        'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
        'display_name': 'System One lab', 'language': 'python'}))
    os.environ['JUPYTER_PATH'] = str(kernel_root)
    os.environ['SYSTEM_ONE_ENV_FILE'] = str(ROOT/'.env')
    os.environ['S1_USE_ENV_KEYS'] = '1'  # Explicit non-interactive validation only.
    os.environ['MPLCONFIGDIR'] = str(ROOT/'.data'/'matplotlib')
    os.environ['HF_HOME'] = str(ROOT/'.data'/'huggingface')
    status_file = ROOT/'artifacts'/'execution_status.json'
    outcomes = json.loads(status_file.read_text()) if status_file.exists() else []
    for number in args.numbers:
        path, = ROOT.glob(number+'_*.ipynb')
        print('EXECUTING', path.name, flush=True)
        outcome = execute(path)
        outcomes = [o for o in outcomes if o['notebook'] != path.name]+[outcome]
        print(json.dumps(outcome), flush=True)
        status_file.write_text(json.dumps(sorted(outcomes,key=lambda o:o['notebook']), indent=2))
    return int(any(o['status']=='failed' for o in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
