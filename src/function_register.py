import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.function_validators import Validator


@dataclass
class FunctionInfo:
    name: str
    func: Callable[[dict[str, Any]], str]
    schema: dict[str, Any]
    module: str = ""


class FunctionRegistry:
    _functions: dict[str, FunctionInfo] = {}

    @staticmethod
    def execute(name: str, args: dict[str, Any]) -> str:
        return FunctionRegistry._functions[name].func(args)

    @staticmethod
    def get_schema(name: str) -> dict[str, Any]:
        if name not in FunctionRegistry._functions:
            raise KeyError(f"Функция '{name}' не найдена в реестре")
        return FunctionRegistry._functions[name].schema

    @staticmethod
    def function(schema: dict[str, Any]):
        def decorator(func: Callable[[dict[str, Any]], str]):
            func_name = func.__name__
            Validator.validate_signature(func)
            Validator.validate_schema(schema, func_name)

            FunctionRegistry._functions[func_name] = FunctionInfo(
                name=func_name,
                func=func,
                schema=schema,
                module=func.__module__,
            )
            return func
        return decorator

    @staticmethod
    def import_functions(project_root: str) -> None:
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
