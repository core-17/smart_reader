import os
<<<<<<< HEAD
import json
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
import httpx
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from fastapi import HTTPException
<<<<<<< HEAD
import google.generativeai as genai
=======

# Новий офіційний SDK від Google
from google import genai
from google.genai import types
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)

# Визначення шляху до .env файлу та завантаження змінних
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

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

# --- Локальний сервіс (Ollama) ---
class LocalAPIService:
    def __init__(self):
        # Налаштування Ollama через змінні оточення
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
<<<<<<< HEAD
        self.model_name = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
=======
        
        # ВАЖЛИВО: Оновлено дефолтну модель на llama3.1:8b (щоб не падало з помилкою 500)
        self.model_name = os.getenv("OLLAMA_MODEL", "gemma4:latest")
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
        
        # Тайм-аут для запитів
        timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
        self.timeout = httpx.Timeout(timeout_seconds)

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
<<<<<<< HEAD
        """
        Метод для отримання пояснення слова від локальної моделі Gemma 4.
        Використовує структуровані промти з XML-тегами для підвищення точності.
        """
        
        # Оптимізований системний промт для Gemma 4
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
        system_prompt = f"""You are a professional linguistic assistant.
Your goal is to analyze vocabulary within a specific reading context.

### CONSTRAINTS:
<<<<<<< HEAD
1. Dictionary translation MUST be in 'Polish'.
2. Contextual explanation and hypothesis feedback MUST be in 'English'.
=======
<<<<<<<< HEAD:backend/services/.local_api.py
1. Dictionary translation MUST be in 'Polish'.
2. Contextual explanation and hypothesis feedback MUST be in 'English'.
========
1. Dictionary translation MUST be in '{payload.translation_lang}'.
2. Contextual explanation and hypothesis feedback MUST be in '{payload.explanation_lang}'.
>>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai):backend/services/AI_api.py
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
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

<<<<<<< HEAD
        # Користувацький промт з використанням XML-тегів для чіткого розділення даних
        user_message = f"""Please analyze the following entry:
<word>{payload.word}</word>
<context>{payload.context}</context>
<hypothesis>{payload.hypothesis if payload.hypothesis else 'None provided'}</hypothesis>

Return the analysis in JSON format according to the system instructions."""
=======
        user_message = f"""Please analyze the following entry:
<word>{payload.word}</word>
<context>{payload.context}</context>
<hypothesis>{payload.hypothesis if payload.hypothesis else 'None provided'}</hypothesis>"""
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)

        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
<<<<<<< HEAD
            "format": "json", # Вмикаємо JSON-режим Ollama
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "stop": ["<|file_separator|>", "###"]
=======
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=request_payload)
                response.raise_for_status()
                
                data = response.json()
                ai_content = data.get("message", {}).get("content", "").strip()
                
<<<<<<< HEAD
                # Захист від можливого Markdown-форматування, яке іноді додають LLM
                if ai_content.startswith("```"):
                    ai_content = ai_content.strip("`").replace("json\n", "", 1)
                
                # Валідація отриманих даних за допомогою Pydantic моделі
=======
                # Захист від можливого Markdown-форматування
                if ai_content.startswith("```"):
                    ai_content = ai_content.strip("`").replace("json\n", "", 1)
                
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
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


# --- Хмарний сервіс (Gemini) ---
class CloudAPIService:
    def __init__(self):
<<<<<<< HEAD
        # Get API key
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise ValueError("AI_API_KEY is missing in the .env file")
        
<<<<<<< HEAD
        # Initialize Gemini client
        genai.configure(api_key=api_key)
        
        # Use gemini-3-flash-preview (fast, affordable, supports JSON Mode)
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
        print("👉 [DEBUG] CloudAPIService initialized with gemini-3-flash-preview model")

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
        # Gemini works better when system instructions are separated,
        # but for compatibility with the current SDK we pass everything clearly in the prompt.
        
=======
        # Ініціалізація нового офіційного клієнта google-genai
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash'
        print(f"👉 [DEBUG] CloudAPIService initialized with {self.model_name} model via new SDK")

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
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
<<<<<<< HEAD
            # Async API call with low temperature and forced JSON response
            response = await self.model.generate_content_async(
                contents=prompt,
                generation_config=genai.GenerationConfig(
=======
            # Асинхронний виклик через новий SDK
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            ai_content = response.text
            
<<<<<<< HEAD
            # Strict validation of generated JSON via Pydantic
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
            parsed_response = DictionaryResponse.model_validate_json(ai_content)
            return parsed_response.model_dump()
            
        except ValidationError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Gemini returned an invalid data format. Details: {str(e)}"
            )
        except Exception as e:
<<<<<<< HEAD
            # Handle network errors or Google API quota/rate-limit failures
=======
>>>>>>> a90816d (update backund and fix ui issues, also remove cloud api and add new model for local ai)
            raise HTTPException(
                status_code=502, 
                detail=f"Communication error with Cloud AI (Gemini): {str(e)}"
            )