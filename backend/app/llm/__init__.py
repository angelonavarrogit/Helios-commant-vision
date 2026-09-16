"""HELIOS BRAIN — LLM provider abstraction (Ollama default, OpenAI opt-in).

See ADR-003 and ADR-016. The default provider is selected from configuration
(``LLM_PROVIDER``) via :func:`get_llm_provider`.
"""

from app.config import get_settings
from app.llm.base import LLMError, LLMProvider
from app.llm.fake import FakeLLMProvider
from app.llm.ollama import OllamaProvider

__all__ = [
    "FakeLLMProvider",
    "LLMError",
    "LLMProvider",
    "OllamaProvider",
    "get_llm_provider",
]


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider instance.

    Ollama by default (local, private). OpenAI is imported lazily only when
    selected, so its dependency stays optional.
    """
    provider = get_settings().llm_provider
    if provider == "openai":
        from app.llm.openai import OpenAIProvider

        return OpenAIProvider()
    return OllamaProvider()
