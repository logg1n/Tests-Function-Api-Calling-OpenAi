import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class FunctionInfo:
    """Информация о функции"""

    name: str
    func: Callable[[dict[str, Any]], str]
    schema: dict[str, Any]
    description: str = ""
    module: str = ""


class FunctionRegister:
    """Универсальный реестр функций"""

    def __init__(self):
        self._functions: dict[str, FunctionInfo] = {}

    def register_function(
        self,
        function: Callable[[dict[str, Any]], str],
        schema: dict[str, Any],
        name: str | None = None,
        description: str | None = None,
    ) -> str:
        func_name = name or function.__name__

        self._validate_function_signature(function)
        self._validate_schema(schema, func_name)

        self._functions[func_name] = FunctionInfo(
            name=func_name,
            func=function,
            schema=schema,
            description=description or schema.get("description", ""),
            module=function.__module__,
        )
        return func_name

    def register_from_module(self, module_name: str) -> list[str]:
        """Регистрирует все функции из модуля по словарю SCHEMAS"""
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise ValueError(f"Не удалось импортировать модуль {module_name}: {e}") from e

        if not hasattr(module, "SCHEMAS"):
            raise ValueError(f"Модуль {module_name} не содержит словарь SCHEMAS")

        registered = []
        for func_name, schema in module.SCHEMAS.items():
            if hasattr(module, func_name):
                func = getattr(module, func_name)
                if callable(func):
                    self.register_function(func, schema, func_name)
                    registered.append(func_name)
        return registered

    def get_function(self, name: str) -> Callable[[dict[str, Any]], str]:
        if name not in self._functions:
            raise KeyError(f"Функция '{name}' не найдена")
        return self._functions[name].func

    def get_schema(self, name: str) -> dict[str, Any]:
        if name not in self._functions:
            raise KeyError(f"Схема для функции '{name}' не найдена")
        return self._functions[name].schema.copy()

    def get_all_schemas(self) -> list[dict[str, Any]]:
        return [info.schema for info in self._functions.values()]

    def get_function_info(self, name: str) -> FunctionInfo:
        if name not in self._functions:
            raise KeyError(f"Функция '{name}' не найдена")
        return self._functions[name]

    def list_functions(self) -> list[str]:
        return list(self._functions.keys())

    def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        func = self.get_function(function_name)
        return func(arguments)

    def _validate_function_signature(self, func: Callable):
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        if len(params) != 1:
            raise ValueError(
                f"Функция {func.__name__} должна принимать ровно 1 аргумент, получено {len(params)}"
            )

    def _validate_schema(self, schema: dict[str, Any], func_name: str):
        required_fields = ["name", "description", "parameters"]
        for field in required_fields:
            if field not in schema:
                raise ValueError(
                    f"Схема для {func_name} не содержит обязательное поле '{field}'"
                )
        if schema["name"] != func_name:
            raise ValueError(
                f"Имя в схеме '{schema['name']}' не соответствует имени функции '{func_name}'"
            )
        params = schema["parameters"]
        if not isinstance(params, dict) or params.get("type") != "object":
            raise ValueError("Поле 'parameters' должно быть объектом с type='object'")
        if "properties" not in params:
            raise ValueError("Схема должна содержать 'parameters.properties'")


# Глобальный экземпляр
_registry = FunctionRegister()


def get_registry() -> FunctionRegister:
    return _registry


def function(schema: dict[str, Any], name: str | None = None):
    """Декоратор для регистрации функции"""

    def decorator(func: Callable[[dict[str, Any]], str]):
        _registry.register_function(func, schema, name or func.__name__)
        return func

    return decorator
