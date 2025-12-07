import json

import pytest
from src.schemas import get_card_creation_schema, get_order_schema


class TestOpenRouterFunctionCalling:
    """Интеграционные тесты с реальным OpenRouter API"""

    @pytest.mark.integration
    def test_natural_language_understanding(self, real_openrouter_client, test_cases):
        """Тестируем понимание естественного языка моделью"""

        schemas = [get_card_creation_schema(), get_order_schema()]

        results = real_openrouter_client.test_natural_language_understanding(
            test_cases=test_cases, function_schemas=schemas
        )

        print("\n📊 Результаты тестирования:")
        print(f"Всего тестов: {results['total']}")
        print(f"Пройдено: {results['passed']}")
        print(f"Провалено: {results['failed']}")

        for detail in results["details"]:
            if detail["status"] != "passed":
                print(f"\n❌ Провален: '{detail['query']}'")
                if "reason" in detail:
                    print(f"   Причина: {detail['reason']}")
                message = detail.get("response", {}).get("message", {})
                tool_calls = message.get("tool_calls")
                function_call = message.get("function_call")
                if tool_calls and len(tool_calls) > 0:
                    print(f"   Вызвана функция: {tool_calls[0]['function']['name']}")
                    print(f"   Аргументы: {tool_calls[0]['function']['arguments']}")
                elif function_call:
                    print(f"   Вызвана функция: {function_call['name']}")
                    print(f"   Аргументы: {function_call['arguments']}")

        with open("test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        success_rate = results["passed"] / results["total"] * 100
        print(f"\n📈 Процент успеха: {success_rate:.1f}%")
        assert success_rate >= 80.0, f"Слишком низкий процент успеха: {success_rate:.1f}%"

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "query, expected_name",
        [
            ("Создай карточку 'Финансы'", "Финансы"),
            ("Нужна карточка под названием Маркетинг", "Маркетинг"),
            ("Заведи карточку для задачи Разработка", "Разработка"),
            ("Сделай карточку: Анализ данных", "Анализ данных"),
        ],
    )
    def test_various_phrasings(self, real_openrouter_client, query, expected_name):
        """Тестируем разные формулировки запросов"""

        schema = get_card_creation_schema()

        response = real_openrouter_client.call_with_functions(
            user_query=query, function_schemas=[schema], use_cache=True
        )

        assert "error" not in response, f"Ошибка API: {response.get('error')}"

        message = response.get("message", {})
        tool_calls = message.get("tool_calls")
        function_call = message.get("function_call")

        if tool_calls and len(tool_calls) > 0:
            actual_function = tool_calls[0]["function"]["name"]
            actual_arguments = tool_calls[0]["function"]["arguments"]
        elif function_call:
            actual_function = function_call["name"]
            actual_arguments = function_call["arguments"]
        else:
            pytest.fail("Модель не вызвала функцию")

        assert actual_function == "create_card"
        assert actual_arguments["name"] == expected_name

    @pytest.mark.integration
    def test_function_selection(self, real_openrouter_client):
        """Тестируем выбор правильной функции"""

        schemas = [get_card_creation_schema(), get_order_schema()]

        response = real_openrouter_client.call_with_functions(
            user_query="Закажи 3 монитора для офиса",
            function_schemas=schemas,
            use_cache=True,
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls")
        function_call = message.get("function_call")

        if tool_calls and len(tool_calls) > 0:
            actual_function = tool_calls[0]["function"]["name"]
            actual_arguments = tool_calls[0]["function"]["arguments"]
        elif function_call:
            actual_function = function_call["name"]
            actual_arguments = function_call["arguments"]
        else:
            pytest.fail("Модель не вызвала функцию")

        assert actual_function == "create_order"
        assert actual_arguments["product_name"] == "мониторы"
        assert actual_arguments["quantity"] == 3

    @pytest.mark.integration
    def test_cache_mechanism(self, real_openrouter_client, tmp_path):
        """Тестируем механизм кеширования"""

        schema = get_card_creation_schema()
        cache_dir = tmp_path / "cache"

        response1 = real_openrouter_client.call_with_functions(
            user_query="Тест кеширования",
            function_schemas=[schema],
            use_cache=True,
            cache_dir=str(cache_dir),
        )

        response2 = real_openrouter_client.call_with_functions(
            user_query="Тест кеширования",
            function_schemas=[schema],
            use_cache=True,
            cache_dir=str(cache_dir),
        )

        assert response1 == response2

        cache_files = list(cache_dir.glob("*.json"))
        assert len(cache_files) == 1
