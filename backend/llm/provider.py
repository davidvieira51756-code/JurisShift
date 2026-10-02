from typing import Protocol


class LLMProvider(Protocol):
    model: str

    def generate_json(
        self,
        prompt: str,
    ) -> tuple[dict, dict]:
        ...