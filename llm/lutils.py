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
try:
    from models import Ticket, ProcessedTicket
    from rag import get_similar_ticket_context
except:
    from llm.models import Ticket, ProcessedTicket
    from llm.rag import get_similar_ticket_context
    
import logging
logging.basicConfig(filename='llm_logs.log', level=logging.INFO)
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI API KEY IS NOT SET IN YOUR ENVIRONMENT. PLEASE SET IT. NOW.")

# Initialize Gemini via LangChain wrapper
# in an async context we might need to ensure your LLM client
# can handle async calls or be instantiated within the async loop
# LangChain's ChatGoogleGenerativeAI is generally async-compatible.

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY)

# Define the expected response structure
response_schemas = [
    ResponseSchema(name="summary", description="Summary of the issue, in about 50 to 75 words. It should be concise and to-the-point, capturing the essence of the ticket. It should also be extremely easy to read and understand. Use acronyms like 'btw' or 'fyi' if necessary."),
    ResponseSchema(name="triage", description="""Assign the triage levels of L1, L2, L3, L4 or L5. 
                   according to the following criteria:
                   L1: Critical ticket of extreme priority. Assess the ticket ASAP.
                   L2: High priority: must be addressed very fast.
                   L3: Medium priority: must be dealt with sooner or later, avoid ignoring.
                   L4: Low priority: can be dealt with later
                   L5: Planning. Can ignore for now, re-assess the ticket later.
                   Only give L1, L2, L3, L4, L5. No additional words."""),
    ResponseSchema(name="category", description="Process the tickets and assign any one among (Frontend, Backend, Infrastructure, Data). It should be one word only, first letter uppercase."),
    ResponseSchema(name="solution", description="solution of 1 or 2 sentences that can address the issue directly and solve it in the most effective manner."),
    ResponseSchema(name="triage_reason", description="Correct reason for assigning the given triage level. In about 15 words. It must be concise and to-the-point."),
    ResponseSchema(name="category_reason", description="Correct reason for assigning the given category. In about 15 words. It must be concise and to-the-point. ")
]

output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

# Prompt template with formatting instructions
prompt_template = PromptTemplate(
    template="""
You are an expert IT support assistant. You recieve IT tickets daily. Given the following ticket details:

Title: {title}
Description: {description}
Return the following fields only:
{format_instructions}
""",
    input_variables=["title", "description"],
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
    )
        # Get RAG context
    context = get_similar_ticket_context(ticket.title, ticket.description)
    rag_augmented_prompt = (
        f"{prompt}\n\n"
        f"====================\n"
        f"📚 SIMILAR TICKET CONTEXT:\n"
        f"{context if context else '[No similar tickets found]'}"
    )
    logging.info("Raw prompt after augmenting:\n")
    logging.info(rag_augmented_prompt)
    logging.info("\n")
    try:
        # LangChain's .ainvoke() is for async calls
        response = await llm.ainvoke(rag_augmented_prompt)
        
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
            triage=parsed["triage"],
            category=parsed["category"],
            solution=parsed["solution"],
            triage_reason=parsed["triage_reason"],
            category_reason=parsed["category_reason"]
        )
    except Exception as e:
        logging.error(f"[ERROR] While processing ticket {ticket.ticket_id}: {e}\n")
        logging.error("+=+="*20)
        # Re-raise the exception if it's not a RateLimitExceeded for tenacity to handle
        # or if it's a critical error you don't want to retry.
        raise # Important: re-raise the exception for tenacity to catch
    
