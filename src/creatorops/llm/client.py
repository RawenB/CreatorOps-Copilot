"""LLM clients. Every client has the same `chat` method:

    chat(messages, tools=None, json_mode=False) -> {"content": str, "tool_calls": [...], "usage": {...}}

- messages use the usual format: {"role": "system"|"user"|"assistant"|"tool", "content": ...}
- tools are JSON schemas in the OpenAI / Ollama "function" format
- tool_calls is a list of {"name": ..., "arguments": {...}}
"""

import json
import re

import httpx

from creatorops.config import settings


class OllamaClient:
    def __init__(self, model: str | None = None, url: str | None = None):
        self.model = model or settings.ollama_model
        self.url = (url or settings.ollama_url).rstrip("/")
        self.http = httpx.Client(timeout=300)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, json_mode=False):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,  # qwen3 "thinking" is slow and not needed here
            "options": {
                "temperature": settings.temperature,
                "num_ctx": 16384,
                "seed": settings.seed,
            },
        }
        if tools:
            body["tools"] = tools
        if json_mode:
            body["format"] = "json"
        r = self.http.post(f"{self.url}/api/chat", json=body)
        r.raise_for_status()
        data = r.json()
        message = data["message"]
        tool_calls = [
            {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or {}}
            for c in message.get("tool_calls") or []
        ]
        return {
            "content": strip_thinking(message.get("content") or ""),
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        }


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks if the model still produces them."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class FakeLLM:
    """Deterministic fake used in tests and CI.

    - json_mode (router): picks a route with simple keywords
    - with tools: calls the first useful tool once, then answers citing source [1]
    """

    def __init__(self):
        self.calls = []

    def chat(self, messages, tools=None, json_mode=False):
        self.calls.append(messages)
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        question = next(m["content"] for m in reversed(messages) if m["role"] == "user")

        if json_mode:
            from creatorops.agent.router import keyword_route

            return {"content": json.dumps({"route": keyword_route(question)}), "tool_calls": [],
                    "usage": usage}  # fmt: skip

        last = messages[-1]
        if last["role"] == "tool":
            if last["content"].startswith("ERROR") or "no results" in last["content"].lower():
                return {"content": "I don't know based on the available sources.",
                        "tool_calls": [], "usage": usage}  # fmt: skip
            return {
                "content": "Here is what the sources say [1].",
                "tool_calls": [],
                "usage": usage,
            }

        names = [t["function"]["name"] for t in tools or []]
        call = fake_tool_call(question, names)
        return {"content": "", "tool_calls": [call] if call else [], "usage": usage}


def fake_tool_call(question: str, names: list[str]):
    q = question.lower()
    if "schedule_post" in names and "schedule" in q:
        return {"name": "schedule_post", "arguments": {
            "creator": "Creator A", "platform": "Instagram", "post_datetime": "2030-01-04 18:00",
            "caption": "New look of the week #ad"}}  # fmt: skip
    if "find_clause" in names and ("contract" in q or "clause" in q):
        return {
            "name": "find_clause",
            "arguments": {"clause_type": "exclusivity", "query": question},
        }
    if "run_sql" in names and ("reach" in q or "engagement" in q or "how many" in q):
        return {"name": "run_sql", "arguments": {"query": "SELECT COUNT(*) AS n FROM posts"}}
    if "search_policies" in names:
        return {"name": "search_policies", "arguments": {"query": question}}
    return None


def get_llm():
    if settings.llm_provider == "fake":
        return FakeLLM()
    return OllamaClient()
