from langchain_sarvam import ChatSarvam
from .Settings import gemini


llm = ChatSarvam(
    model="sarvam-105b",
    api_key=gemini(),
    temperature=0,
    reasoning_effort="low",
    max_tokens=8192,
    max_retries=5,
)

fast_llm = ChatSarvam(
    model="sarvam-105b-conversations",
    api_key=gemini(),
    temperature=0,
    max_tokens=4096,
    max_retries=3,
)
