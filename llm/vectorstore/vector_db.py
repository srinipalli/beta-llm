import os
import lancedb
import pyarrow as pa

# LanceDB config
LANCE_DB_PATH = os.getenv("LANCE_DB_PATH", "ticket_vector_db")
TABLE_NAME = "tickets"

def get_lance_table():
    db = lancedb.connect(LANCE_DB_PATH)

    try:
        # Try to open the existing table
        return db.open_table(TABLE_NAME)
    except:
        # If the table doesn't exist, define schema and create it
        schema = pa.schema([
            pa.field("ticket_id", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("triage", pa.string()),
            pa.field("category", pa.string()),
            pa.field("solution", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 768))  # Correct vector field
        ])
        return db.create_table(TABLE_NAME, schema=schema)
