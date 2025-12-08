import json
from typing import Any

from openai import OpenAI

from configurates.config import OPENROUTER_API_KEY, USE_CACHE
from src.cache_manager import CacheManager


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "openai/gpt-3.5-turbo",
    ):
        self.api_key = OPENROUTER_API_KEY
        self.client = OpenAI(base_url=base_url, api_key=self.api_key)
        self.model = model
        self.cache = CacheManager(enabled=USE_CACHE)

    def call_with_functions(
        self,
        user_query: str,
        function_schemas: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        key = f"{user_query}:{json.dumps(function_schemas, sort_keys=True, ensure_ascii=False)}"

        # пробуем достать из кэша
        cached = self.cache.get(key)
        if cached:
            return cached

        # реальный вызов
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты ассистент с поддержкой tools."},
                {"role": "user", "content": user_query},
            ],
            tools=[{"type": "function", "function": f} for f in function_schemas],
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens,
        )

        message = response.choices[0].message
        result = {
            "user_query": user_query,
            "model": self.model,
            "timestamp": response.created,
            "message": {
                "content": message.content,
                "tool_calls": None,
                "function_call": None,
            },
        }

        if getattr(message, "tool_calls", None):
            tool_calls = []
            for tool_call in message.tool_calls:
                if tool_call.type == "function":
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = tool_call.function.arguments
                    tool_calls.append(
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": args,
                            },
                        }
                    )
            result["message"]["tool_calls"] = tool_calls

            # для обратной совместимости оставляем первый вызов
            if tool_calls:
                result["message"]["function_call"] = tool_calls[0]["function"]

        # сохраняем в кэш
        self.cache.set(key, result)
        return result
