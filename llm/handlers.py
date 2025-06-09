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

def process_ticket(ticket: Ticket) -> ProcessedTicket:
    global last_request_time

    current_time = time.time()
    time_since_last_request = current_time - last_request_time

    if time_since_last_request < REQUEST_INTERVAL_SECONDS:
        time_to_wait = REQUEST_INTERVAL_SECONDS - time_since_last_request
        print(f"Rate limit approaching. Waiting for {time_to_wait:.2f} seconds...")
        time.sleep(time_to_wait)

    prompt_text = f"""
    You are an expert IT support assistant.
    Given the following ticket:
    Title: {ticket.title}
    Description: {ticket.description}
    Module: {ticket.module}

    Please return:
    - Summary (in about 50 to 75 words)
    - Priority (L1, L2 or L3. and if it is Critical, High, Medium, Low or Planning appropriately)
    - Category (Process the tickets and assign any one among (Core Services & Backend systems, Product Development & UX, Platform & Infra, Data & System Management))
    - Sub-Category (Process the tickets and assign any one among (Backend Engineering,Payments Team,Search Platform,Messaging Infrastructure,Release Engineering,Infrastructure,Database Administration,Mobile Development,Data Engineering,Frontend/UX,Network Security,Internal Services,Cloud Engineering,System Operations,DevOps,Release Engineering,Partnership Integrations,Frontend Engineering,Platform Operations,Authentication Services))
    - Assigned Employee (Just the name. Do not repeat if aldready assigned)
    - Solution (one sentence)

    do not say unnecessary things, other than the things I asked you for. Only generate what I asked you, in the same format(do not highlght anything).
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
        print(generated_text)
        print("\n-------------------\n")

        pres = parse_gemini_response(generated_text)
        print("Parsed result:")
        print(pres)
        print("\n-------------------\n")

        return ProcessedTicket(
            ticket_id=ticket.ticket_id,
            summary=pres["summary"],
            priority=pres["priority"],
            category=pres["category"],
            sub_category=pres["sub_category"],
            assigned_to=pres["assigned_to"],
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
        'sub_category': '',
        'assigned_to': '',
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
        elif key == 'sub-category':
            result['sub_category'] = value
        elif key == 'assigned employee':
            result['assigned_to'] = value[:200]
        elif key == 'solution':
            result['solution'] = value

    return result
