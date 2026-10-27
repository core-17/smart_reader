import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from services.ollama_api import query_ollama
from core.database import Book, LexiconEntry, PromptTemplate, SessionLocal, User, init_db
from services.auth_service import hash_password, verify_password
from services.ocr_service import ALLOWED_LANGS, get_available_ocr_languages, process_pdf_with_ocr
from services.storage_service import (
    delete_pdf_from_s3,
    get_pdf_from_s3,
    init_s3_bucket,
    upload_pdf_to_s3,
)

logger = logging.getLogger("smart_reader")

Action = Literal["translate", "explain", "vocabulary"]
MAX_TEXT_CHARS = 500
MAX_CONTEXT_CHARS = 4000
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "150")) * 1024 * 1024
DEFAULT_SYSTEM_PROMPT = "Проаналізуй наданий фрагмент тексту."
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_s3_bucket()
    yield


app = FastAPI(title="Smart Reader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# --- СХЕМИ ВАЛІДАЦІЇ PYDANTIC ---

class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


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


def _sanitize_filename(name: str | None) -> str:
    base = os.path.basename(name or "") or "book.pdf"
    cleaned = re.sub(r"[^\w.\-]+", "_", base)
    return cleaned[:120]


def _run_ocr_background(book_id: int, lang: str):
    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            return

        try:
            logger.info("Початок фонового OCR для книги ID=%d (%s)", book_id, book.title)
            raw_bytes = get_pdf_from_s3(book.s3_raw_key)
            result_bytes = process_pdf_with_ocr(pdf_bytes=raw_bytes, lang=lang)

            file_id = uuid.uuid4().hex[:8]
            ocr_key = f"ocr/{file_id}_{book.title}"
            upload_pdf_to_s3(ocr_key, result_bytes)

            book.s3_ocr_key = ocr_key
            book.ocr_status = "completed"
            book.ocr_error = None
            db.commit()
            logger.info("OCR успішно завершено для ID=%d", book_id)
        except Exception as e:
            logger.exception("Помилка фонового OCR для книги ID=%d", book_id)
            book.ocr_status = "failed"
            book.ocr_error = str(e)
            db.commit()


# --- ЕНДПОІНТИ АВТОРИЗАЦІЇ ---

@app.post("/api/auth/register")
def register_user(payload: UserRegisterRequest):
    clean_username = payload.username.strip().lower()
    clean_email = payload.email.strip().lower()

    with SessionLocal() as db:
        existing = db.query(User).filter(
            or_(User.username == clean_username, User.email == clean_email)
        ).first()

        if existing:
            if existing.username == clean_username:
                raise HTTPException(status_code=400, detail="Користувач із таким нікнеймом уже існує")
            raise HTTPException(status_code=400, detail="Користувач із такою поштою уже існує")

        new_user = User(
            username=clean_username,
            email=clean_email,
            hashed_password=hash_password(payload.password),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "status": "ok",
            "message": "Користувача успішно зареєстровано",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
            },
        }


@app.post("/api/auth/login")
def login_user(payload: UserLoginRequest):
    ident = payload.identifier.strip().lower()

    with SessionLocal() as db:
        user = db.query(User).filter(
            or_(User.email == ident, User.username == ident)
        ).first()

        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Невірний логін/пошта або пароль")

        return {
            "status": "ok",
            "message": "Успішний вхід",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        }


# --- СИСТЕМНІ ЕНДПОІНТИ ТА ПРОМТИ ---

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
        return [
            {"action_key": p.action_key, "name": p.name, "config": p.config}
            for p in prompts
        ]


# --- РОБОТА З КНИГАМИ ---

@app.get("/api/books")
@app.get("/api/books")
def get_books(user_id: int | None = None):
    with SessionLocal() as db:
        query = db.query(Book)
        if user_id:
            # Книги користувача + усі публічні книги
            query = query.filter(or_(Book.user_id == user_id, Book.is_public == True))
        else:
            # Якщо гість — доступні тільки публічні книги
            query = query.filter(Book.is_public == True)

        books = query.order_by(Book.id.desc()).all()
        return [
            {
                "id": b.id,
                "title": b.title,
                "has_ocr": bool(b.s3_ocr_key and b.ocr_status == "completed"),
                "ocr_status": b.ocr_status,
                "ocr_error": b.ocr_error,
                "is_public": b.is_public,
                "user_id": b.user_id,
                "is_mine": bool(user_id and b.user_id == user_id),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in books
        ]

@app.post("/api/books/upload")
def upload_book(
    file: UploadFile = File(...),
    is_public: bool = Form(False),
    user_id: int | None = Form(None),
):
    pdf_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл завеликий")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Очікувався PDF-файл")

    file_id = uuid.uuid4().hex[:8]
    safe_name = _sanitize_filename(file.filename)
    raw_key = upload_pdf_to_s3(f"raw/{file_id}_{safe_name}", pdf_bytes)

    with SessionLocal() as db:
        book = Book(
            title=safe_name,
            s3_raw_key=raw_key,
            s3_ocr_key=None,
            ocr_status="not_started",
            is_public=is_public,
            user_id=user_id,
        )
        db.add(book)
        db.commit()
        db.refresh(book)

        return {
            "status": "ok",
            "book": {
                "id": book.id,
                "title": book.title,
                "ocr_status": book.ocr_status,
                "is_public": book.is_public,
                "user_id": book.user_id,
            },
        }
@app.post("/api/books/{book_id}/ocr")
def start_book_ocr(
    book_id: int,
    background_tasks: BackgroundTasks,
    lang: str = Form("ukr+eng"),
):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail="Непідтримувана мова OCR")

    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Книгу не знайдено")

        if book.ocr_status == "processing":
            raise HTTPException(status_code=409, detail="OCR для цієї книги вже виконується")

        book.ocr_status = "processing"
        book.ocr_error = None
        db.commit()

        background_tasks.add_task(_run_ocr_background, book_id=book.id, lang=lang)

        return {"status": "processing", "message": "OCR запущено у фоні"}
@app.get("/api/books/{book_id}/status")
def get_book_status(book_id: int):
    """Швидкий точковий ендпоінт для перевірки статусу OCR конкретної книги."""
    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Книгу не знайдено")
        return {
            "id": book.id,
            "has_ocr": bool(book.s3_ocr_key and book.ocr_status == "completed"),
            "ocr_status": book.ocr_status,
            "ocr_error": book.ocr_error,
        }

@app.get("/api/books/{book_id}/pdf")
def get_book_pdf(book_id: int, version: Literal["raw", "ocr"] = "raw"):
    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Книгу не знайдено")

        s3_key = book.s3_ocr_key if (version == "ocr" and book.s3_ocr_key) else book.s3_raw_key

        try:
            pdf_bytes = get_pdf_from_s3(s3_key)
            return Response(content=pdf_bytes, media_type="application/pdf")
        except Exception:
            raise HTTPException(status_code=500, detail="Не вдалося отримати PDF зі сховища S3")


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int):
    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Книгу не знайдено")

        if book.s3_raw_key:
            delete_pdf_from_s3(book.s3_raw_key)
        if book.s3_ocr_key:
            delete_pdf_from_s3(book.s3_ocr_key)

        db.delete(book)
        db.commit()

        return {"status": "ok", "message": "Книгу видалено"}


# --- АНАЛІЗ ТА ШІ ---

@app.post("/api/analyze")
def analyze_text(payload: TextActionRequest):
    normalized = payload.text.lower()

    with SessionLocal() as db:
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