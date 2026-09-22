import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def make_llm(model="gpt-4o", temperature=0.7):
    if model == "gpt-4o":
        model = "gpt-4"
    llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=os.getenv("LITELLM_API_KEY"),
            openai_api_base=os.getenv("LITELLM_ENDPOINT"),
        )
    return llm


def make_embeddings_model():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("LITELLM_API_KEY"),
        openai_api_base=os.getenv("LITELLM_ENDPOINT"),
    )
    return embeddings

