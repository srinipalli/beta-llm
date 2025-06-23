import requests
import os
from dotenv import load_dotenv
import time
from llm.models import Ticket, ProcessedTicket

load_dotenv()
GEMINI_API_URL = os.getenv("GEMINI_API_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

REQUEST_INTERVAL_SECONDS = 2.50
last_request_time = 0


# HORSE 7
def process_ticket(ticket: Ticket) -> ProcessedTicket:
    global last_request_time

    current_time = time.time()
    time_since_last_request = current_time - last_request_time

    if time_since_last_request < REQUEST_INTERVAL_SECONDS:
        time_to_wait = REQUEST_INTERVAL_SECONDS - time_since_last_request
        print(f"Rate limit approaching. Waiting for {time_to_wait:.2f} seconds...")
        time.sleep(time_to_wait)

    prompt_text = f"""
    You are an expert IT support assistant, with expertise in all areas of IT. 
    Given the following ticket:
    Title: {ticket.title}
    Description: {ticket.description}
    Module: {ticket.module}

    Please return:
    - Summary (in about 50 to 75 words)
    - Priority (L1, L2 or L3. and if it is Critical, High, Medium, Low or Planning appropriately)
    - Category (Process the tickets and assign any one among (Core Services & Backend services, Product Development & UX, Platform & Infra, Data & System Management))
    - Solution (one sentence)
    
    make sure to provide expert responses, with accurate and concise information.
    do not say unnecessary things, other than the things I asked you for. Only generate what I asked you, in the same format(do not highlght anything).
    do not use highlighting, markdown or code blocks. Do not communicate with the user directly.
    """

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "contents": [
            {
                "parts": [{"text": prompt_text}]
            }
        ]
    }

    response = requests.post(GEMINI_API_URL, headers=headers, json=data)

    last_request_time = time.time()

    if response.status_code == 200:
        result = response.json()
        generated_text = result["candidates"][0]["content"]["parts"][0]["text"]
        print("Raw generated text from Gemini:")
        print(f"generated_text for ticket {ticket.ticket_id}")
        print("\n-------------------\n")

        pres = parse_gemini_response(generated_text)
        print("Parsed result:")
        print(f"parsed result for ticket {ticket.ticket_id}")
        print("\n-------------------\n")

        return ProcessedTicket(
            ticket_id=ticket.ticket_id,
            summary=pres["summary"],
            priority=pres["priority"],
            category=pres["category"],
            solution=pres["solution"]
        )
    else:
        if response.status_code == 429:
            print(f"Received 429 Too Many Requests. Try increasing interval above 5s or consider batching requests.")
        raise Exception(f"Gemini API failed: {response.status_code} {response.text}")

def parse_gemini_response(text: str) -> dict:
    result = {
        'summary': '',
        'priority': '',
        'category': '',
        'solution': ''
    }

    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line.startswith('-') or ':' not in line:
            continue
        key, value = line[1:].strip().split(':', 1)
        key = key.strip().lower()
        value = value.strip()

        if key == 'summary':
            result['summary'] = value
        elif key == 'priority':
            result['priority'] = value
        elif key == 'category':
            result['category'] = value
        elif key == 'solution':
            result['solution'] = value
    return result
