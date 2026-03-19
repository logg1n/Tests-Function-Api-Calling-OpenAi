from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionFunctionToolParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition

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

        if response.usage:
            client_conf._request_token += response.usage.prompt_tokens
            client_conf._response_token += response.usage.completion_tokens
            client_conf._total_token += response.usage.total_tokens

        return response.choices[0].message
