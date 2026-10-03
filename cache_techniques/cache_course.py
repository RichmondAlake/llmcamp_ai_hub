"""Reviewed provider, local-model and Oracle helpers shared by the Cachecraft appbook."""
import array
import copy
import hashlib
import json
import os
import time
import uuid
from getpass import getpass

import numpy as np
import oracledb
import pandas as pd
from anthropic import Anthropic
from IPython.display import display
from tavily import TavilyClient

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

CALLS = []
SEARCH_CALLS = []
EMBEDDING_CALLS = []
CACHE_METRICS = []
MODEL = "claude-opus-5-5"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBED_DIM = 384
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
SEMANTIC_TABLE = "CT_SEMANTIC_LOCAL"
RESPONSE_TABLE = "CT_RESPONSE_CACHE"
OWNER = os.getenv("CACHE_TRAVELER", "local-learner")
TAVILY_USD_PER_CREDIT = float(os.getenv("TAVILY_USD_PER_CREDIT", "0.008"))
PRICE_DATE = "2026-10-03"
RATES = {"input": 4, "write": 5, "read": 0.20, "output": 20}
MISSING = object()
_LOCAL_MODELS = {}


def secret(name):
    """Request a private key with getpass; automation explicitly opts into environment keys."""
    value = os.getenv(name, "") if os.getenv("NOTEBOOK_USE_ENV_KEYS") == "1" else getpass(f"Enter {name}: ")
    if not value.strip():
        raise ValueError(f"{name} is required.")
    return value.strip()


def pretty(value):
    """Indent nested objects so configuration and provider counters are easy to inspect."""
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def key_for(value):
    """Hash canonical structured inputs; hashes are identities, not secret credentials."""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def model_client():
    """Construct the raw Anthropic client; every cache miss still uses real generation."""
    return Anthropic(api_key=secret("ANTHROPIC_API_KEY"), timeout=120, max_retries=2)


def generate(client, question, prefix, use_prompt_cache=False, evidence=None):
    """Send stable prefix before changing question/evidence and record actual provider counters."""
    block = {"type": "text", "text": prefix}
    if use_prompt_cache:
        block["cache_control"] = {"type": "ephemeral"}

    started = time.perf_counter()
    response = client.messages.create(
        model=MODEL, max_tokens=4096,
        system=[block],
        messages=[{"role": "user", "content": pretty({"question": question, "evidence": evidence or []})}],
        output_config={"effort": "low"},
    )
    usage = response.usage
    record = {
        "seconds": time.perf_counter() - started,
        "input_tokens": usage.input_tokens,
        "cache_write_tokens": usage.cache_creation_input_tokens or 0,
        "cache_read_tokens": usage.cache_read_input_tokens or 0,
        "output_tokens": usage.output_tokens,
    }
    record["estimated_usd"] = (
        record["input_tokens"] * RATES["input"]
        + record["cache_write_tokens"] * RATES["write"]
        + record["cache_read_tokens"] * RATES["read"]
        + record["output_tokens"] * RATES["output"]
    ) / 1_000_000
    CALLS.append(record)
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"Incomplete response: {response.stop_reason}")
    text = "\n".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise RuntimeError("No visible answer.")
    return text


class TTLCache:
    """Bounded exact-key cache; an expired result is a miss and returned data is copied."""
    def __init__(self, ttl_seconds=300, capacity=128):
        self.ttl_seconds = ttl_seconds
        self.capacity = capacity
        self.entries = {}

    def get(self, key):
        entry = self.entries.get(key)
        if not entry or entry["expires_at"] <= time.monotonic():
            self.entries.pop(key, None)
            return MISSING
        return copy.deepcopy(entry["value"])

    def put(self, key, value):
        if self.ttl_seconds <= 0:
            raise ValueError("TTL must be positive.")
        if key not in self.entries and len(self.entries) >= self.capacity:
            self.entries.pop(next(iter(self.entries)))
        self.entries[key] = {
            "value": copy.deepcopy(value),
            "expires_at": time.monotonic() + self.ttl_seconds,
        }


def exact_response(client, query, prefix, cache=None):
    """Reuse only the same owner, model, prefix and exact query, within this cache's TTL."""
    identity = key_for({"owner": OWNER, "model": MODEL, "prefix": prefix, "query": query})
    if cache is not None:
        found = cache.get(identity)
        if found is not MISSING:
            return {"answer": found, "hit": True}

    answer = generate(client, query, prefix)
    if cache is not None:
        cache.put(identity, answer)
    return {"answer": answer, "hit": False}


