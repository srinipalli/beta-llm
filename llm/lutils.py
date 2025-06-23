# llm/lutils.py

import asyncio
import aiohttp
import os
import json
import logging
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Try both module paths for RAG utilities and models
try:
    from models import Ticket, ProcessedTicket
    from rag import get_similar_ticket_context
except ImportError:
    from llm.models import Ticket, ProcessedTicket
    from llm.rag import get_similar_ticket_context

# Configure logging to file
logging.basicConfig(filename='llm_logs.log', level=logging.INFO)  # Python logging docs [4]

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI API KEY IS NOT SET IN YOUR ENVIRONMENT. PLEASE SET IT. NOW.")  # Env var checking [1]

# Initialize Langfuse tracing client and global callback handler
langfuse         = get_client()                           # Langfuse Python SDK v3 [1]
global_handler   = CallbackHandler()                      # Generic handler for nested spans

# Initialize async LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GEMINI_API_KEY
)

# Define expected response structure using LangChain’s StructuredOutputParser [2]
response_schemas = [
    ResponseSchema(name="summary",    description="Summary of the issue, in 50–75 words. Use acronyms like 'btw' or 'fyi' if needed."),
    ResponseSchema(name="triage",     description="Assign L1–L5 levels only. No extra text."),
    ResponseSchema(name="category",   description="One of Frontend, Backend, Infrastructure, Data."),
    ResponseSchema(name="solution",   description="Solution in 1–2 sentences addressing the issue."),
    ResponseSchema(name="triage_reason",   description="15-word reason for triage level."),
    ResponseSchema(name="category_reason", description="15-word reason for category.")
]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

# Prompt template with formatting instructions
prompt_template = PromptTemplate(
    template="""
You are an expert IT support assistant. You receive IT tickets daily. Given:

Title: {title}
Description: {description}

Return only these fields:
{format_instructions}
""",
    input_variables=["title","description"],
    partial_variables={"format_instructions": output_parser.get_format_instructions()}
)

# Custom exception for rate limits
class RateLimitExceeded(Exception):
    pass

# Retry decorator with exponential backoff on RateLimitExceeded [3]
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitExceeded)
)
async def process_ticket_with_retry(ticket: Ticket) -> ProcessedTicket:
    """
    Process a support ticket: build prompt, augment via RAG context,
    call Gemini async, parse response, and trace all steps in Langfuse.
    """
    # Format base prompt
    base_prompt = prompt_template.format(
        title=ticket.title,
        description=ticket.description
    )

    # Retrieve similar ticket context (RAG)
    context = get_similar_ticket_context(ticket.title, ticket.description)
    full_prompt = (
        f"{base_prompt}\n\n"
        f"====================\n"
        f"📚 SIMILAR TICKET CONTEXT:\n"
        f"{context or '[No similar tickets found]'}"
    )

    # Log raw prompt for debug
    logging.info("Raw prompt after augmenting:\n%s\n", full_prompt)

    # Start top‐level span for this ticket processing
    with langfuse.start_as_current_span(name="process-ticket") as span:
        # Record input data
        span.update_trace(
            input={
                "ticket_id": ticket.ticket_id,
                "title":     ticket.title,
                "description": ticket.description,
                "full_prompt": full_prompt
            },
            user_id="system",
            session_id=f"ticket-{ticket.ticket_id}"
        )

        # Obtain a handler scoped to this span
        handler = CallbackHandler()

        # Propagates I/O to this span [1]

        try:
            # Invoke the LLM asynchronously with span‐scoped handler
            response = await llm.ainvoke(full_prompt, config={"callbacks":[handler]})
            raw_output = response.content.strip()

            # Trace raw LLM output
            span.update_trace(output={"raw_output": raw_output})

            # Detect rate limit messages
            low = raw_output.lower()
            if "rate limit" in low or "quota exceeded" in low:
                raise RateLimitExceeded(f"Rate limit for ticket {ticket.ticket_id}")

            # Parse structured output
            parsed = output_parser.parse(raw_output)

            # Trace parsed fields
            span.update_trace(output={"parsed": parsed})

            # Return a structured ProcessedTicket
            return ProcessedTicket(
                ticket_id       = ticket.ticket_id,
                summary         = parsed["summary"],
                triage          = parsed["triage"],
                category        = parsed["category"],
                solution        = parsed["solution"],
                triage_reason   = parsed["triage_reason"],
                category_reason = parsed["category_reason"]
            )

        except Exception as e:
            # Log and trace any errors
            logging.error("[ERROR] While processing ticket %s: %s", ticket.ticket_id, e)
            span.update_trace(output={"error": str(e)})
            raise  # Re-raise for Tenacity to handle retry