import os
from dotenv import load_dotenv
import mysql.connector
from llm.models import Ticket, ProcessedTicket
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

cursor = conn.cursor()

def assign_ticket(ticketId: str):
    try:
        cursor.execute(f'SELECT category, priority FROM processed WHERE ticket_id = "{ticketId}";')
        res = cursor.fetchone()
        c = res[0]
        # print("category: '",c.strip(),"'",sep='')
        p = res[1]
        # print("priority: ",p)
        cursor.execute(f'SELECT employee_id FROM employee WHERE category = "{c}" AND triage = "{p}" AND role = "P";')
        aid = cursor.fetchone()
        # print("aid: ",aid)
        cursor.execute(f'SELECT assigned_date FROM main_table WHERE ticket_id = "{ticketId}";')
        ad = cursor.fetchone()
        # print(ad)
        cursor.execute(f'INSERT INTO assign (ticket_id, assigned_id, assigned_date) VALUES ("{ticketId}","{aid[0]}","{ad[0]}")')
        conn.commit()
        cursor.execute(f'SELECT employee_name FROM employee WHERE employee_id = "{aid[0]}";')
        n = cursor.fetchone()
        # print(n)
        print(f'Ticket {ticketId} assigned to employee {n[0]} with ID {aid[0]} on date {ad[0]}')
        return True
    except Exception as e:
        print(f"Error while fetching ticket {ticketId}. This is the error:\n{e}")
        return False

# cursor.execute('SELECT ticket_id FROM processed;')
# tickets = cursor.fetchall()
# print(f"{len(tickets)} tickets are now being fetched from the database.")
# for i in tickets:
#     assign_ticket(i[0])
    
conn.close()