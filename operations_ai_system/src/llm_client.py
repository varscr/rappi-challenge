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
        import streamlit as st
        api_key = os.getenv("OPENAI_API_KEY")
        
        # Cloud-Ready API Key detection
        try:
            if not api_key and "OPENAI_API_KEY" in st.secrets:
                api_key = st.secrets["OPENAI_API_KEY"]
        except Exception:
            pass

        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Copy .env.example to .env and add your key.")
        self.client = OpenAI(api_key=api_key)
        self.memory = ConversationMemory()

    def parse_intent(self, system_prompt: str, user_question: str) -> dict:
        """Parse a user question into a structured JSON intent."""
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
                # Don't add to memory here, we add after execution/narration in QueryEngine
                return intent
            except json.JSONDecodeError:
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f"Failed to parse LLM response as JSON: {raw}")

        raise ValueError("Unreachable: exhausted retries")

    def narrate(self, prompt: str) -> str:
        """Generate a business-language narration of query results."""
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content

    def chat(self, user_question: str) -> str:
        """Answer meta-questions about the chat using history."""
        messages = [
            {"role": "system", "content": "Eres un asistente de Rappi. Responde preguntas sobre la conversación actual en español."},
            *self.memory.get_messages(),
            {"role": "user", "content": user_question},
        ]
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.5,
        )
        return response.choices[0].message.content

    def suggest_followups(self, prompt: str) -> list[str]:
        """Generate follow-up question suggestions."""
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
