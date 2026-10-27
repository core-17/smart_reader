import logging
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Знаходимо файл .env у корені репозиторію (~/smart_reader/.env)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")

def query_ollama(
    system_prompt: str,
    user_text: str,
    context: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Відправляє запит до Ollama API для обробки фрагмента тексту."""
    target_model = model or DEFAULT_OLLAMA_MODEL
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    user_content = f"Текст для аналізу:\n{user_text}"
    if context:
        user_content = f"Контекст документа:\n{context}\n\n{user_content}"

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "options": {
            "temperature": temperature,
        },
        "stream": False,
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "").strip()
    except httpx.ConnectError:
        logger.error("Неможливо з'єднатися з Ollama за адресою %s", url)
        raise RuntimeError(f"Сервер Ollama недоступний за адресою {OLLAMA_BASE_URL}")
    except httpx.HTTPStatusError as e:
        logger.error("Ollama повернула помилку: %s", e.response.text)
        raise RuntimeError(f"Помилка моделі Ollama: {e.response.status_code}")
    except Exception as e:
        logger.exception("Невідома помилка під час виклику Ollama")
        raise RuntimeError(f"Збій генерації Ollama: {str(e)}")