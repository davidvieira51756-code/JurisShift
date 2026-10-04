import json

import httpx


class OllamaProvider:
    def __init__(
        self,
        model: str = "qwen3.5:2b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = (
            base_url.rstrip("/")
        )

    def generate_json(
        self,
        prompt: str,
        schema: dict | None = None,
        schema_name: str | None = None,
    ) -> tuple[dict, dict]:
        del schema_name

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "think": False,
                "format": (
                    schema
                    if schema is not None
                    else "json"
                ),
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "options": {
                    "temperature": 0,
                    "num_ctx": 4096,
                },
            },
            timeout=180,
        )

        response.raise_for_status()

        payload = (
            response.json()
        )

        content = payload[
            "message"
        ][
            "content"
        ]

        result = json.loads(
            content
        )

        usage = {
            "input_tokens": (
                payload.get(
                    "prompt_eval_count"
                )
            ),
            "output_tokens": (
                payload.get(
                    "eval_count"
                )
            ),
        }

        return result, usage