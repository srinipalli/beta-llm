import numpy as np
from sentence_transformers import SentenceTransformer
import lancedb
from llm.vectorstore.vector_db import get_lance_table

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
table = get_lance_table()

def embed_and_store(processed):
    vector = embedding_model.encode(processed.summary).astype(np.float32).tolist()

    row = {
        "ticket_id": processed.ticket_id,
        "summary": processed.summary,
        "vector": vector
    }

    table.add([row])
    print(f"✅ Embedded & stored: {processed.ticket_id}")
