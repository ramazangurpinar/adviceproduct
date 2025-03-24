from dotenv import load_dotenv
import os
import re

# repository: Tech-Watt-Deepseek-simple-Chatbot
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



    final_prompt = f"""
                    FOLLOW THESE RULES STRICTLY:
                    1. IF the user asks for product recommendations, reply ONLY with a list of 5 products + a 10-word description each.  
                    2. IF the request is NOT about products, reply EXACTLY with:  
                    "I am sorry but this box is only for the suggestion of products, please insert a new prompt".  

                USER PROMPT: '{prompt}'
                """
    print(final_prompt)
    res1 = deepseek_chain.invoke(final_prompt)

    category_prompt_init = "Categorise the product that i'm aking: '"
    category_end = "' reply only with one word in english"

    category_final_prompt = category_prompt_init + prompt + category_end
    print(deepseek_chain.invoke(category_final_prompt))

    return remove_thinking_tags(res1)


def remove_thinking_tags(input_string):
    cleaned_string = re.sub(r'<think>.*?</think>', '', input_string, flags=re.DOTALL)
    return cleaned_string