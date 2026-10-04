from typing import Protocol


class LLMProvider(Protocol):
    model: str

    def generate_json(
        self,
        prompt: str,
        schema: dict | None = None,
        schema_name: str | None = None,
    ) -> tuple[dict, dict]:
        ...