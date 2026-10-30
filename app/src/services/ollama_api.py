import json
import logging
import time
from typing import Generator

import httpx

from core.config import settings

logger = logging.getLogger("smart_reader.ollama")


def get_embeddings(texts: list[str], model: str | None = None) -> list[list[float]]:
    target_model = model or settings.OLLAMA_EMBED_MODEL
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"

    start_ts = time.perf_counter()
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                json={"model": target_model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            elapsed = time.perf_counter() - start_ts
            logger.info(
                "🧠 [Ollama Embed] Модель '%s': векторизовано %d фрагментів за %.2f сек",
                target_model,
                len(texts),
                elapsed,
            )
            return embeddings
    except httpx.ConnectError:
        logger.error("❌ Неможливо з'єднатися з Ollama за адресою %s", url)
        raise RuntimeError(f"Сервер Ollama недоступний за адресою {settings.OLLAMA_BASE_URL}")
    except httpx.HTTPStatusError as e:
        logger.error("❌ Помилка Ollama Embed (%s): %s", target_model, e.response.text)
        raise RuntimeError(
            f"Помилка моделі ембедінгів '{target_model}' (перевірте 'ollama pull {target_model}'): {e.response.status_code}"
        )


def stream_ollama_chat(
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    temperature: float = 0.2,
) -> Generator[str, None, None]:
    target_model = model or settings.OLLAMA_MODEL
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "options": {"temperature": temperature},
        "stream": True,
    }

    start_ts = time.perf_counter()
    token_count = 0
    logger.info("🤖 [Ollama Chat] Старт генерації (модель='%s', temp=%.1f)...", target_model, temperature)

    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        token_count += 1
                        if token_count == 1:
                            ttft = time.perf_counter() - start_ts
                            logger.info("⚡ [Ollama Chat] Перший токен отримано за %.2f сек...", ttft)
                        elif token_count % 40 == 0:
                            elapsed = time.perf_counter() - start_ts
                            logger.info("⏳ [Ollama Chat] Згенеровано %d токенів (%.1f сек)...", token_count, elapsed)
                        yield token

        total_time = time.perf_counter() - start_ts
        logger.info("✅ [Ollama Chat] Генерацію завершено: %d токенів за %.2f сек", token_count, total_time)

    except httpx.ConnectError:
        logger.error("❌ Неможливо з'єднатися з Ollama за адресою %s", url)
        raise RuntimeError(f"Сервер Ollama недоступний за адресою {settings.OLLAMA_BASE_URL}")
    except httpx.HTTPStatusError as e:
        logger.error("❌ Ollama повернула помилку: %s", e.response.text)
        raise RuntimeError(f"Помилка моделі Ollama: {e.response.status_code}")
    except Exception as e:
        logger.exception("❌ Невідома помилка під час виклику Ollama")
        raise RuntimeError(f"Збій генерації Ollama: {str(e)}")


def query_ollama(
    system_prompt: str,
    user_text: str,
    context: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    user_content = f"Текст для аналізу:\n{user_text}"
    if context:
        user_content = f"Контекст документа:\n{context}\n\n{user_content}"

    tokens = list(
        stream_ollama_chat(
            system_prompt=system_prompt,
            user_content=user_content,
            model=model,
            temperature=temperature,
        )
    )
    return "".join(tokens).strip()