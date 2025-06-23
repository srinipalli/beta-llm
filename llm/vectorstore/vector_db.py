import os
import lancedb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

import pyarrow as pa

schema = pa.schema([
    pa.field("ticket_id", pa.string()),
    pa.field("title", pa.string()),
    pa.field("description", pa.string()),
    pa.field("priority", pa.string()),
    pa.field("category", pa.string()),
    pa.field("triage", pa.string()),
    pa.field("status", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 768)),
])


LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "ticketbackend/lancedb_data")
TABLE_NAME = "tickets"

embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def get_lance_table():
    db = lancedb.connect(LANCE_DB_PATH)
    if TABLE_NAME not in db.table_names():
        dummy_row = [{
            "ticket_id": "dummy ID",
            "title": "dummy title",
            "description": "dummy description",
            "priority": "P2",
            "category": "network",
            "triage": "L1",
            "status": "open",
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
        "title": ticket.get("title", ""),
        "description": ticket.get("description", ""),
        "priority": ticket.get("priority", ""),
        "category": ticket.get("category", "unknown"),
        "triage": ticket.get("triage", "L5"),
        "status": ticket.get("status", "unknown"),
        "vector": vector
    }
    table.add([row])
