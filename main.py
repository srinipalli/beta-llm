import mysql.connector
from llm.lutils import process_ticket
from llm.models import Ticket, ProcessedTicket
import os
import time
from llm.assign import assign_ticket
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host = os.getenv("MYSQL_HOST"),
    user = os.getenv("MYSQL_USER"),
    password = os.getenv("MYSQL_PASSWORD"),
    database = os.getenv("MYSQL_DB")
)
REQUEST_INTERVAL = 2.5  # seconds
last_request_time = 0
cursor = conn.cursor()
cursor.execute('SELECT * from main_table;')
t = cursor.fetchall()
print(f"{len(t)} tickets are now being fetched from the database.")
print("Time to start the loop to process the tickets :D")
consent = input("Do you want to start processing? (Y or N): ")
if consent.lower() == "y":
    for i in t:
        current_time = time.time()
        time_since_last = current_time - last_request_time

        if time_since_last < REQUEST_INTERVAL:
            wait_time = REQUEST_INTERVAL - time_since_last
            print(f"Rate limiting: waiting for {wait_time:.2f} seconds...")
            time.sleep(wait_time)
        try:
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
            print(f"processed for {ticketz.ticket_id}:\n",processed)
            cursor.execute("INSERT INTO processed (ticket_id, summary, priority, category, solution) VALUES (%s, %s, %s, %s, %s)",
                        (processed.ticket_id, processed.summary, processed.priority, processed.category, processed.solution))
            conn.commit()
            cursor.execute(f'SELECT ticket_id FROM processed WHERE ticket_id = "{ticketz.ticket_id}";')
            a = cursor.fetchone()
            if a is not None:
                assign_ticket(ticketz.ticket_id)
                print(f'Ticket {ticketz.ticket_id} is assigned.')
            else:
                print(f'Ticket {ticketz.ticket_id} was not assigned, unfortunately.')
            print(f"Ticket {ticketz.ticket_id} processed and stored.\n")
        except Exception as e:
            print(f"[ERROR] Ticket {i[0]} failed: {e}")
        last_request_time = time.time()
    cursor.execute('SELECT ticket_id FROM processed;')
    processedList = cursor.fetchall()
    cursor.execute('SELECT ticket_id FROM assign;')
    assignedList = cursor.fetchall()
    for processedTicketId in processedList:
        if processedTicketId not in assignedList:
            print(f'Ticket {processedTicketId} was processed but not assigned. Now retrying...')
            try:
                assign_ticket(processedTicketId)
            except Exception as e:
                print(f'Failed to assign ticket {processedTicketId} again')
                print(f'Error:\n{e}')

else:
    print("Cancelled by user.")
conn.close()