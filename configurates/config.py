import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не установлен")

USE_CACHE = os.getenv("USE_CACHE", "false").lower() == "true"
if not USE_CACHE:
    raise ValueError("API_TOKEN_TRELLO не установлен")

