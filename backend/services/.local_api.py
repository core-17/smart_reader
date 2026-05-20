import json
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from fastapi import HTTPException

# Визначення шляху до .env файлу
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

# --- DTO для валідації вхідних запитів ---
class DictionaryPromptPayload(BaseModel):
    word: str = Field(..., description="Обране слово або фраза")
    context: str = Field(..., description="Контекст (речення або абзац)")
    hypothesis: Optional[str] = Field(None, description="Гіпотеза користувача про значення")
    
    word_lang: str = Field(
        default="auto", 
        description="Мова оригіналу (наприклад, 'en', 'de')"
    )
    translation_lang: str = Field(
        default="uk", 
        description="Мова перекладу"
    )
    explanation_lang: str = Field(
        default="uk", 
        description="Мова пояснення та фідбеку"
    )

# --- DTO для валідації відповіді від LLM ---
class HypothesisFeedback(BaseModel):
    is_correct: bool = Field(..., description="Чи правильна гіпотеза користувача")
    explanation: str = Field(..., description="Пояснення правильності або помилковості гіпотези")

class DictionaryResponse(BaseModel):
    translation: str = Field(..., description="Переклад слова або фрази")
    contextual_meaning: str = Field(..., description="Пояснення значення у конкретному контексті")
    hypothesis_feedback: Optional[HypothesisFeedback] = Field(
        None, 
        description="Фідбек на гіпотезу (генерується лише якщо гіпотеза була надана)"
    )

# --- Клас сервісу ---
class LocalAPIService:
    def __init__(self):
        # Налаштування Ollama через змінні оточення
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
        self.model_name = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
        
        # Тайм-аут для запитів
        timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
        self.timeout = httpx.Timeout(timeout_seconds)

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
        """
        Метод для отримання пояснення слова від локальної моделі Gemma 4.
        Використовує структуровані промти з XML-тегами для підвищення точності.
        """
        
        # Оптимізований системний промт для Gemma 4
        system_prompt = f"""You are a professional linguistic assistant.
Your goal is to analyze vocabulary within a specific reading context.

### CONSTRAINTS:
1. Dictionary translation MUST be in 'Polish'.
2. Contextual explanation and hypothesis feedback MUST be in 'English'.
3. Output format: Strictly JSON. No explanations outside the JSON object.

### JSON STRUCTURE:
{{
    "translation": "string",
    "contextual_meaning": "string",
    "hypothesis_feedback": {{
        "is_correct": boolean,
        "explanation": "string"
    }}
}}"""

        # Користувацький промт з використанням XML-тегів для чіткого розділення даних
        user_message = f"""Please analyze the following entry:
<word>{payload.word}</word>
<context>{payload.context}</context>
<hypothesis>{payload.hypothesis if payload.hypothesis else 'None provided'}</hypothesis>

Return the analysis in JSON format according to the system instructions."""

        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "format": "json", # Вмикаємо JSON-режим Ollama
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "stop": ["<|file_separator|>", "###"]
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=request_payload)
                response.raise_for_status()
                
                data = response.json()
                ai_content = data.get("message", {}).get("content", "").strip()
                
                # Захист від можливого Markdown-форматування, яке іноді додають LLM
                if ai_content.startswith("```"):
                    ai_content = ai_content.strip("`").replace("json\n", "", 1)
                
                # Валідація отриманих даних за допомогою Pydantic моделі
                parsed_response = DictionaryResponse.model_validate_json(ai_content)
                return parsed_response.model_dump()
                
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502, 
                detail=f"Ollama API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502, 
                detail=f"Connection failed. Is Ollama running? Error: {str(e)}"
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"AI returned invalid JSON structure: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"An unexpected error occurred: {str(e)}"
            )