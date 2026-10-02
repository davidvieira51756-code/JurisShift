import os

from dotenv import load_dotenv

from backend.llm.ollama_provider import (
    OllamaProvider,
)
from backend.llm.openai_provider import (
    OpenAIProvider,
)
from backend.llm.provider import (
    LLMProvider,
)


load_dotenv()


def get_llm_provider() -> LLMProvider:
    provider = os.getenv(
        "LLM_PROVIDER",
        "ollama",
    ).lower()

    model = os.getenv(
        "LLM_MODEL",
        "qwen3.5:2b",
    )

    if provider == "ollama":
        return OllamaProvider(
            model=model,
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434",
            ),
        )

    if provider == "openai":
        return OpenAIProvider(
            model=model,
        )

    raise RuntimeError(
        f"Provider LLM não suportado: "
        f"{provider}"
    )