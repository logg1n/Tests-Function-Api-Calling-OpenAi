import json
import os
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionFunctionToolParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition

from src.exceptions.custom_exceptions import LLMGenerationError, LLMMismatchError
from src.schema.client_schema import ClientModel, ModelConfig, RouterConfig
from src.schema.json_schema import Schema


class ModelInterface:
    @staticmethod
    async def call_with_functions(
        ai_client: AsyncOpenAI,
        client_conf: ClientModel,
        router_conf: RouterConfig,
        model_conf: ModelConfig,
        query: str,
        json_schema: Schema,
    ):
        func = FunctionDefinition(
            name=json_schema.name,
            description=json_schema.description,
            parameters=json_schema.parameters.model_dump(
                by_alias=True, exclude_none=True
            ),
        )

        tools: list[ChatCompletionFunctionToolParam] = [
            ChatCompletionFunctionToolParam(type="function", function=func)
        ]

        model_params: dict[str, Any] = model_conf.get_params()

        try:
            response = await ai_client.chat.completions.create(
                model=model_conf.model_id,
                messages=[
                    router_conf.system_message,
                    ChatCompletionUserMessageParam(role="user", content=query),
                ],
                tools=tools,
                tool_choice=router_conf.tool_choice,
                timeout=router_conf.timeout,
                **model_params,
            )
        except openai.APITimeoutError as e:
            raise LLMGenerationError(
                message=f"Превышено время ожидания ({router_conf.timeout}с)",
                fields={"timeout": router_conf.timeout},
            ) from e
        except openai.APIConnectionError as e:
            raise LLMGenerationError(
                message=f"Ошибка сети: {e}",
                fields={"error_type": "connection"},
            ) from e
        except openai.APIStatusError as e:
            raise LLMGenerationError(
                message=f"Ошибка API (Статус {e.status_code}): {e.message}",
                fields={"status_code": e.status_code},
            ) from e

        if not response.choices:
            raise LLMGenerationError(
                message="Пустой список choices в ответе модели",
                fields={"response_id": getattr(response, "id", "unknown")},
            )

        # !TODO : Создание dataclass вместо прямых полей в pydantic
        request_usage = 0
        response_usage = 0
        total_usage = 0

        if response.usage:
            request_usage = response.usage.prompt_tokens
            response_usage = response.usage.completion_tokens
            total_usage = response.usage.total_tokens

            client_conf._request_token += request_usage
            client_conf._response_token += response_usage
            client_conf._total_token += total_usage

        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        if message.tool_calls:
            called_tool = message.tool_calls[0].function.name
            if called_tool == json_schema.name:
                return {
                    "message": message,
                    "usage": {
                        "prompt_tokens": request_usage,
                        "completion_tokens": response_usage,
                        "total_tokens": total_usage,
                    },
                }

            raise LLMMismatchError(
                message="Вызвана неверная функция",
                fields={"expected": json_schema.name, "received": called_tool},
            )

        if finish_reason == "length":
            raise LLMGenerationError(
                message="Генерация прервана: не хватило токенов",
                fields={"max_tokens": model_conf.max_tokens, "finish_reason": "length"},
            )

        if finish_reason == "content_filter":
            raise LLMGenerationError(
                message="Ответ заблокирован фильтрами безопасности",
                fields={"finish_reason": "content_filter"},
            )

        if message.content is not None and message.content:
            raise LLMMismatchError(
                message="Модель ответила текстом вместо вызова функции",
                fields={"content_preview": message.content[:100]},
            )

        raise LLMGenerationError(
            message="Пустой ответ от модели (ни текста, ни функций)"
        )

    @staticmethod
    def ci_report(results, output_path="test_results.json"):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("### Результаты тестов\n\n")
                for i, detail in enumerate(results.get("details", []), 1):
                    f.write(f"#### Тест {i}\n")
                    f.write(f"- Запрос: {detail.get('query', '')}\n")
                    for step in detail.get("execution_chain", []):
                        f.write(f"- Функция: {step['function']}\n")
                        f.write(f"- Результат: {step['result']}\n\n")
