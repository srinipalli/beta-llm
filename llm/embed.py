import numpy as np
from sentence_transformers import SentenceTransformer
from llm.vectorstore.vector_db import get_lance_table

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
table = get_lance_table()

def embed_and_store(row: dict):
    vector = embedding_model.encode(row.get("summary", "")).astype(np.float32).tolist()

    record = {
        "ticket_id": row["ticket_id"],
        "title": row.get("title", ""),
        "summary": row.get("summary", ""),
        "solution": row.get("solution", ""),
        "category": row.get("category", ""),
        "triage": row.get("triage", "L5"),
        "source": row.get("source", "unknown"),
        "status": row.get("status", "unknown"),
        "employee_name": row.get("employee_name", "Unknown"),
        "vector": vector
    }

    table.add([record])
    print(f"✅ Embedded & stored ticket: {row['ticket_id']}")