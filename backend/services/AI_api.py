import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from fastapi import HTTPException

# New official Google SDK
from google import genai
from google.genai import types

# Locate project .env file and load environment variables
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# --- DTOs for validating incoming requests ---
class DictionaryPromptPayload(BaseModel):
    word: str = Field(..., description="Target word or phrase to analyze")
    context: str = Field(..., description="Context sentence or paragraph")
    hypothesis: Optional[str] = Field(None, description="User-provided hypothesis about the meaning")

    word_lang: str = Field(
        default="auto",
        description="Language of the source word (e.g. 'en', 'de')"
    )
    translation_lang: str = Field(
        default="uk",
        description="Language for the dictionary translation"
    )
    explanation_lang: str = Field(
        default="uk",
        description="Language for the contextual explanation and feedback"
    )

# --- DTO for validating LLM responses ---
class HypothesisFeedback(BaseModel):
    is_correct: bool = Field(..., description="Whether the user's hypothesis is correct")
    explanation: str = Field(..., description="Explanation of why the hypothesis is correct or not")

class DictionaryResponse(BaseModel):
    translation: str = Field(..., description="Translation of the word or phrase")
    contextual_meaning: str = Field(..., description="Explanation of the meaning in the specific context")
    hypothesis_feedback: Optional[HypothesisFeedback] = Field(
        None,
        description="Feedback on the hypothesis (generated only if a hypothesis was provided)"
    )
# --- Local AI service (Ollama) ---
class LocalAPIService:
    def __init__(self):
        # Ollama settings from environment variables
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
        self.model_name = os.getenv("OLLAMA_MODEL", "gemma4:latest")
        
        # Request timeout configuration
        timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
        self.timeout = httpx.Timeout(timeout_seconds)

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
        system_prompt = f"""You are a professional linguistic assistant.
Your goal is to analyze vocabulary within a specific reading context.

### CONSTRAINTS:
1. Dictionary translation MUST be in '{payload.translation_lang}'.
2. Contextual explanation and hypothesis feedback MUST be in '{payload.explanation_lang}'.
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

        user_message = f"""Please analyze the following entry:
<word>{payload.word}</word>
<context>{payload.context}</context>
<hypothesis>{payload.hypothesis if payload.hypothesis else 'None provided'}</hypothesis>"""

        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=request_payload)
                response.raise_for_status()
                
                data = response.json()
                ai_content = data.get("message", {}).get("content", "").strip()
                
                # Protect against possible Markdown formatting in the response
                if ai_content.startswith("```"):
                    ai_content = ai_content.strip("`").replace("json\n", "", 1)
                
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


# --- Cloud AI service (Gemini) ---
class CloudAPIService:
    def __init__(self):
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise ValueError("AI_API_KEY is missing in the .env file")
        
        # Initialize the new official google-genai client
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash'
        print(f"[DEBUG] CloudAPIService initialized with {self.model_name} model via google-genai SDK")

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
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
            # Asynchronous call using the new SDK
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            ai_content = response.text
            
            parsed_response = DictionaryResponse.model_validate_json(ai_content)
            return parsed_response.model_dump()
            
        except ValidationError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Gemini returned an invalid data format. Details: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=502, 
                detail=f"Communication error with Cloud AI (Gemini): {str(e)}"
            )