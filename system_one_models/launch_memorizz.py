"""Open this course in the local Memorizz checkout's real Evalground UI."""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=ROOT.parent.parent/'memorizz')
parser.add_argument('--port',type=int,default=8766)
args = parser.parse_args()
load_dotenv(ROOT/'.env')
sys.path.insert(0,str(args.repo/'src'))
os.environ['MEMORIZZ_SYSTEM_ONE_HOME']=str(ROOT)
os.environ['MEMORIZZ_COMPARISON_HOME']=str(ROOT/'artifacts'/'memorizz'/'experiments')
os.environ['HF_HOME']=str(ROOT/'.data'/'huggingface')

import uvicorn
from memorizz.memory_provider import FileSystemConfig, FileSystemProvider
from memorizz.ui import state
from memorizz.ui.app import create_app

# UI session metadata is local. Experiment evidence is the verified Oracle export;
# the replay never calls this provider or silently rebuilds embeddings with Ollama.
provider=FileSystemProvider(FileSystemConfig(
    root_path=str(ROOT/'.data'/'memorizz-ui'),lazy_vector_indexes=True))
state._state.update(provider=provider,provider_type='filesystem',connection_info={})
uvicorn.run(create_app(),host='127.0.0.1',port=args.port,lifespan='off')
