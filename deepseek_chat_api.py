# repository: Tech-Watt-Deepseek-simple-Chatbot

from dotenv import load_dotenv
import os
import re


def chat(prompt):
    from langchain_groq import ChatGroq
    from langchain_core.output_parsers import StrOutputParser
    from langchain_community.document_loaders import TextLoader

    load_dotenv()
    api_key = os.getenv('API_KEY')
    model = "deepseek-r1-distill-llama-70b"
    deepseek = ChatGroq(api_key=api_key, model_name=model)

    parser = StrOutputParser()
    deepseek_chain = deepseek | parser


    prompt_init = "reply only listing 5 products followed by a breaf description of each of them that suits the following prompt: '"
    user_prompt = prompt
    prompt_end = "' if the request is not a request reguarding a product reply 'I'm sorry but this box is only for the suggestion of products, please insert a new prompt'"

    final_prompt = prompt_init + user_prompt +prompt_end
    res1 = deepseek_chain.invoke(final_prompt)

    category_prompt_init = "Categorise the product that i'm aking: '"
    category_end = "' reply only with one word"

    category_final_prompt = category_prompt_init + user_prompt + category_end
    print(deepseek_chain.invoke(category_final_prompt))

    return remove_thinking_tags(res1)


def remove_thinking_tags(input_string):
    cleaned_string = re.sub(r'<think>.*?</think>', '', input_string, flags=re.DOTALL)
    return cleaned_string