from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import LexiconEntry, PromptTemplate, get_db
from services.ollama_api import query_ollama

router = APIRouter(prefix="/api/analyze", tags=["Analysis"])

Action = Literal["translate", "explain", "vocabulary"]
MAX_TEXT_CHARS = 500
MAX_CONTEXT_CHARS = 4000
DEFAULT_SYSTEM_PROMPT = "Проаналізуй наданий фрагмент тексту."


class TextActionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    action: Action
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    force_refresh: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Текст не може бути порожнім")
        return stripped


@router.post("")
def analyze_text(payload: TextActionRequest, db: Session = Depends(get_db)):
    normalized = payload.text.lower()

    existing = (
        db.query(LexiconEntry)
        .filter_by(normalized_text=normalized, action=payload.action)
        .first()
    )

    if existing and not payload.force_refresh:
        return {
            "status": "ok",
            "from_db": True,
            "action": payload.action,
            "original_text": payload.text,
            "result": (existing.ai_data or {}).get("text", ""),
            "ai_data": existing.ai_data,
        }

    prompt_obj = db.query(PromptTemplate).filter_by(action_key=payload.action).first()
    config = (prompt_obj.config if prompt_obj else None) or {}
    system_instruction = config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    temperature = float(config.get("temperature", 0.2))

    try:
        generated_text = query_ollama(
            system_prompt=system_instruction,
            user_text=payload.text,
            context=payload.context,
            temperature=temperature,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    ai_data = {
        "text": generated_text,
        "prompt_used": system_instruction,
        "context": payload.context,
    }

    try:
        if existing:
            existing.ai_data = ai_data
        else:
            db.add(
                LexiconEntry(
                    original_text=payload.text,
                    normalized_text=normalized,
                    action=payload.action,
                    ai_data=ai_data,
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()

    return {
        "status": "ok",
        "from_db": False,
        "action": payload.action,
        "original_text": payload.text,
        "result": generated_text,
        "ai_data": ai_data,
    }