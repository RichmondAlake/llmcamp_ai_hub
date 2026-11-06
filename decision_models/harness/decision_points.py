"""The twenty decision points of the memory loop, as data.

Each row names the question a memory system has to answer, how it is usually implemented, the
d1 primitive that fits it, and the notebook that builds it. Rows marked "listed only" are here so
the inventory is complete; they are not implemented in these notebooks.
"""

from __future__ import annotations

import pandas as pd

R_ORDER = ["Retain", "Refine", "Recall", "Reuse"]

DECISION_POINTS = [
    {"r": "Retain", "n": 1, "name": "Chunk boundary",
     "question": "Does a new unit of meaning start here?",
     "typical": "cosine drop between neighbouring sentences, cut at a percentile (or a fixed window)",
     "d1_primitive": "Noul per gap", "notebook": "01"},
    {"r": "Retain", "n": 2, "name": "Retention gate",
     "question": "Is this worth keeping at all?",
     "typical": "none: extraction runs on every turn (or an LLM importance prompt)",
     "d1_primitive": "Noul, a gate before extraction", "notebook": "06"},
    {"r": "Retain", "n": 3, "name": "Memory type",
     "question": "Which store does this belong in?",
     "typical": "LLM prompt",
     "d1_primitive": "Choice: preference, fact, procedure, event", "notebook": "06"},
    {"r": "Retain", "n": 4, "name": "Sensitivity gate",
     "question": "Does this contain something that must not be stored?",
     "typical": "regex, then LLM",
     "d1_primitive": "regex mask, then Choice on the local model", "notebook": "listed only"},
    {"r": "Retain", "n": 5, "name": "Extraction quality",
     "question": "Is the extracted memory faithful to the source?",
     "typical": "LLM as judge",
     "d1_primitive": "Noul", "notebook": "listed only"},
    {"r": "Retain", "n": 6, "name": "Duplicate check",
     "question": "Is this the same as something already stored?",
     "typical": "cosine threshold (0.95 is common; memorizz treats summaries as duplicates from 0.97)",
     "d1_primitive": "Choice of five relations, per candidate pair", "notebook": "05"},
    {"r": "Retain", "n": 7, "name": "Conflict detection",
     "question": "Does this contradict something already stored?",
     "typical": "LLM prompt, or nothing",
     "d1_primitive": "the same Choice: contradicts", "notebook": "05"},
    {"r": "Retain", "n": 8, "name": "Resolution",
     "question": "Insert, update, merge or forget?",
     "typical": "LLM prompt",
     "d1_primitive": "the same Choice picks skip, update, supersede, link or insert", "notebook": "05"},
    {"r": "Refine", "n": 9, "name": "Staleness",
     "question": "Is this memory still true?",
     "typical": "age decay (memorizz RetentionPlanner)",
     "d1_primitive": "Noul", "notebook": "listed only"},
    {"r": "Refine", "n": 10, "name": "Consolidation and promotion",
     "question": "Should these memories become one, or move up a tier?",
     "typical": "LLM (memorizz consolidation)",
     "d1_primitive": "the same Choice, run on a schedule", "notebook": "05"},
    {"r": "Refine", "n": 11, "name": "Memory utility",
     "question": "Has this memory been useful?",
     "typical": "access counts",
     "d1_primitive": "Noul", "notebook": "listed only"},
    {"r": "Refine", "n": 12, "name": "Trace selection",
     "question": "Is this run worth learning from?",
     "typical": "LLM",
     "d1_primitive": "Noul", "notebook": "listed only"},
    {"r": "Recall", "n": 13, "name": "Recall gate",
     "question": "Does this turn need memory at all?",
     "typical": "always retrieve",
     "d1_primitive": "no memory type says yes", "notebook": "04"},
    {"r": "Recall", "n": 14, "name": "Memory routing",
     "question": "Which store should be searched?",
     "typical": "nearest store description, or an LLM prompt",
     "d1_primitive": "Noul per memory type, in one request", "notebook": "04"},
    {"r": "Recall", "n": 15, "name": "Query rewrite need",
     "question": "Can this be searched as written?",
     "typical": "LLM (RetrievalPolicy.query_expansion)",
     "d1_primitive": "Noul", "notebook": "listed only"},
    {"r": "Recall", "n": 16, "name": "Reranking",
     "question": "Does this candidate help answer the query?",
     "typical": "cosine order, or a cross-encoder",
     "d1_primitive": "Noul per candidate, sorted by P", "notebook": "02"},
    {"r": "Recall", "n": 17, "name": "Sufficiency check",
     "question": "Is what we kept enough to answer?",
     "typical": "LLM",
     "d1_primitive": "Noul over the relevant count", "notebook": "listed only"},
    {"r": "Recall", "n": 18, "name": "Injection screen",
     "question": "Is this memory trying to instruct the agent?",
     "typical": "LLM or classifier",
     "d1_primitive": "Noul per candidate", "notebook": "listed only"},
    {"r": "Reuse", "n": 19, "name": "Tool and skill selection",
     "question": "Which tool should run?",
     "typical": "embedding top-k, then the LLM picks",
     "d1_primitive": "Choice over the top k, plus none", "notebook": "07"},
    {"r": "Reuse", "n": 20, "name": "Tool-call guard",
     "question": "Should this call run as written?",
     "typical": "allowlist rules",
     "d1_primitive": "Noul", "notebook": "listed only"},
]


def inventory() -> pd.DataFrame:
    """The twenty decision points as a table, in loop order (Retain, Refine, Recall, Reuse)."""
    frame = pd.DataFrame(DECISION_POINTS)
    frame["r"] = pd.Categorical(frame["r"], categories=R_ORDER, ordered=True)
    return frame.sort_values(["r", "n"]).reset_index(drop=True)
