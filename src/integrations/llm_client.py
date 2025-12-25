# integrations/llm_client.py

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def make_openai_llm(
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
):
    """
    Returns a LangChain Runnable LLM compatible with:
    - LangChain pipe operator (|)
    - LangGraph
    - PromptTemplates
    """

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set in environment.")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )
