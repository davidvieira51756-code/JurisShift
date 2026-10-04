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
        schema: dict | None = None,
        schema_name: str | None = None,
    ) -> tuple[dict, dict]:
        effective_schema = (
            schema
            if schema is not None
            else STANCE_SCHEMA
        )

        effective_name = (
            schema_name
            or "stance_classification"
        )

        response = (
            self.client.responses.create(
                model=self.model,
                reasoning={
                    "effort": "low",
                },
                input=prompt,
                text={
                    "verbosity": "low",
                    "format": {
                        "type": "json_schema",
                        "name": effective_name,
                        "strict": True,
                        "schema": effective_schema,
                    },
                },
                max_output_tokens=1500,
            )
        )

        if (
            response.status
            != "completed"
        ):
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