"""Oracle-maintained vector storage; benchmark retrieval stays exact and explicit."""
import array
import time

from langchain_core.embeddings import Embeddings
from langchain_oracledb.vectorstores import DistanceStrategy, OracleVS

from lab_core import embed, read_lob


class MeasuredVoyage(Embeddings):
    """Reuse the lesson's measured HTTP calls, including query/document input types."""
    def __init__(self, lab):
        self.lab = lab

    def embed_documents(self, texts):
        return embed(self.lab, texts)

    def embed_query(self, text):
        return embed(self.lab, [text], 'query')[0]


class VoyageStore(OracleVS):
    def get_embedding_dimension(self):
        # embed() explicitly requests and validates 1024 dimensions. Avoid an
        # otherwise redundant, billable probe just to discover this known size.
        return 1024


class OracleStorage:
    def __init__(self, lab):
        self.lab = lab
        self.embeddings = MeasuredVoyage(lab)
        self.vectors = VoyageStore(lab['db'], self.embeddings, 'S1_VECTORS',
                                   DistanceStrategy.COSINE)
        lab['metadata']['storage_backend'] = 'langchain-oracledb 1.5.0 / OracleVS'
        lab['metadata']['retrieval_mode'] = 'exact cosine SQL; distance then source ID'

    def store(self, collection, documents):
        ids = [collection + ':' + d['id'] for d in documents]
        metadata = [{**{k: v for k, v in d.items() if k not in ('text', 'id')},
                     'doc_id': d['id'], 'collection': collection,
                     'run_id': self.lab['run_id'],
                     'embedding_model': self.lab['models']['voyage']} for d in documents]
        inserted = self.vectors.add_texts([d['text'] for d in documents], metadata, ids=ids)
        if inserted != ids:
            raise ValueError('Vector insertion was incomplete; do not score a partial corpus.')

    def retrieve(self, collection, query, limit=20):
        vector = array.array('f', self.embeddings.embed_query(query))
        # OracleVS search uses FETCH APPROX. Keep the experiment's exact search
        # and deterministic ID tie-break, including at the candidate cutoff.
        sql = """
            SELECT
                JSON_VALUE(metadata, '$.doc_id') AS doc_id,
                text,
                metadata,
                VECTOR_DISTANCE(embedding, :vector, COSINE) AS distance
            FROM s1_vectors
            WHERE JSON_VALUE(metadata, '$.collection') = :collection
            ORDER BY distance, doc_id
            FETCH FIRST :count ROWS ONLY
        """
        started = time.perf_counter()
        with self.lab['db'].cursor() as cur:
            cur.execute(sql, vector=vector, collection=collection, count=limit)
            rows = [{'id': r[0], 'text': read_lob(r[1]),
                     'metadata': {k: v for k, v in r[2].items()
                                  if k not in ('doc_id', 'collection', 'run_id', '__orcl_internal_doc_id')},
                     'distance': float(r[3])} for r in cur.fetchall()]
        return rows, time.perf_counter() - started
