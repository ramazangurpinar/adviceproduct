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
                    Context: you are a chatbot that helps users find products.
                    1. Provide a small overview of 200 words maximum on what are the imprtant metrics to consider when buying the 
                    kind of product you are asked.
                    2. IF the user asks for product recommendations, reply ONLY with maximum of 5 products + a small description of 
                    maximum 100 words each.  
                    3. IF the request is NOT about products, reply EXACTLY with:  
                    "I am sorry but this box is only for the suggestion of products, please insert a new prompt.".
                    4. All the product suggestion should have the following format: "Separator - Product name - Description" Where Sepearator = "querty"

                    USER PROMPT: '{prompt}'
                    """
    res_string = remove_thinking_tags(deepseek_chain.invoke(final_prompt))
    res1 = separate_bot_messages(res_string)
    print(res1)
    #res1 = extract_products(res1)
    #print(res1)
    if res1 != "I am sorry but this box is only for the suggestion of products, please insert a new prompt.":
        category_prompt_init = "Categorise the product that i'm aking: '"
        category_end = "' reply only with one word in english"

        category_final_prompt = category_prompt_init + prompt + category_end
        res2 = deepseek_chain.invoke(category_final_prompt)
        res2 = remove_thinking_tags(res2)

    return res1, res2


def remove_thinking_tags(input_string):
    cleaned_string = re.sub(r'<think>.*?</think>', '', input_string, flags=re.DOTALL)
    return cleaned_string

def separate_bot_messages(response):
    print(response) ### COMMENT LATER
    l = [segment.strip().replace("querty", "") for segment in response.split("querty") if segment.strip()]
    print(l) ### COMMENT LATER
    return l
