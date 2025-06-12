import os
from dotenv import load_dotenv
import mysql.connector
try:
    from llm.models import Ticket, ProcessedTicket
except ImportError:
    from models import Ticket, ProcessedTicket
import datetime
load_dotenv()

H = os.getenv("MYSQL_HOST")
D = os.getenv("MYSQL_DB")
U = os.getenv("MYSQL_USER")
P = os.getenv("MYSQL_PASSWORD")

conn = mysql.connector.connect(
    host = H,
    database = D,
    user = U,
    password = P
)

cursor2 = conn.cursor()

def assign_ticket(ticketId: str, conn):
    cursor2 = conn.cursor()
    try:
        cursor2.execute(f'SELECT category, priority FROM processed WHERE ticket_id = "{ticketId}" LIMIT 1;')
        res = cursor2.fetchall()
        c = res[0][0]
        print("category: '",c.strip(),"'",sep='')
        p = res[0][1]
        print("priority: ",p)
        cursor2.execute(f'SELECT employee_id FROM employee WHERE category = "{c}" AND triage = "{p}" AND role = "P" LIMIT 1;')
        aidz = cursor2.fetchall()
        print(aidz)
        aid = aidz[0][0]
        print("assigned id: ",aid)
        cursor2.execute(f'SELECT assigned_date FROM main_table WHERE ticket_id = "{ticketId}" LIMIT 1;')
        adz = cursor2.fetchall()
        ad = adz[0][0]
        print("assigned date: ",ad)
        cursor2.execute(f'INSERT INTO assign (ticket_id, assigned_id, assigned_date) VALUES ("{ticketId}","{aid}","{ad}")')
        conn.commit()
        cursor2.execute(f'SELECT employee_name FROM employee WHERE employee_id = "{aid}";')
        n = cursor2.fetchall()
        name = n[0][0]
        print("name: ",name)
        print(f'Ticket {ticketId} assigned to employee {name} with ID {aid} on date {ad}')
        return True
    except Exception as e:
        print(f"Error while fetching ticket {ticketId}. This is the error:\n{e}")
        return False

# cursor2.execute('SELECT ticket_id FROM processed;')
# tickets = cursor2.fetchall()
# print(f"{len(tickets)} tickets are now being fetched from the database.")
# for i in tickets:
#     assign_ticket(i[0],conn)
conn.close()