import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.function_validators import validate_schema, validate_signature


@dataclass
class FunctionInfo:
    name: str
    func: Callable[[dict[str, Any]], str]
    schema: dict[str, Any]
    description: str = ""
    module: str = ""


def import_all_functions(project_root: str) -> None:
    functions_dir = os.path.join(project_root, "src", "functions")
    if os.path.exists(functions_dir):
        for file in os.listdir(functions_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = f"src.functions.{file[:-3]}"
                try:
                    importlib.import_module(module_name)
                    print(f"📥 Импортирован модуль: {module_name}")
                except Exception as e:
                    print(f"❌ Ошибка импорта {module_name}: {e}")


class FunctionRegistry:
    def __init__(self):
        self._functions: dict[str, FunctionInfo] = {}

    def register(self, func: Callable, schema: dict[str, Any], name: str | None = None):
        func_name = name or func.__name__
        validate_signature(func)
        validate_schema(schema, func_name)

        self._functions[func_name] = FunctionInfo(
            name=func_name,
            func=func,
            schema=schema,
            description=schema.get("description", ""),
            module=func.__module__,
        )
        return func

    def execute(self, name: str, args: dict[str, Any]) -> str:
        return self._functions[name].func(args)

    def get_schema(self, name: str) -> dict[str, Any]:
        if name not in self._functions:
            raise KeyError(f"Функция '{name}' не найдена в реестре")
        return self._functions[name].schema

    def list_functions(self) -> list[str]:
        return list(self._functions.keys())


# глобальный реестр
registry = FunctionRegistry()


def function(schema: dict[str, Any], name: str | None = None):
    """Единый декоратор для регистрации функции"""

    def decorator(func: Callable[[dict[str, Any]], str]):
        return registry.register(func, schema, name)

    return decorator
