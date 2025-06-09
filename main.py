import mysql.connector
from llm.handlers import process_ticket
from llm.models import Ticket, ProcessedTicket

conn = mysql.connector.connect(
    host = 'localhost',
    username = 'root',
    password = 'Root1234',
    database = 'ticket'
)

cursor = conn.cursor()

cursor.execute("SELECT * from main_table;")

t = cursor.fetchall()
cursor.execute("DELETE FROM processed;")
for i in t:
    ticketz = Ticket(
        ticket_id = i[0],
        severity = i[1],
        module = i[2],
        title = i[3],
        description = i[4],
        priority = i[5],
        status = i[6],
        category = i[7],
        reported_date = i[8],
        assigned_to = i[9],
        assigned_date = i[10]
    )
    processed = process_ticket(ticketz)
    cursor.execute("INSERT INTO processed (ticket_id, summary, priority, category, sub_category, assigned_to, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (processed.ticket_id, processed.summary, processed.priority, processed.category, processed.sub_category, processed.assigned_to, processed.reason))
    conn.commit()
conn.close()