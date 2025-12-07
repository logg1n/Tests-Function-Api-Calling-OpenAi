"""
Обновленный клиент OpenRouter с поддержкой нового формата Tools
"""

import json
import os
from typing import Any

from openai import OpenAI


class OpenRouterClient:
    """Клиент для работы с OpenRouter API с поддержкой tools"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "openai/gpt-3.5-turbo",
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY не установлен")

        self.client = OpenAI(base_url=base_url, api_key=self.api_key)
        self.model = model

    def convert_functions_to_tools(
        self, functions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Конвертирует старый формат functions в новый формат tools"""
        return [{"type": "function", "function": func} for func in functions]

    def _get_cache_key(self, user_query: str, schemas_str: str) -> str:
        """Генерирует ключ для запроса"""
        return f"{user_query}:{schemas_str}"

    def call_with_functions(
        self,
        user_query: str,
        function_schemas: list[dict[str, Any]],
        use_cache: bool = True,
        cache_dir: str | None = "test_results/cache",
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """Вызывает модель с новым форматом tools"""
        tools = self.convert_functions_to_tools(function_schemas)

        schemas_str = json.dumps(function_schemas, sort_keys=True)
        cache_key = self._get_cache_key(user_query, schemas_str)

        # если кэш отключён
        if not use_cache or cache_dir is None:
            cache_file = None
        else:
            os.makedirs(cache_dir, exist_ok=True)
            safe_key = str(abs(hash(cache_key)))  # безопасное имя файла
            cache_file = os.path.join(cache_dir, f"{safe_key}.json")

        # если кэш включён и файл существует
        if cache_file and os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                print(f"📂 Загружено из кеша: {cache_file}")
                return json.load(f)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помогающий ассистент. Используй предоставленные инструменты (tools).",
                    },
                    {"role": "user", "content": user_query},
                ],
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens,
            )

            message = response.choices[0].message
            result = {
                "user_query": user_query,
                "model": self.model,
                "timestamp": response.created,
                "message": {"content": message.content, "tool_calls": None},
            }

            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = []
                for tool_call in message.tool_calls:
                    if tool_call.type == "function":
                        tool_calls.append(
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": json.loads(tool_call.function.arguments),
                                },
                            }
                        )
                result["message"]["tool_calls"] = tool_calls

                # Обратная совместимость
                if tool_calls:
                    result["message"]["function_call"] = {
                        "name": tool_calls[0]["function"]["name"],
                        "arguments": tool_calls[0]["function"]["arguments"],
                    }

            # сохраняем в кэш, если включён
            if cache_file:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                    print(f"💾 Сохранено в кеш: {cache_file}")

            return result

        except Exception as e:
            return {
                "error": str(e),
                "user_query": user_query,
                "functions_called": [func["name"] for func in function_schemas],
            }


# Простой тест
if __name__ == "__main__":
    import sys

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Установите OPENROUTER_API_KEY")
        sys.exit(1)

    try:
        client = OpenRouterClient(api_key=api_key)
        print("✅ Клиент OpenRouter создан (новый формат tools)")

        test_schema = {
            "name": "test_function",
            "description": "Тестовая функция",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Сообщение"}},
                "required": ["message"],
            },
        }

        result = client.call_with_functions(
            user_query="Скажи привет", function_schemas=[test_schema], use_cache=False
        )

        print("\n📊 Результат теста:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