def local_model(kind):
    """Load the pinned open-source Hugging Face encoder or reranker once per process, on the CPU."""
    if kind not in _LOCAL_MODELS:
        from sentence_transformers import CrossEncoder, SentenceTransformer
        if kind == "encoder":
            _LOCAL_MODELS[kind] = SentenceTransformer(EMBED_MODEL, revision=EMBED_REVISION, device="cpu")
        else:
            _LOCAL_MODELS[kind] = CrossEncoder(RERANK_MODEL, revision=RERANK_REVISION, device="cpu")
    return _LOCAL_MODELS[kind]


def local_embedding(text, role=None):
    """Encode locally; record compute time and token count. A local encoder has no API cost.

    MiniLM has no query/document prompt, so role does not change this vector. It stays in the
    cache identity because models that use input-role prompts produce different vectors per role.
    """
    model = local_model("encoder")
    started = time.perf_counter()
    vector = model.encode(text, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
    if vector.shape != (EMBED_DIM,) or not np.isfinite(vector).all():
        raise ValueError("Invalid embedding.")
    tokens = len(model.tokenizer(text, truncation=True, max_length=model.max_seq_length)["input_ids"])
    EMBEDDING_CALLS.append({
        "seconds": time.perf_counter() - started, "input_tokens": tokens, "estimated_usd": 0.0,
    })
    return vector.tolist()


def cached_embedding(text, cache=None, role=None):
    """Key includes text, model, revision, role and dimensions; a hit skips the local encoder."""
    identity = key_for({
        "owner": OWNER, "model": EMBED_MODEL, "revision": EMBED_REVISION, "role": role,
        "dimensions": EMBED_DIM, "text": text,
    })
    if cache is not None:
        found = cache.get(identity)
        if found is not MISSING:
            return found, True

    vector = local_embedding(text, role)
    if cache is not None:
        cache.put(identity, vector)
    return vector, False


def rerank(query, passages):
    """Score each (query, passage) pair with the local cross-encoder; higher is more relevant."""
    if not passages:
        return []
    scores = local_model("reranker").predict([(query, passage) for passage in passages])
    return [float(score) for score in scores]


def merge_once(cursor, sql, binds):
    """Run an upsert MERGE; a concurrent first insert of the same key by another worker wins.

    Two sessions that MERGE the same new key at once both take the insert branch. The second waits
    for the first to commit and then fails with ORA-00001; its row already exists, so that is success.
    """
    try:
        cursor.execute(sql, binds)
    except oracledb.IntegrityError as error:
        if error.args[0].code != 1:
            raise


def true_cache_connections():
    """Writes go to the primary service; reads go to the Oracle True Cache service."""
    user, password = os.environ["TRUE_CACHE_USER"], os.environ["TRUE_CACHE_PASSWORD"]
    primary = oracledb.connect(user=user, password=password, dsn=os.environ["PRIMARY_DSN"])
    cache = oracledb.connect(user=user, password=password, dsn=os.environ["TRUE_CACHE_DSN"])
    return primary, cache


def response_table(primary):
    """Create the exact-response table on the primary; True Cache replicates it from redo."""
    create_if_missing(primary, f"""
        CREATE TABLE {RESPONSE_TABLE} (
            cache_key VARCHAR2(64) PRIMARY KEY,
            payload CLOB NOT NULL CHECK (payload IS JSON),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    with primary.cursor() as cursor:
        cursor.execute(f"DELETE FROM {RESPONSE_TABLE} WHERE expires_at <= SYSTIMESTAMP")
    primary.commit()


class TrueCacheStore:
    """Exact-key TTL cache in Oracle: reads are served by True Cache, writes go to the primary.

    True Cache follows the primary with a small lag, so a True Cache miss is checked on the
    primary (the table of record) before the caller pays for generation. last_tier records
    which tier answered: "true_cache", "primary" or None for a miss.
    """
    def __init__(self, primary, cache, ttl_seconds=300):
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive.")
        self.primary, self.cache, self.ttl_seconds = primary, cache, ttl_seconds
        self.last_tier, self.last_read_seconds = None, None

    def read(self, conn, key):
        rows = sql_rows(conn, f"""
            SELECT payload FROM {RESPONSE_TABLE}
            WHERE cache_key = :cache_key AND expires_at > SYSTIMESTAMP
        """, {"cache_key": key})
        if not rows:
            return MISSING
        payload = rows[0]["payload"]
        # python-oracledb returns a column with an IS JSON check as Python objects already.
        return json.loads(payload) if isinstance(payload, (str, bytes)) else payload

    def get(self, key):
        started = time.perf_counter()
        self.last_tier = None
        for tier, conn in [("true_cache", self.cache), ("primary", self.primary)]:
            found = self.read(conn, key)
            if found is not MISSING:
                self.last_tier = tier
                break
        self.last_read_seconds = time.perf_counter() - started
        return found

    def put(self, key, value):
        with self.primary.cursor() as cursor:
            # Bind each value once in the source row; a CLOB bound twice in a MERGE can fail (ORA-03146).
            merge_once(cursor, f"""
                MERGE INTO {RESPONSE_TABLE} d
                USING (SELECT :cache_key cache_key, :payload payload, :ttl ttl FROM dual) s
                ON (d.cache_key = s.cache_key)
                WHEN MATCHED THEN UPDATE SET d.payload = s.payload, d.created_at = SYSTIMESTAMP,
                    d.expires_at = SYSTIMESTAMP + NUMTODSINTERVAL(s.ttl, 'SECOND')
                WHEN NOT MATCHED THEN INSERT (cache_key, payload, expires_at)
                VALUES (s.cache_key, s.payload, SYSTIMESTAMP + NUMTODSINTERVAL(s.ttl, 'SECOND'))
            """, {"cache_key": key, "payload": json.dumps(value, default=str), "ttl": self.ttl_seconds})
        self.primary.commit()


def oracle_connection():
    """Connect to a dedicated learner schema; database password entry is hidden."""
    user = os.getenv("ORACLE_USER") or input("Oracle schema user: ").strip()
    password = os.getenv("ORACLE_PASSWORD") or getpass("Oracle password: ")
    dsn = os.getenv("ORACLE_DSN") or input("Oracle DSN: ").strip()
    if user.lower() in {"sys", "system"}:
        raise ValueError("Use a dedicated learner schema.")
    return oracledb.connect(user=user, password=password, dsn=dsn)


def sql_rows(conn, sql, binds=None):
    """Read actual Oracle records with bound values and convert LOBs to ordinary values."""
    with conn.cursor() as cursor:
        cursor.execute(sql, binds or {})
        names = [column[0].lower() for column in cursor.description]
        return [dict(zip(names, [value.read() if hasattr(value, "read") else value for value in row])) for row in cursor]


def create_if_missing(conn, sql):
    """Ignore only an existing object; missing privileges and vector-memory errors remain visible."""
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql)
        except oracledb.DatabaseError as error:
            if error.args[0].code != 955:
                raise


def semantic_table(conn):
    """Create the standalone semantic cache's vector table explicitly, from scratch."""
    create_if_missing(conn, f"""
        CREATE TABLE {SEMANTIC_TABLE} (
            cache_id VARCHAR2(64) PRIMARY KEY,
            namespace VARCHAR2(64) NOT NULL,
            question CLOB NOT NULL,
            answer CLOB NOT NULL,
            embedding VECTOR({EMBED_DIM}, FLOAT32) NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)


def semantic_index(conn):
    """Build HNSW for the standalone cache; Oracle needs a configured vector pool."""
    create_if_missing(conn, f"""
        CREATE VECTOR INDEX CT_LOCAL_HNSW ON {SEMANTIC_TABLE}(embedding)
        ORGANIZATION INMEMORY NEIGHBOR GRAPH
        DISTANCE COSINE WITH TARGET ACCURACY 95
        PARAMETERS (TYPE HNSW, NEIGHBORS 32, EFCONSTRUCTION 128)
    """)


def raw_semantic_lookup(conn, query, vector, namespace, threshold=0.10):
    """Filter namespace/expiry before cosine ranking; lower distance is better."""
    found = sql_rows(conn, f"""
        SELECT /*+ VECTOR_INDEX_TRANSFORM({SEMANTIC_TABLE}) */
               question, answer, VECTOR_DISTANCE(embedding, :vector, COSINE) AS distance
        FROM {SEMANTIC_TABLE}
        WHERE namespace = :namespace AND expires_at > SYSTIMESTAMP
        ORDER BY distance
        FETCH APPROX FIRST 1 ROWS ONLY
    """, {"vector": array.array("f", vector), "namespace": namespace})
    if found and found[0]["distance"] <= threshold:
        return found[0]
    return None


def raw_semantic_store(conn, query, answer, vector, namespace, ttl_seconds=300):
    """Persist one generated stable answer with an application-owned namespace and expiry."""
    identity = key_for([namespace, query])
    with conn.cursor() as cursor:
        merge_once(cursor, f"""
            MERGE INTO {SEMANTIC_TABLE} d
            USING (SELECT :id cache_id, :namespace namespace, :question question, :answer answer,
                          :vector embedding, :ttl ttl FROM dual) s
            ON (d.cache_id = s.cache_id)
            WHEN MATCHED THEN UPDATE SET
                d.answer = s.answer, d.embedding = s.embedding,
                d.expires_at = SYSTIMESTAMP + NUMTODSINTERVAL(s.ttl, 'SECOND')
            WHEN NOT MATCHED THEN INSERT
                (cache_id, namespace, question, answer, embedding, expires_at)
            VALUES (
                s.cache_id, s.namespace, s.question, s.answer, s.embedding,
                SYSTIMESTAMP + NUMTODSINTERVAL(s.ttl, 'SECOND')
            )
        """, {
            "id": identity, "namespace": namespace, "question": query,
            "answer": answer, "vector": array.array("f", vector), "ttl": ttl_seconds,
        })
    conn.commit()


def raw_semantic_response(client, conn, query, prefix, namespace):
    """Make an embedding on every lookup; a semantic hit avoids generation but still has lookup cost."""
    vector = local_embedding(query)
    hit = raw_semantic_lookup(conn, query, vector, namespace)
    if hit:
        return {"answer": hit["answer"], "hit": True, "distance": hit["distance"]}
    answer = generate(client, query, prefix)
    raw_semantic_store(conn, query, answer, vector, namespace)
    return {"answer": answer, "hit": False, "distance": None}


def live_tool(tavily, query, cache=None, depth="basic", max_results=3):
    """Cache a read-only search by every argument and owner; retain the original collection time."""
    identity = key_for({
        "owner": OWNER, "tool": "tavily.search", "query": query,
        "depth": depth, "max_results": max_results, "include_answer": False,
    })
    if cache is not None:
        found = cache.get(identity)
        if found is not MISSING:
            return {**found, "tool_cache_hit": True}

    started = time.perf_counter()
    result = tavily.search(
        query=query, search_depth=depth, max_results=max_results,
        include_answer=False, include_usage=True, timeout=60,
    )
    result["collected_at"] = time.time()
    usage = result.get("usage") or {}
    credits = usage.get("credits")
    SEARCH_CALLS.append({
        "seconds": time.perf_counter() - started, "credits": credits,
        "estimated_usd": credits * TAVILY_USD_PER_CREDIT if credits is not None else None,
    })
    if cache is not None:
        cache.put(identity, result)
    return {**result, "tool_cache_hit": False}


def snapshot():
    """Mark ledger positions so each measurement includes only its own real provider calls."""
    return len(CALLS), len(EMBEDDING_CALLS), len(SEARCH_CALLS)


def measured(label, operation):
    """Record wall-clock latency and sum provider-priced usage deltas; a warm application hit costs zero API calls."""
    before = snapshot()
    started = time.perf_counter()
    result = operation()
    after = snapshot()
    slices = [
        CALLS[before[0]:after[0]],
        EMBEDDING_CALLS[before[1]:after[1]],
        SEARCH_CALLS[before[2]:after[2]],
    ]
    costs = [record["estimated_usd"] for ledger in slices for record in ledger]
    CACHE_METRICS.append({
        "mechanism": label, "seconds": time.perf_counter() - started,
        "estimated_api_usd": sum(costs) if all(value is not None for value in costs) else None,
        "llm_calls": after[0] - before[0],
        "embedding_calls": after[1] - before[1],
        "tool_calls": after[2] - before[2],
        "provider_cache_read_tokens": sum(record["cache_read_tokens"] for record in slices[0]),
        "provider_cache_write_tokens": sum(record["cache_write_tokens"] for record in slices[0]),
    })
    return result


def compare_measurements():
    """Show actual cold/warm measurements; negative savings remain visible."""
    frame = pd.DataFrame(CACHE_METRICS)
    if len(frame) >= 2:
        baseline = frame.iloc[0]
        frame["latency_saved_seconds"] = baseline["seconds"] - frame["seconds"]
        frame["api_usd_saved"] = baseline["estimated_api_usd"] - frame["estimated_api_usd"]
    display(frame)
    return frame
