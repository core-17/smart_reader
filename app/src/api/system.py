from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import PromptTemplate, get_db
from services.ocr_service import get_available_ocr_languages

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health")
def read_health():
    return {
        "status": "ok",
        "ocr_languages": get_available_ocr_languages(),
    }


@router.get("/prompts")
def list_prompts(db: Session = Depends(get_db)):
    prompts = db.query(PromptTemplate).all()
    return [
        {"action_key": p.action_key, "name": p.name, "config": p.config}
        for p in prompts
    ]