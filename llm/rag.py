from sentence_transformers import SentenceTransformer
from llm.vectorstore.vector_db import get_lance_table

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
table = get_lance_table()


def get_similar_ticket_context(title: str, description: str, top_k=3):
    query = f"{title}\n{description}"
    query_vector = embedding_model.encode(query).tolist()
    results = table.search(query_vector).distance_type("cosine").limit(top_k).to_list()

    context_blocks = []
    for res in results:
        context_blocks.append(
            f"""--- Context from Ticket {res["ticket_id"]} ---
Summary: {res["summary"]}
Triage: {res["triage"]}
Category: {res["category"]}
Solution: {res["solution"]}"""
        )
    return "\n\n".join(context_blocks)
