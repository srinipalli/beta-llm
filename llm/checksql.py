import mysql.connector
try:
    from database import get_connection
except ImportError:
    from llm.database import get_connection

def is_ticket_embedded(ticket_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT vectorized FROM metrics WHERE ticket_id = %s"
    cursor.execute(query, (ticket_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row and row[0] == 'Y'

def mark_ticket_as_embedded(ticket_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    query = "UPDATE metrics SET vectorized = 'Y' WHERE ticket_id = %s"
    cursor.execute(query, (ticket_id,))
    conn.commit()
    cursor.close()
    conn.close()
