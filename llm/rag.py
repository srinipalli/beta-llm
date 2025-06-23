from sentence_transformers import SentenceTransformer
from llm.vectorstore.vector_db import get_lance_table

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
table = get_lance_table()

def get_similar_ticket_context(title: str, description: str, top_k=10, similarity_threshold=0.3):
    query = f"{title}\n{description}"
    query_vector = embedding_model.encode(query).tolist()

    # Search top_k results
    results = (
        table.search(query_vector)
        .distance_type("cosine")
        .limit(top_k)
        .to_list()
    )

    context_blocks = []
    for res in results:
        distance = res.get("_distance", 1.0)  # Default far away
        if distance <= similarity_threshold:
            context_blocks.append(
                f"""--- Context from Ticket {res["ticket_id"]} ---
Title: {res.get("title", "N/A")}
Description: {res.get("description", "N/A")}
Priority: {res.get("priority", "N/A")}
Triage: {res.get("triage", "N/A")}
Category: {res.get("category", "N/A")}
Status: {res.get("status", "N/A")}
(Similarity Score: {round(1 - distance, 2)})"""
            )

    if not context_blocks:
        return "No highly similar tickets found."

    return "\n\n".join(context_blocks)
