# llm/lutils.py
import asyncio
import aiohttp
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import json # To handle parsing the LLM response content if needed
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Assuming your models.py defines Ticket and ProcessedTicket
from llm.models import Ticket, ProcessedTicket

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI API KEY IS NOT SET IN YOUR ENVIRONMENT. PLEASE SET IT. NOW.")

# Initialize Gemini via LangChain wrapper
# Note: In an async context, you might need to ensure your LLM client
# can handle async calls or be instantiated within the async loop.
# LangChain's ChatGoogleGenerativeAI is generally async-compatible.
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY)

# Define the expected response structure
response_schemas = [
    ResponseSchema(name="summary", description="Summary of the issue, in about 50 to 75 words. It should be concise and to-the-point, capturing the essence of the ticket. It should also be extremely easy to read and understand. Use acronyms like 'btw' or 'fyi' if necessary."),
    ResponseSchema(name="priority", description="L1, L2, L3, L4 ,L5. Think carefully what the priority is, based on the description of the ticket. It should be realistic based on real-life scenarios."),
    ResponseSchema(name="category", description="High-level ticket category: Process the tickets and assign any one among (Core Services and Backend Services, Backend Development and UX, Platform and Infrastructure, Data and System Management)"),
    ResponseSchema(name="solution", description="solution of 1 or 2 sentences that can address the issue directly and solve it in the most effective manner.")
]

output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

# Prompt template with formatting instructions
prompt_template = PromptTemplate(
    template="""
You are an expert IT support assistant. Given the following ticket details:

Title: {title}
Description: {description}
Module: {module}

Return the following fields only:
{format_instructions}
""",
    input_variables=["title", "description", "module"],
    partial_variables={"format_instructions": output_parser.get_format_instructions()}
)

# Custom exception for rate limits (or other retriable errors)
class RateLimitExceeded(Exception):
    pass

# Decorator for exponential backoff on specific exceptions
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60), # Wait 4s, 8s, 16s, max 60s
    stop=stop_after_attempt(5), # Try up to 5 times
    retry=retry_if_exception_type(RateLimitExceeded) # Only retry if this specific exception
)
async def process_ticket_with_retry(ticket: Ticket) -> ProcessedTicket:
    prompt = prompt_template.format(
        title=ticket.title,
        description=ticket.description,
        module=ticket.module
    )
    try:
        # LangChain's .ainvoke() is for async calls
        response = await llm.ainvoke(prompt)
        
        # print("LLM raw response:")
        # print(response.content) # Enable for debugging
        
        # Check for rate limit or other issues from the LLM's response content
        # This is a simplification; you might need to parse the response content
        # more robustly to identify a rate limit message from the LLM itself,
        # or rely on HTTP status codes if using a direct API client like aiohttp.
        if "rate limit" in response.content.lower() or "quota exceeded" in response.content.lower():
            raise RateLimitExceeded(f"LLM indicated rate limit for ticket {ticket.ticket_id}")

        parsed = output_parser.parse(response.content)
        
        return ProcessedTicket(
            ticket_id=ticket.ticket_id,
            summary=parsed["summary"],
            priority=parsed["priority"],
            category=parsed["category"],
            solution=parsed["solution"]
        )
    except Exception as e:
        print(f"[ERROR] While processing ticket {ticket.ticket_id}: {e}")
        # Re-raise the exception if it's not a RateLimitExceeded for tenacity to handle
        # or if it's a critical error you don't want to retry.
        raise # Important: re-raise the exception for tenacity to catch