import os
from dotenv import load_dotenv
import mysql.connector
try:
    from llm.models import Ticket, ProcessedTicket
except ImportError:
    from models import Ticket, ProcessedTicket

load_dotenv()

H = os.getenv("MYSQL_HOST")
D = os.getenv("MYSQL_DB")
U = os.getenv("MYSQL_USER")
P = os.getenv("MYSQL_PASSWORD")

def assign_ticket(ticket_id: str, conn):
    try:
        cursor = conn.cursor()

        # Step 1: Get processed ticket category and triage
        cursor.execute("""
            SELECT category, triage FROM processed 
            WHERE ticket_id = %s LIMIT 1
        """, (ticket_id,))
        r = cursor.fetchone()
        if not r:
            print(f"[WARN] No processed ticket found with ID {ticket_id}")
            return False

        raw_category, raw_triage = r
        category = raw_category.strip()
        triage = raw_triage.strip()

        print(f"→ category: '{category}' | triage: '{triage}'")

        # Step 2: Query for matching employee
        cursor.execute("""
            SELECT employee_id FROM employee 
            WHERE TRIM(category) = %s AND TRIM(triage) = %s AND role = 'P'
            LIMIT 1
        """, (category, triage))
        id_find = cursor.fetchone()

        if not id_find:
            print(f"[WARN] No employee found for category='{category}', triage='{triage}'")
            return False

        employee_id = id_find[0]

        # Step 3: Get assigned_date
        cursor.execute("""
            SELECT assigned_date FROM main_table 
            WHERE ticket_id = %s LIMIT 1
        """, (ticket_id,))
        date_find = cursor.fetchone()
        assigned_date = date_find[0] if date_find else None

        # Step 4: Insert into assign table
        cursor.execute("""
            INSERT INTO assign (ticket_id, assigned_id, assigned_date)
            VALUES (%s, %s, %s)
        """, (ticket_id, employee_id, assigned_date))
        conn.commit()

        # Step 5: Log assignment
        cursor.execute("SELECT employee_name FROM employee WHERE employee_id = %s", (employee_id,))
        name = cursor.fetchone()[0]
        
        print('='*40,'\n',f"✅ Ticket {ticket_id} assigned to {name} (ID: {employee_id}) on {assigned_date}",'='*40,'\n',sep='')
        return True

    except Exception as e:
        print(f"[ERROR] Assignment failed for ticket {ticket_id}: {e}")
        print('='*40)
        return False
