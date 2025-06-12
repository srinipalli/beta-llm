# process_tickets_main.py
import mysql.connector
import asyncio
from llm.lutils import process_ticket_with_retry, RateLimitExceeded
from llm.models import Ticket, ProcessedTicket
import os
import time
from llm.assign import assign_ticket # Assuming assign_ticket can work with just ticket_id and conn
from dotenv import load_dotenv

load_dotenv()

# --- Database Setup (Keep as is, but ensure connection is handled properly in async context) ---
# For simplicity, we'll use a single connection for now.
# For truly high concurrency, you might need a connection pool (e.g., using `aiomysql`).
# But for processing N concurrent LLM requests, one connection is often sufficient if not blocking.
conn = mysql.connector.connect(
    host = os.getenv("MYSQL_HOST"),
    user = os.getenv("MYSQL_USER"),
    password = os.getenv("MYSQL_PASSWORD"),
    database = os.getenv("MYSQL_DB")
)

# --- Configuration ---
MAX_CONCURRENT_LLM_REQUESTS = 5 # Adjust this based on your LLM's rate limits and your system's capacity
DATABASE_BATCH_SIZE = 10 # How many processed tickets to accumulate before inserting into DB

# --- Asynchronous Processing Logic ---
async def process_and_store_single_ticket(ticket: Ticket, semaphore: asyncio.Semaphore, db_cursor, db_conn):
    async with semaphore: # Acquire a semaphore slot before making an LLM call
        try:
            print(f"Attempting to process ticket: {ticket.ticket_id}")
            processed = await process_ticket_with_retry(ticket)
            print(f"Processed ticket {ticket.ticket_id}: Summary - {processed.summary[:50]}...")
            return processed
        except RateLimitExceeded as e:
            print(f"Rate limit hit for ticket {ticket.ticket_id}, retrying later: {e}")
            return None # Indicate failure, will be retried by tenacity
        except Exception as e:
            print(f"[ERROR] Critical failure for ticket {ticket.ticket_id}: {e}")
            return None # Indicate failure

async def main():
    cursor = conn.cursor()
    cursor.execute('SELECT * from main_table;')
    db_tickets_raw = cursor.fetchall()
    print(f"{len(db_tickets_raw)} tickets are now being fetched from the database.")
    
    # Convert raw DB rows to Ticket objects
    tickets_to_process = []
    for i in db_tickets_raw:
        tickets_to_process.append(Ticket(
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
        ))

    print("Time to start the loop to process the tickets :D")
    consent = input("Do you want to start processing? (Y or N): ")

    if consent.lower() != "y":
        print("Cancelled by user.")
        conn.close()
        return

    start_time = time.time()
    
    # Use an asyncio.Semaphore to limit concurrent LLM requests
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_REQUESTS)
    
    processed_tickets_buffer = []
    
    # Create tasks for all tickets
    processing_tasks = [
        process_and_store_single_ticket(t, semaphore, cursor, conn) 
        for t in tickets_to_process
    ]

    # Run tasks concurrently and collect results
    # `asyncio.as_completed` yields tasks as they complete, useful for processing results as they come
    for task in asyncio.as_completed(processing_tasks):
        processed_ticket = await task
        if processed_ticket:
            processed_tickets_buffer.append(processed_ticket)
            
            # Batch insertion into DB
            if len(processed_tickets_buffer) >= DATABASE_BATCH_SIZE:
                print(f"Inserting {len(processed_tickets_buffer)} processed tickets into DB...")
                try:
                    insert_query = "INSERT INTO processed (ticket_id, summary, priority, category, solution) VALUES (%s, %s, %s, %s, %s)"
                    values = [(pt.ticket_id, pt.summary, pt.priority, pt.category, pt.solution) for pt in processed_tickets_buffer]
                    cursor.executemany(insert_query, values)
                    conn.commit()
                    print(f"Successfully inserted batch into 'processed' table.")
                    
                    # After successful processing and insertion, proceed with assignment
                    for pt in processed_tickets_buffer:
                        print(f"Attempting to assign ticket {pt.ticket_id}...")
                        try:
                            # You might need to make assign_ticket async or ensure it's quick/non-blocking
                            # or run it in a separate thread/process if it involves blocking I/O.
                            # For simplicity, assuming assign_ticket is quick or handles its own blocking.
                            assign_ticket(pt.ticket_id, conn) 
                            print(f'Ticket {pt.ticket_id} is assigned.')
                        except Exception as e:
                            print(f'[ERROR] Failed to assign ticket {pt.ticket_id}: {e}')
                    
                except Exception as e:
                    print(f"[ERROR] Failed to insert batch into 'processed' table: {e}")
                finally:
                    processed_tickets_buffer = [] # Clear buffer regardless of success/failure
        # else: A 'None' return means a retry or critical failure, handled by tenacity/error logging

    # Process any remaining tickets in the buffer after the loop finishes
    if processed_tickets_buffer:
        print(f"Inserting remaining {len(processed_tickets_buffer)} processed tickets into DB...")
        try:
            insert_query = "INSERT INTO processed (ticket_id, summary, priority, category, solution) VALUES (%s, %s, %s, %s, %s)"
            values = [(pt.ticket_id, pt.summary, pt.priority, pt.category, pt.solution) for pt in processed_tickets_buffer]
            cursor.executemany(insert_query, values)
            conn.commit()
            print(f"Successfully inserted remaining batch into 'processed' table.")
            
            for pt in processed_tickets_buffer:
                print(f"Attempting to assign remaining ticket {pt.ticket_id}...")
                try:
                    assign_ticket(pt.ticket_id, conn)
                    print(f'Ticket {pt.ticket_id} is assigned.')
                except Exception as e:
                    print(f'[ERROR] Failed to assign remaining ticket {pt.ticket_id}: {e}')

        except Exception as e:
            print(f"[ERROR] Failed to insert remaining batch into 'processed' table: {e}")

    # Final check for unassigned tickets (from original code, kept for completeness)
    print("\nPerforming final assignment check for processed but unassigned tickets...")
    cursor.execute('SELECT ticket_id FROM processed;')
    processed_ids = {item[0] for item in cursor.fetchall()} # Use set for efficient lookup
    cursor.execute('SELECT ticket_id FROM assign;')
    assigned_ids = {item[0] for item in cursor.fetchall()}

    unassigned_processed_tickets = processed_ids - assigned_ids
    if unassigned_processed_tickets:
        print(f'{len(unassigned_processed_tickets)} tickets were processed but not assigned. Retrying...')
        for ticket_id in unassigned_processed_tickets:
            print(f'Retrying assignment for ticket {ticket_id}...')
            try:
                assign_ticket(ticket_id, conn)
                print(f'Ticket {ticket_id} is now assigned.')
            except Exception as e:
                print(f'[ERROR] Failed to assign ticket {ticket_id} again: {e}')
    else:
        print("All processed tickets are assigned.")

    end_time = time.time()
    print(f"\nProcessing complete. Total time taken: {end_time - start_time:.2f} seconds.")
    
    conn.close() # Close connection when all is done

if __name__ == "__main__":
    asyncio.run(main())