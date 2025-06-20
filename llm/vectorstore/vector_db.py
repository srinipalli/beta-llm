# import os
# import lancedb
# import pyarrow as pa

# # LanceDB config
# # LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "ticket_vector_db")
# LANCE_DB_PATH = os.getenv("LANCE_DB_PATH")
# TABLE_NAME = "tickets"

# def get_lance_table():
#     db = lancedb.connect(LANCE_DB_PATH)

#     try:
#         # Try to open the existing table
#         return db.open_table(TABLE_NAME)
#     except:
#         # If the table doesn't exist, define schema and create it
#         schema = pa.schema([
#             pa.field("ticket_id", pa.string()),
#             pa.field("summary", pa.string()),
#             pa.field("triage", pa.string()),
#             pa.field("category", pa.string()),
#             pa.field("solution", pa.string()),
#             pa.field("vector", pa.list_(pa.float32(), 768))  # Correct vector field
#         ])
#         return db.create_table(TABLE_NAME, schema=schema)
# ticketbackend/lance_utils.py

import os
import lancedb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "ticketbackend/lancedb_data")
TABLE_NAME = "tickets"

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def get_lance_table():
    db = lancedb.connect(LANCE_DB_PATH)
    if TABLE_NAME not in db.table_names():
        dummy_row = [{
            "source": "dummy source",
            "ticket_id": "dummy ID",
            "title": "dummy title",
            "status": "dummy status",
            "triage": "L0",
            "category": "dummy",
            "employee_name" : "varshikan",
            "summary": "dummy summary",
            "solution": "dummy solution",
            "vector": embedding_model.encode("dummy summary").tolist(),
        }]
        table = db.create_table(TABLE_NAME, data=dummy_row)
        table.delete("ticket_id = 'dummy'")
    else:
        table = db.open_table(TABLE_NAME)
    return table

def add_ticket_to_lance(ticket: dict):
    table = get_lance_table()
    summary_text = ticket.get("summary", "")
    vector = embedding_model.encode(summary_text).tolist()
    existing = table.search(embedding_model.encode(ticket["summary"]).tolist()).limit(1).to_list()
    if any(row["ticket_id"] == ticket["ticket_id"] for row in existing):
        print("🟡 Ticket already embedded.")
        return

    row = {
        "ticket_id": ticket["ticket_id"],
        "title": ticket["title"],
        "summary": summary_text,
        "solution": ticket.get("solution", "No solution"),
        "category": ticket.get("category", "unknown"),
        "triage level": ticket.get("triage", "L5"),
        "ticket source": ticket.get("source", "unknown"),
        "ticket status": ticket.get("status", "unknown"),
        "employee assigned": ticket.get("employee_name", "unknown"),
        "vector": vector
    }

    table.add([row])
