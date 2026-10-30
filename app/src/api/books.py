import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Book, SessionLocal, get_db
from services.ocr_service import ALLOWED_LANGS, process_pdf_with_ocr
from services.storage_service import delete_pdf_from_s3, get_pdf_from_s3, upload_pdf_to_s3

logger = logging.getLogger("smart_reader.books")
router = APIRouter(prefix="/api/books", tags=["Books"])


def _sanitize_filename(name: str | None) -> str:
    base = re.sub(r"[^\w.\-]+", "_", (name or "").strip()) or "book.pdf"
    return base[:120]


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


@router.get("")
def get_books(user_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Book)
    if user_id:
        query = query.filter(or_(Book.user_id == user_id, Book.is_public == True))
    else:
        query = query.filter(Book.is_public == True)

    books = query.order_by(Book.id.desc()).all()
    return [
        {
            "id": b.id,
            "title": b.title,
            "has_ocr": bool(b.s3_ocr_key and b.ocr_status == "completed"),
            "ocr_status": b.ocr_status,
            "ocr_error": b.ocr_error,
            "has_rag": b.rag_status == "completed",
            "rag_status": b.rag_status,
            "rag_progress": b.rag_progress,
            "is_public": b.is_public,
            "user_id": b.user_id,
            "is_mine": bool(user_id and b.user_id == user_id),
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in books
    ]


@router.post("/upload")
def upload_book(
    file: UploadFile = File(...),
    is_public: bool = Form(False),
    user_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    pdf_bytes = file.file.read(settings.max_upload_bytes + 1)
    if len(pdf_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Файл завеликий")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Очікувався PDF-файл")

    file_id = uuid.uuid4().hex[:8]
    safe_name = _sanitize_filename(file.filename)
    raw_key = upload_pdf_to_s3(f"raw/{file_id}_{safe_name}", pdf_bytes)

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


@router.post("/{book_id}/ocr")
def start_book_ocr(
    book_id: int,
    background_tasks: BackgroundTasks,
    lang: str = Form("ukr+eng"),
    db: Session = Depends(get_db),
):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail="Непідтримувана мова OCR")

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


@router.get("/{book_id}/status")
def get_book_status(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter_by(id=book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Книгу не знайдено")
    return {
        "id": book.id,
        "has_ocr": bool(book.s3_ocr_key and book.ocr_status == "completed"),
        "ocr_status": book.ocr_status,
        "ocr_error": book.ocr_error,
        "has_rag": book.rag_status == "completed",
        "rag_status": book.rag_status,
        "rag_progress": book.rag_progress,
    }


@router.get("/{book_id}/pdf")
def get_book_pdf(
    book_id: int,
    version: Literal["raw", "ocr"] = "raw",
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter_by(id=book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Книгу не знайдено")

    s3_key = book.s3_ocr_key if (version == "ocr" and book.s3_ocr_key) else book.s3_raw_key

    try:
        pdf_bytes = get_pdf_from_s3(s3_key)
        return Response(content=pdf_bytes, media_type="application/pdf")
    except Exception:
        raise HTTPException(status_code=500, detail="Не вдалося отримати PDF зі сховища S3")


@router.delete("/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
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