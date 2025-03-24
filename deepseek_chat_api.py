from dotenv import load_dotenv
import os 
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import TextLoader

load_dotenv()
api_key = os.getenv('API_KEY')
model = "deepseek-r1-distill-llama-70b"
deepseek = ChatGroq(api_key=api_key, model_name=model)

parser = StrOutputParser()
deepseek_chain = deepseek | parser

print(deepseek_chain.invoke("Hello, how are you?"))