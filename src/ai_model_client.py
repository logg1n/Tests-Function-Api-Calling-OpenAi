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
            raise Exception(f"Превышено время ожидания ({router_conf.timeout}с)") from e
        except openai.APIConnectionError as e:
            raise Exception(f"Ошибка сети: {e}") from e
        except openai.APIStatusError as e:
            raise Exception(f"Ошибка API (Статус {e.status_code}): {e.message}") from e

        if response.usage:
            client_conf._request_token += response.usage.prompt_tokens
            client_conf._response_token += response.usage.completion_tokens
            client_conf._total_token += response.usage.total_tokens

        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason

        # ... (код после получения response)

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # 1. Проверка на вызов функций (даже если статус stop)
        if message.tool_calls:
            called_tool = message.tool_calls[0].function.name
            if called_tool == json_schema.name:
                return message

            raise LLMMismatchError(
                message="Вызвана неверная функция",
                fields={"expected": json_schema.name, "received": called_tool},
            )

        # 2. Ошибки лимитов и цензуры
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

        # 3. Модель просто поболтала текстом
        if message.content:
            raise LLMMismatchError(
                message="Модель ответила текстом вместо вызова функции",
                fields={"content_preview": message.content[:100]},
            )

        # 4. Если вообще ничего не пришло
        raise LLMGenerationError(
            message="Пустой ответ от модели (ни текста, ни функций)"
        )
