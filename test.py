import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI  # Not `ChatOpenAI`

load_dotenv()

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version=os.getenv("AZURE_API_VERSION"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0.2
)

response = llm.invoke("Say hello from Azure OpenAI!")
print("✅ Azure Response:", response.content)
