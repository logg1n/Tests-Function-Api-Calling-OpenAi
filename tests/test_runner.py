#!/usr/bin/env python3
"""
Тест-раннер:
1. Результаты тестов (passed/failed/errors).
2. Результаты реального выполнения функций.
"""

import argparse
import importlib
import json
import os
from datetime import datetime

from configurates.config import OPENROUTER_API_KEY
from src.function_register import get_registry
from src.openrouter_client import OpenRouterClient

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)


def import_all_functions():
    """Импортирует все модули из src/functions, чтобы функции зарегистрировались"""
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


def run_tests_for_function(
    function_name, test_cases, verbose=True, model="openai/gpt-3.5-turbo"
):

    registry = get_registry()
    api_key = OPENROUTER_API_KEY

    # Получаем схему функции
    try:
        schema = registry.get_schema(function_name)
    except KeyError:
        print(f"❌ Функция '{function_name}' не найдена в реестре")
        print(f"   Доступные функции: {', '.join(registry.list_functions())}")
        return None

    # Создаем клиент
    try:
        client = OpenRouterClient(api_key=api_key, model=model)
    except Exception as e:
        print(f"❌ Ошибка создания клиента: {e}")
        return None

    print(f"\n🎯 Тестирование функции: {function_name}")
    print(f"   Количество тестов: {len(test_cases)}")
    print(f"   Модель: {model}")

    results = {
        "total": len(test_cases),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "details": [],
    }

    for i, test_case in enumerate(test_cases, 1):
        if verbose:
            query_preview = (
                test_case["query"][:50] + "..."
                if len(test_case["query"]) > 50
                else test_case["query"]
            )
            print(f"\n🔍 Тест {i}/{len(test_cases)}: '{query_preview}'")

        test_result = {
            "test_index": i,
            "query": test_case["query"],
            "description": test_case.get("description", ""),
            "expected_function": test_case.get("expected_function"),
            "expected_arguments": test_case.get("expected_arguments", {}),
        }

        try:
            # Вызываем OpenRouter
            response = client.call_with_functions(
                user_query=test_case["query"], function_schemas=[schema], use_cache=True
            )
            test_result["response"] = response

            if "error" in response:
                test_result["status"] = "error"
                test_result["error"] = response["error"]
                results["errors"] += 1
                if verbose:
                    print(f"❌ Ошибка API: {response['error']}")
            else:
                message = response.get("message", {})
                tool_calls = message.get("tool_calls")
                function_call = message.get("function_call")  # fallback

                if tool_calls and len(tool_calls) > 0:
                    func_name = tool_calls[0]["function"]["name"]
                    func_args = tool_calls[0]["function"]["arguments"]
                elif function_call:
                    func_name = function_call["name"]
                    func_args = function_call["arguments"]
                else:
                    test_result["status"] = "failed"
                    test_result["reason"] = "Функция не вызвана"
                    results["failed"] += 1
                    if verbose:
                        print("❌ Функция не вызвана")
                    results["details"].append(test_result)
                    continue

                test_result["actual_function"] = func_name
                test_result["actual_arguments"] = func_args

                expected_func = test_case.get("expected_function")
                if expected_func and func_name != expected_func:
                    test_result["status"] = "failed"
                    test_result["reason"] = (
                        f"Ожидалась функция '{expected_func}', вызвана '{func_name}'"
                    )
                    results["failed"] += 1
                    if verbose:
                        print(f"❌ Ожидалась '{expected_func}', вызвана '{func_name}'")
                else:
                    test_result["status"] = "passed"
                    results["passed"] += 1
                    if verbose:
                        print(f"✅ Пройдено! Функция: {func_name}")

                # ⚙️ Реальное выполнение функции
                try:
                    execution_result = registry.execute(func_name, func_args)
                    test_result["execution_result"] = execution_result
                    if verbose:
                        print(f"⚙️ Результат выполнения: {str(execution_result)[:200]}...")
                except Exception as e:
                    test_result["execution_result"] = f"Ошибка выполнения: {e}"
                    if verbose:
                        print(f"❌ Ошибка выполнения функции: {e}")

            results["details"].append(test_result)

        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            results["details"].append(test_result)
            results["errors"] += 1
            if verbose:
                print(f"🔥 Исключение: {e}")

    print(f"\n{'=' * 60}")
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print(f"{'=' * 60}")
    print(f"Всего тестов: {results['total']}")
    print(f"✅ Пройдено: {results['passed']}")
    print(f"❌ Провалено: {results['failed']}")
    print(f"⚠️  Ошибок: {results['errors']}")

    if results["total"] > 0:
        success_rate = results["passed"] / results["total"] * 100
        print(f"📈 Успешность: {success_rate:.1f}%")

    return results


def save_test_results(results, function_name):
    """Сохраняет результаты тестов"""
    dir_path = os.path.join("test_results", function_name)
    os.makedirs(dir_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(dir_path, f"tests_{timestamp}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return filename


def save_execution_results(results, function_name):
    """Сохраняет результаты выполнения функций отдельно"""
    dir_path = os.path.join("test_results", function_name)
    os.makedirs(dir_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(dir_path, f"exec_{timestamp}.json")

    exec_data = []
    for detail in results["details"]:
        exec_data.append(
            {
                "test_index": detail["test_index"],
                "query": detail["query"],
                "execution_result": detail.get("execution_result", None),
            }
        )

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(exec_data, f, ensure_ascii=False, indent=2)
    return filename


def main():
    parser = argparse.ArgumentParser(description="Тестирование function calling")
    parser.add_argument("--function", type=str, required=True, help="Имя функции для тестирования")
    parser.add_argument("--tests", type=str, required=True, help="JSON файл с тестовыми кейсами")
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод")
    parser.add_argument("--model", type=str, default="openai/gpt-3.5-turbo", help="Модель OpenRouter")

    args = parser.parse_args()

    # Импортируем все функции, чтобы они зарегистрировались
    import_all_functions()

    if not os.path.exists(args.tests):
        print(f"❌ Файл тестов не найден: {args.tests}")
        return

    with open(args.tests, encoding="utf-8") as f:
        test_cases = json.load(f)

    results = run_tests_for_function(
        function_name=args.function,
        test_cases=test_cases,
        verbose=args.verbose,
        model=args.model,
    )

    if results:
        tests_file = save_test_results(results, args.function)
        exec_file = save_execution_results(results, args.function)
        print(f"\n💾 Результаты тестов сохранены в: {tests_file}")
        print(f"⚙️ Результаты выполнения функций сохранены в: {exec_file}")

if __name__ == '__main__':
    main()
