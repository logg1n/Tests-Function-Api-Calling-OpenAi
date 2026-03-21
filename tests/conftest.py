import json
import textwrap
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from src.schema.client_schema import ClientModel
from src.schema.json_schema import Schema

NAME = "function_name"


def get_mock_function(name: str, body: str, *args):
    args_str = ", ".join(map(str, args))

    clean_body = textwrap.dedent(body).strip()
    indented_body = textwrap.indent(clean_body, "    ")
    source = f"def {name}({args_str}):\n{indented_body}"

    func_module = compile(source, "<string>", "exec")
    func_code = [c for c in func_module.co_consts if isinstance(c, types.CodeType)][0]

    func = types.FunctionType(func_code, globals(), name)
    func.__source__ = source

    return func


@pytest.fixture
def get_json_schema():
    def _loader(file_name: str, schema_name: str):
        folder = Path("src/mock")

        file_path = folder / file_name

        with allure.step(f"Чтение файла {file_name}"):
            with open(file_path, encoding="utf-8") as f:
                raw_json = json.load(f)

        with allure.step(f"Поиск схемы '{schema_name}'"):
            try:
                schema = next(j for j in raw_json if j["name"] == schema_name)
                # Прикрепляем JSON прямо к отчету Allure
                allure.attach(
                    json.dumps(schema, indent=2, ensure_ascii=False),
                    name=f"Schema: {schema_name}",
                    attachment_type=allure.attachment_type.JSON,
                )
                return schema
            except StopIteration:
                pytest.fail(f"Схема с именем '{schema_name}' не найдена в {file_name}")

    return _loader


@pytest.fixture(scope="session")
def schema_json():
    """Твоя JSON схема для тестов (Weather API)"""
    return {
        "name": "call_in_model_ai",
        "description": "Получает текущие погодные условия для заданного города.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Название города, например, Москва или Нью-Йорк",
                    "default": "",
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "description": "Система измерения: metric (Celsius) или imperial (Fahrenheit)",
                    "default": "",
                },
            },
            "required": ["city"],
        },
    }


@pytest.fixture(scope="session")
def schema(schema_json):
    """Превращаем JSON в объект валидированной модели Schema"""
    return Schema.model_validate(schema_json)


@pytest.fixture(scope="session")
def raw_config_data():
    """
    Сырые данные для валидации ClientModel.
    Имена полей приведены в соответствие со схемой.
    """
    return {
        # Поле называется 'router', а не 'aggregator'
        "router": {
            "name": "OPENROUTER",  # Пойдет в config_name
            "base_url": "https://openrouter.ai",
            "role": "Ты инженер-программист.",
            "timeout": 60,
            "tool_choice": "auto",
            "models": {
                "name": "openai/gpt-4o-mini",
                "semaphore": 25,
                "max_tokens": 1000,
                "temperature": 0.3,
            },
            # Добавляем тестовый ключ, чтобы прошел model_post_init
            "api_key": "sk-test-key-12345",
        },
        # Поле 'queries' должно быть списком (list), а не словарем
        "queries": [{"query": "Как погода в Минске?"}],
    }


@pytest.fixture
def root_config(raw_config_data):
    """
    Создаем свежий конфиг для каждого теста.
    Pydantic сам применит 'prepare_all_data' к списку queries.
    """
    return ClientModel.model_validate(raw_config_data)


@pytest.fixture
def ai_mock():
    """Мок-клиент для имитации запросов к OpenAI"""
    mock_client = MagicMock()
    # Метод .create асинхронный, поэтому используем AsyncMock
    mock_client.chat.completions.create = AsyncMock()
    return mock_client
