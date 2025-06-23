import mysql.connector
try:
    from llm.embed import embed_and_store 
except ImportError:
    from embed import embed_and_store
from database import get_connection

def embed_ground_tickets():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM ground LIMIT 200")
    rows = cursor.fetchall()

    for row in rows:
        embed_and_store(row)

    cursor.close()
    conn.close()
    print("✅ Embedded 200 ground tickets.")

# Run this once
embed_ground_tickets()
