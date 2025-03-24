# repository: Tech-Watt-Deepseek-simple-Chatbot

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


prompt_init = "List 5 products that suits the following prompt: '"
prompt_end = "' if the request is not a request reguarding a product reply 'I'm sorry but this box is only for the suggestion of products, please insert a new prompt'"

print(deepseek_chain.invoke("Give me an advice on what phone can i buy with a budget of 200 pounds"))
