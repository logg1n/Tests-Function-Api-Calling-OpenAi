FROM python:3.12-slim

WORKDIR /app

# Установим uv
RUN pip install uv

# Скопируем зависимости (requirements.txt из репо А мы заранее копируем в репо B шагом workflow)
COPY requirements.txt ./requirements.txt
COPY pyproject.toml ./

# Установим зависимости
RUN uv sync || true
RUN uv pip install -r requirements.txt || true

# Скопируем код тестов
COPY . .

CMD ["/app/.venv/bin/python", "test_runner.py"]
