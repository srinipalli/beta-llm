from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
from llm.models import Ticket, ProcessedTicket

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI API KEY IS NOT SET IN YOUR ENVIRONMENT. PLEASE SET IT. NOW.")
# Initialize Gemini via LangChain wrapper
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY)

# Define the expected response structure
response_schemas = [
    ResponseSchema(name="summary", description="Summary of the issue, in about 50 to 75 words. It should be concise and to-the-point, capturing the essence of the ticket. It should also be extremely easy to read and understand. Use acronyms like 'btw' or 'fyi' if necessary."),
    ResponseSchema(name="priority", description="L1, L2, L3, L4 ,L5. Think carefully what the priority is, based on the description of the ticket. It should be realistic based on real-life scenarios."),
    ResponseSchema(name="category", description="High-level ticket category: Process the tickets and assign any one among (Core Services & Product Services, Product Development & UX, Platform & Infrastructure, Data & System Management)"),
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

def process_ticket(ticket: Ticket) -> ProcessedTicket:
    prompt = prompt_template.format(
        title=ticket.title,
        description=ticket.description,
        module=ticket.module
    )
    try:
        response = llm.invoke(prompt)
        print("LLM raw response:")
        # print(response.content)
        print("¯"*50)
        parsed = output_parser.parse(response.content)
        print("Parsed response:")
        print("¯"*50)
        # print(parsed)
        
    except Exception as e:
        print(f"[ERROR] While processing ticket {ticket.ticket_id}: {e}")

    return ProcessedTicket(
        ticket_id=ticket.ticket_id,
        summary=parsed["summary"],
        priority=parsed["priority"],
        category=parsed["category"],
        solution=parsed["solution"]
    )
