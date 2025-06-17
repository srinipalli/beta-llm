import mysql.connector
import asyncio
from llm.lutils import process_ticket_with_retry as _base_process_ticket, RateLimitExceeded
from llm.models import Ticket
from llm.assign import assign_ticket
import os
import time
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

# --- DB Connection ---
conn = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST"),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DB")
)

# --- Config ---
MAX_CONCURRENT_LLM_REQUESTS = 5
MAX_REQUESTS_PER_MINUTE = 60
MIN_INTERVAL_BETWEEN_CALLS = 60 / MAX_REQUESTS_PER_MINUTE
last_call_time = 0
rate_limiter_lock = asyncio.Lock()

# --- Define additional retryable exceptions ---
class DeadlineExceeded(Exception): pass
class TemporaryServerError(Exception): pass

# --- Universal retry wrapper ---
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((RateLimitExceeded, DeadlineExceeded, TemporaryServerError))
)
async def process_ticket_with_retry(ticket):
    try:
        return await _base_process_ticket(ticket)
    except Exception as e:
        if "504" in str(e) or "deadline" in str(e).lower():
            raise DeadlineExceeded(str(e))
        if "503" in str(e) or "unavailable" in str(e).lower() or "timeout" in str(e).lower():
            raise TemporaryServerError(str(e))
        raise

# --- Single ticket processor ---
async def process_and_store_single_ticket(ticket: Ticket, semaphore: asyncio.Semaphore, db_conn):
    global last_call_time

    async with semaphore:
        async with rate_limiter_lock:
            elapsed = time.time() - last_call_time
            wait_time = max(0, MIN_INTERVAL_BETWEEN_CALLS - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            last_call_time = time.time()

        try:
            print(f"🚀 Processing ticket: {ticket.ticket_id}")
            processed = await process_ticket_with_retry(ticket)
            print(f"✅ Processed ticket {ticket.ticket_id}")

            cursor = db_conn.cursor()
            cursor.execute("""
                INSERT INTO processed (ticket_id, summary, priority, category, solution)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    summary=VALUES(summary),
                    priority=VALUES(priority),
                    category=VALUES(category),
                    solution=VALUES(solution)
            """, (
                processed.ticket_id,
                processed.summary,
                processed.priority.strip(),
                processed.category.strip(),
                processed.solution
            ))
            db_conn.commit()
            print(f"📥 Inserted/Updated processed ticket {processed.ticket_id}")

            assigned = assign_ticket(processed.ticket_id, db_conn)
            if not assigned:
                print(f"⚠️ [WARN] Ticket {processed.ticket_id} not assigned.")

            return processed

        except Exception as e:
            print(f"❌ [ERROR] Processing failed for {ticket.ticket_id}: {e}")
            return None

# --- Retry loop for all tickets ---
async def process_all_tickets():
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM main_table")
    raw_tickets = cursor.fetchall()

    tickets = [
        Ticket(
            ticket_id=row[0],
            severity=row[1],
            module=row[2],
            title=row[3],
            description=row[4] or "",
            priority=row[5] or "",
            status=row[6],
            category=row[7] or "",
            reported_date=row[8],
            assigned_to=row[9] or "",
            assigned_date=row[10]
        ) for row in raw_tickets
    ]

    print(f"\n🧾 Found {len(tickets)} total tickets in main_table.")
    if input("Process ALL tickets? (Y/N): ").strip().lower() != "y":
        print("❌ Aborted.")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_REQUESTS)
    remaining = tickets
    total_attempted = 0
    attempt = 1

    while remaining:
        print(f"\n🔄 Attempt #{attempt} - Processing {len(remaining)} tickets...")
        start_time = time.time()

        tasks = [
            process_and_store_single_ticket(ticket, semaphore, conn)
            for ticket in remaining
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        failed = [
            ticket for ticket, result in zip(remaining, results)
            if result is None or isinstance(result, Exception)
        ]
        succeeded = len(remaining) - len(failed)
        total_attempted += len(remaining)

        print(f"✅ {succeeded} succeeded | ❌ {len(failed)} failed in attempt #{attempt}")
        print(f"⏱ Time taken: {time.time() - start_time:.2f} sec")

        remaining = failed
        attempt += 1

    print(f"\n🎉 All {total_attempted} tickets processed and assigned successfully!")

# --- Entry point ---
if __name__ == "__main__":
    asyncio.run(process_all_tickets())
    conn.close()
