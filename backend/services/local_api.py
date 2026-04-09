import json
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from typing import Optional
from fastapi import HTTPException

# Resolve the absolute path to the .env file (two directories above this file)
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

# --- DTO for validating incoming client requests ---
class DictionaryPromptPayload(BaseModel):
    word: str = Field(..., description="Selected word or phrase")
    context: str = Field(..., description="Paragraph or sentence used to understand the context")
    hypothesis: Optional[str] = Field(None, description="User's hypothesis about the meaning")
    
    word_lang: str = Field(
        default="auto", 
        description="Source language (for example, 'en', 'de', or 'auto')"
    )
    translation_lang: str = Field(
        default="uk", 
        description="Target translation language"
    )
    explanation_lang: str = Field(
        default="uk", 
        description="Language used by the AI for contextual explanation and feedback"
    )

# --- DTO for strict validation of the LLM response ---
class HypothesisFeedback(BaseModel):
    is_correct: bool = Field(..., description="Whether the user's hypothesis is correct")
    explanation: str = Field(..., description="Explanation of why the hypothesis is correct or not")

class DictionaryResponse(BaseModel):
    translation: str = Field(..., description="Translation of the word or phrase")
    contextual_meaning: str = Field(..., description="Explanation of how the word is used in this context")
    hypothesis_feedback: Optional[HypothesisFeedback] = Field(
        None, 
        description="Feedback on the user's hypothesis (generated only if a hypothesis was provided)"
    )

# --- Service class ---
class LocalAPIService:
    def __init__(self):
        # Configure the Ollama API through environment variables (with default fallbacks)
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
        self.model_name = os.getenv("OLLAMA_MODEL", "llama3")
        
        # Parse the timeout as a float because os.getenv returns a string
        timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
        self.timeout = httpx.Timeout(timeout_seconds)

    async def explain_word(self, payload: DictionaryPromptPayload) -> dict:
        # Dynamically generate the system prompt based on language settings
        system_prompt = f"""
        You are an expert linguistic AI agent. Your task is to explain vocabulary in the context of reading.
        The user will provide a word in '{payload.word_lang}' language, the context paragraph, and optionally their hypothesis.
        
        You MUST adhere to the following strict language constraints:
        1. The exact dictionary translation MUST be in '{payload.translation_lang}' language.
        2. The contextual explanation and hypothesis feedback MUST be in '{payload.explanation_lang}' language.
        
        Return ONLY a valid JSON object matching this schema. Do not output markdown, just raw JSON:
        {{
            "translation": "string",
            "contextual_meaning": "string",
            "hypothesis_feedback": {{
                "is_correct": boolean,
                "explanation": "string"
            }} // Optional: Include only if the user provides a hypothesis
        }}
        """

        user_message = f"""
        Word: {payload.word}
        Context: {payload.context}
        Hypothesis: {payload.hypothesis if payload.hypothesis else 'None provided'}
        """

        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "format": "json", # Enable structured output (JSON mode) in Ollama
            "stream": False,
            "options": {
                "temperature": 0.1 # Lower temperature to reduce hallucinations
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.ollama_url, json=request_payload)
                response.raise_for_status()
                
                data = response.json()
                ai_content = data.get("message", {}).get("content", "")
                
                # Validate the generated JSON with Pydantic
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
                detail=f"Failed to connect to the local AI. Check whether Ollama is running: {str(e)}"
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"The AI returned invalid data format. Details: {str(e)}"
            )