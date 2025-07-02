import asyncio
import os
import logging
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_openai import AzureChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Try both module paths
try:
    from models import Ticket, ProcessedTicket
    from rag import get_similar_ticket_context
except ImportError:
    from llm.models import Ticket, ProcessedTicket
    from llm.rag import get_similar_ticket_context

# Logging
logging.basicConfig(filename='llm_logs.log', level=logging.INFO)

# Load env variables
load_dotenv()
AZURE_API_KEY     = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_BASE    = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT  = os.getenv("AZURE_DEPLOYMENT_NAME")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01")

if not all([AZURE_API_KEY, AZURE_API_BASE, AZURE_DEPLOYMENT]):
    raise ValueError("Missing Azure OpenAI credentials or configuration in .env")

# Langfuse Tracing
langfuse = get_client()
global_handler = CallbackHandler()

# Azure LLM
llm = AzureChatOpenAI(
    azure_endpoint=AZURE_API_BASE,
    deployment_name=AZURE_DEPLOYMENT,  # 👈 e.g. "gpt-4-1-mini"
    api_version=AZURE_API_VERSION,
    api_key=AZURE_API_KEY,
    temperature=0.2,
)

# Output format schema
response_schemas = [
    ResponseSchema(name="summary", description="50–75 word summary of the issue."),
    ResponseSchema(name="triage", description="Assign priority: L1 to L5 only. L1 is the basic level(least prioritized), L2 is the next level to L1 (low priorirized), L3 is the next level to L2 (medium priority), L4 is a high prioritized ticket and L5 is a critical ticket(most prioritized) . No extra text."),
    ResponseSchema(name="category", description="Choose one: Payroll, Leave Management, Authentication, Reporting, Time Tracking, Notifications, User Management, Performance, Recruitment, Attendance, Dashboard, Globalization, Directory, Help, Leave, UI/UX, Documents, Integrations."),
    ResponseSchema(name="solution", description="Provide a 1–2 sentence solution."),
    ResponseSchema(name="triage_reason", description="15-word explanation for triage level."),
    ResponseSchema(name="category_reason", description="15-word explanation for category.")
]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

# Prompt template
prompt_template = PromptTemplate(
    template="""
You are an expert IT support assistant. Suppose you're given a ticket like this:

Title: {title}
Description: {description}

Return only these fields:
{format_instructions}
""",
    input_variables=["title", "description"],
    partial_variables={"format_instructions": output_parser.get_format_instructions()}
)

# Custom Exception
class RateLimitExceeded(Exception):
    pass

# Retry logic with backoff
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(RateLimitExceeded)
)
async def process_ticket_with_retry(ticket: Ticket) -> ProcessedTicket:
    base_prompt = prompt_template.format(
        title=ticket.title,
        description=ticket.description
    )

    context = get_similar_ticket_context(ticket.title, ticket.description)
    full_prompt = (
        f"{base_prompt}\n\n"
        f"====================\n"
        f"📚 SIMILAR TICKET CONTEXT:\n"
        f"{context or '[No similar tickets found]'}"
    )

    logging.info("Prompt for ticket %s:\n%s", ticket.ticket_id, full_prompt)

    with langfuse.start_as_current_span(name="process-ticket") as span:
        span.update_trace(
            input={
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "description": ticket.description,
                "full_prompt": full_prompt
            },
            user_id="system",
            session_id=f"ticket-{ticket.ticket_id}"
        )

        handler = CallbackHandler()

        try:
            response = await llm.ainvoke(full_prompt, config={"callbacks": [handler]})
            raw_output = response.content.strip()
            span.update_trace(output={"raw_output": raw_output})

            if "rate limit" in raw_output.lower() or "quota exceeded" in raw_output.lower():
                raise RateLimitExceeded(f"Rate limit hit for ticket {ticket.ticket_id}")

            parsed = output_parser.parse(raw_output)
            span.update_trace(output={"parsed": parsed})

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
            logging.error("[ERROR] Failed processing ticket %s: %s", ticket.ticket_id, e)
            span.update_trace(output={"error": str(e)})
            raise
