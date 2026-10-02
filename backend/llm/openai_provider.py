import json

from openai import OpenAI


STANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "decides_issue": {
            "type": "boolean",
        },
        "position_id": {
            "type": [
                "string",
                "null",
            ],
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "evidence_quote": {
            "type": [
                "string",
                "null",
            ],
        },
        "reason": {
            "type": "string",
        },
    },
    "required": [
        "decides_issue",
        "position_id",
        "confidence",
        "evidence_quote",
        "reason",
    ],
    "additionalProperties": False,
}


class OpenAIProvider:
    def __init__(
        self,
        model: str = "gpt-6.1-sol",
    ):
        self.model = model

        self.client = OpenAI()

    def generate_json(
        self,
        prompt: str,
    ) -> tuple[dict, dict]:

        response = self.client.responses.create(
            model=self.model,
            reasoning={
                "effort": "low",
            },
            input=prompt,
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "stance_classification",
                    "strict": True,
                    "schema": STANCE_SCHEMA,
                },
            },
            max_output_tokens=1500,
        )

        if response.status != "completed":
            raise RuntimeError(
                f"OpenAI response status: "
                f"{response.status}"
            )

        result = json.loads(
            response.output_text
        )

        usage = {
            "input_tokens": (
                response.usage.input_tokens
                if response.usage
                else None
            ),
            "output_tokens": (
                response.usage.output_tokens
                if response.usage
                else None
            ),
        }

        return result, usage