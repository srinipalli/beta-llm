import requests
from config import GEMINI_API_KEY, GEMINI_API_URL
from models import Ticket, ProcessedTicket

def process_ticket(ticket: Ticket) -> ProcessedTicket:
    prompt_text = f"""
    You are an expert IT support assistant.
    Given the following ticket:
    Title: {ticket.title}
    Description: {ticket.description}
    Module: {ticket.module}

    Please return:
    - Summary
    - Priority (Just say L1, L2 or L3.)
    - Category (one word)
    - Sub-category (one word)
    - Assigned Employee (Just the name)
    - Reason for assignment (one sentence)

    do not say unnecessary things, other than the things I asked you for. Only generate what I asked you, each not more than one sentence. 
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

    if response.status_code == 200:
        result = response.json()

        # Extract the generated text from the response
        generated_text = (result["candidates"][0]["content"]["parts"][0]["text"])
        print("Raw generated text from Gemini:")
        print(generated_text)
        print("\n-------------------\n")
        
        # You must now parse that text into structured fields
        pres = parse_gemini_response(generated_text)
        print("Parsed result:")
        print(pres)
        print("\n-------------------\n")
        # For now, use placeholders or write parsing logic
        return ProcessedTicket(
            ticket_id=ticket.ticket_id,
            summary=pres["summary"],
            priority=pres["priority"],
            category=pres["category"],
            sub_category=pres["sub_category"],
            assigned_to=pres["assigned_to"],
            reason=pres["reason"]
        )
    else:
        raise Exception(f"Gemini API failed: {response.status_code} {response.text}")

import re

def parse_gemini_response(text: str) -> dict:
    result = {
        'summary': '',
        'priority': '',
        'category': '',
        'sub_category': '',
        'assigned_to': '',
        'reason': ''
    }

    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()

        # Skip if not a key-value line
        if not line.startswith('-') or ':' not in line:
            continue

        # Remove leading "-" and split into key and value
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
            result['assigned_to'] = value[:200]  # truncate if too long
        elif key == 'reason for assignment':
            result['reason'] = value

    return result

