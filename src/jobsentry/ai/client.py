"""Anthropic Claude API client wrapper."""

import json

from anthropic import Anthropic

from jobsentry.config import get_settings


class AIClient:
    """Thin wrapper around the Anthropic SDK."""

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    def call(
        self,
        system: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Send a message to Claude and return the text response."""
        settings = get_settings()
        response = self._client.messages.create(
            model=model or settings.match_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        return response.content[0].text

    def call_json(
        self,
        system: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> dict | list:
        """Send a message and parse JSON from the response."""
        text = self.call(system, user_message, model, max_tokens)
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)

    @property
    def usage_summary(self) -> str:
        return (
            f"Tokens used — input: {self._total_input_tokens:,}, "
            f"output: {self._total_output_tokens:,}"
        )
