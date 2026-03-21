def call_in_model_ai(arguments) -> str:
    """
    Получает текущие погодные условия для заданного города.
    """
    # Имитация логики извлечения (для твоих AST тестов)
    location = arguments.get("city", "")
    temp_units = arguments.get("units", "")

    # Мокаем ответ, так как работаем без реального API
    return f"В городе {location} сейчас ясно, 25° {temp_units}"
