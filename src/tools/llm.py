"""
LLM factory. Returns a LangChain BaseChatModel that satisfies the
LanguageModel Protocol used by all agents.

Supported model strings:
  deepseek-chat       — DeepSeek Chat (fast, low cost, routine tasks)
  deepseek-reasoner   — DeepSeek R1 (slower, better reasoning, drafts)
  claude              — Claude claude-sonnet-4-6 (high-stakes writing)
"""
import logging
from src.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


def get_llm(model: str = "deepseek-chat"):
    """
    Return a LangChain chat model instance.
    All returned objects satisfy the LanguageModel Protocol (have .invoke(messages)).
    """
    if model.startswith("deepseek"):
        from langchain_openai import ChatOpenAI
        model_name = "deepseek-reasoner" if model == "deepseek-reasoner" else "deepseek-chat"
        return ChatOpenAI(
            model=model_name,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.3,
        )
    elif model == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
            max_tokens=8192,
        )
    else:
        raise ValueError(f"Unknown model '{model}'. Use: deepseek-chat, deepseek-reasoner, claude")
