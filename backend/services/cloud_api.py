import os
import google.generativeai as genai
from fastapi import HTTPException
from pydantic import ValidationError
from pathlib import Path
from dotenv import load_dotenv

# Перевикористовуємо вже існуючі DTO для збереження єдиного контракту
from services.local_api import DictionaryPromptPayload, DictionaryResponse

# Завантаження змінних середовища
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

class CloudAPIService:
    def __init__(self):
        # Отримання API ключа
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise ValueError("AI_API_KEY відсутній у файлі .env")
        
        # Ініціалізація клієнта Gemini
        genai.configure(api_key=api_key)
        
        # Використовуємо gemini-3-flash-preview (швидкий, дешевий, підтримує JSON Mode)
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
        print("👉 [DEBUG] CloudAPIService ініціалізовано з моделлю gemini-3-flash-preview")

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
        # Gemini краще працює, коли системні інструкції відокремлені, 
        # але для сумісності з поточним SDK ми передаємо все чітко в промпті.
        
        prompt = f"""
        You are an expert linguistic AI agent. Your task is to explain vocabulary in the context of reading.
        The user will provide a word in '{payload.word_lang}' language, the context paragraph, and optionally their hypothesis.
        
        You MUST adhere to the following strict language constraints:
        1. The exact dictionary translation MUST be in '{payload.translation_lang}' language.
        2. The contextual explanation and hypothesis feedback MUST be in '{payload.explanation_lang}' language.
        
        Word: {payload.word}
        Context: {payload.context}
        Hypothesis: {payload.hypothesis if payload.hypothesis else 'None provided'}
        
        Return ONLY a valid JSON object matching this schema:
        {{
            "translation": "string",
            "contextual_meaning": "string",
            "hypothesis_feedback": {{
                "is_correct": boolean,
                "explanation": "string"
            }}
        }}
        """

        try:
            # Асинхронний виклик API з налаштуванням температури та примусового JSON
            response = await self.model.generate_content_async(
                contents=prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            ai_content = response.text
            
            # Строга валідація згенерованого JSON через Pydantic
            parsed_response = DictionaryResponse.model_validate_json(ai_content)
            return parsed_response.model_dump()
            
        except ValidationError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Gemini повернув невалідний формат даних. Деталі: {str(e)}"
            )
        except Exception as e:
            # Обробка помилок мережі або лімітів квоти (Rate Limits) від Google
            raise HTTPException(
                status_code=502, 
                detail=f"Помилка комунікації з Cloud AI (Gemini): {str(e)}"
            )