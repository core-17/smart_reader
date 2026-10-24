import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from core.database import init_db, SessionLocal, LexiconEntry, PromptTemplate, Book
from services.ocr_service import process_pdf_with_ocr, get_available_ocr_languages
from services.storage_service import init_s3_bucket, upload_pdf_to_s3


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_s3_bucket()
    yield


app = FastAPI(title="Smart Reader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextActionRequest(BaseModel):
    text: str
    action: str
    context: str | None = None
    force_refresh: bool = False  # Якщо True — ігнорує кеш у БД і питає ШІ заново


@app.get("/api/health")
def read_health():
    return {
        "status": "ok",
        "ocr_languages": get_available_ocr_languages(),
    }


@app.get("/api/prompts")
def list_prompts():
    with SessionLocal() as db:
        prompts = db.query(PromptTemplate).all()
        return [{"action_key": p.action_key, "name": p.name, "config": p.config} for p in prompts]


@app.post("/api/pdf/process-ocr")
async def api_process_pdf_ocr(
    file: UploadFile = File(...),
    lang: str = Form("ukr+eng"),
):
    try:
        pdf_bytes = await file.read()
        file_id = uuid.uuid4().hex[:8]
        safe_name = (file.filename or "book.pdf").replace(" ", "_")

        # 1. Зберігаємо оригінал у SeaweedFS (S3)
        raw_key = upload_pdf_to_s3(f"raw/{file_id}_{safe_name}", pdf_bytes)

        # 2. Виконуємо OCR
        result_bytes = process_pdf_with_ocr(pdf_bytes=pdf_bytes, lang=lang)

        # 3. Зберігаємо OCR-версію у SeaweedFS (S3) та записуємо книгу в PostgreSQL
        ocr_key = upload_pdf_to_s3(f"ocr/{file_id}_{safe_name}", result_bytes)
        with SessionLocal() as db:
            book = Book(title=safe_name, s3_raw_key=raw_key, s3_ocr_key=ocr_key)
            db.add(book)
            db.commit()

        return Response(content=result_bytes, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR Error: {str(e)}")


@app.post("/api/analyze")
async def analyze_text(payload: TextActionRequest):
    normalized = payload.text.strip().lower()

    with SessionLocal() as db:
        # 1. Перевіряємо, чи це слово/фраза вже є в PostgreSQL (JSONB)
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
                "result": existing.ai_data.get("text", ""),
                "ai_data": existing.ai_data,
            }

        # 2. Дістаємо JSONB-конфіг промта з БД
        prompt_obj = db.query(PromptTemplate).filter_by(action_key=payload.action).first()
        system_instruction = (
            prompt_obj.config.get("system_prompt")
            if prompt_obj
            else "Проаналізуй наданий фрагмент тексту."
        )

        # 3. Генерація відповіді (тут підключається виклик Gemini / Ollama)
        generated_text = (
            f"[Промт із JSONB: '{system_instruction}']\n\n"
            f"Розбір для «{payload.text}» (збережено в PostgreSQL JSONB)."
        )
        ai_json_payload = {
            "text": generated_text,
            "prompt_used": system_instruction,
            "context": payload.context,
        }

        # 4. Зберігаємо або оновлюємо в PostgreSQL JSONB назавжди
        if existing:
            existing.ai_data = ai_json_payload
        else:
            new_entry = LexiconEntry(
                original_text=payload.text,
                normalized_text=normalized,
                action=payload.action,
                ai_data=ai_json_payload,
            )
            db.add(new_entry)

        db.commit()

        return {
            "status": "ok",
            "from_db": False,
            "action": payload.action,
            "original_text": payload.text,
            "result": generated_text,
            "ai_data": ai_json_payload,
        }
