"""OpenAI API wrapper with conversation memory."""

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-4o"
MAX_RETRIES = 2


@dataclass
class ConversationMemory:
    """Maintains conversation history and last parsed intent."""

    max_turns: int = 6
    history: list[dict[str, str]] = field(default_factory=list)
    last_intent: dict | None = None

    def add(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns :]

    def get_messages(self) -> list[dict[str, str]]:
        """Return conversation history for API context."""
        return list(self.history)

    def clear(self) -> None:
        """Reset conversation state."""
        self.history.clear()
        self.last_intent = None


class LLMClient:
    """OpenAI API client for intent parsing and response narration."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Copy .env.example to .env and add your key.")
        self.client = OpenAI(api_key=api_key)
        self.memory = ConversationMemory()

    def parse_intent(self, system_prompt: str, user_question: str) -> dict:
        """Parse a user question into a structured JSON intent.

        Args:
            system_prompt: Fully formatted intent parser prompt with schema context.
            user_question: The user's natural language question.

        Returns:
            Parsed intent dictionary.

        Raises:
            ValueError: If JSON parsing fails after retries.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            *self.memory.get_messages(),
            {"role": "user", "content": user_question},
        ]

        for attempt in range(MAX_RETRIES):
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            try:
                intent = json.loads(raw)
                self.memory.add("user", user_question)
                self.memory.add("assistant", raw)
                self.memory.last_intent = intent
                return intent
            except json.JSONDecodeError:
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f"Failed to parse LLM response as JSON: {raw}")

        raise ValueError("Unreachable: exhausted retries")

    def narrate(self, prompt: str) -> str:
        """Generate a business-language narration of query results.

        Args:
            prompt: Fully formatted narrator prompt with question and results.

        Returns:
            Natural language response string.
        """
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content

    def suggest_followups(self, prompt: str) -> list[str]:
        """Generate follow-up question suggestions.

        Args:
            prompt: Fully formatted suggestion prompt.

        Returns:
            List of 2 suggested follow-up questions.
        """
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[:2]
            if isinstance(data, dict) and "suggestions" in data:
                return data["suggestions"][:2]
            return []
        except (json.JSONDecodeError, KeyError):
            return []
