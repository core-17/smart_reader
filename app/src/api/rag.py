import json
import logging
from typing import Generator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Book, BookChunk, get_db
from services.ollama_api import query_ollama, stream_ollama_chat
from services.rag_service import index_book_background, retrieve_relevant_chunks

logger = logging.getLogger("smart_reader.api.rag")
router = APIRouter(prefix="/api/books", tags=["RAG"])

RAG_SYSTEM_PROMPT = (
    "Ти — інтелектуальний асистент для читання книг. "
    "Відповідай на запитання користувача ВИКЛЮЧНО на основі наданих фрагментів книги. "
    "Обов'язково вказуй номери сторінок у дужках, наприклад: (стор. 14). "
    "Якщо у наданих фрагментах немає відповіді на запитання, чесно скажи про це."
)


class BookAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=settings.RAG_TOP_K, ge=1, le=15)
    stream: bool = Field(default=True)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Запитання не може бути порожнім")
        return cleaned


def _format_rag_context(chunks: list[dict]) -> str:
    blocks = []
    for idx, ch in enumerate(chunks, start=1):
        blocks.append(f"[Фрагмент #{idx} | Сторінка {ch['page_number']}]\n{ch['content']}")
    return "\n\n---\n\n".join(blocks)


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{book_id}/rag/index")
def start_book_rag_indexing(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter_by(id=book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Книгу не знайдено")

    if book.rag_status == "indexing":
        raise HTTPException(status_code=409, detail="Індексація цієї книги вже виконується")

    book.rag_status = "indexing"
    book.rag_progress = 0
    book.rag_error = None
    db.commit()

    background_tasks.add_task(index_book_background, book_id=book.id)

    return {
        "status": "indexing",
        "message": "RAG-індексацію книги запущено у фоні",
        "book_id": book.id,
    }


@router.get("/{book_id}/rag/status")
def get_book_rag_status(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter_by(id=book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Книгу не знайдено")

    chunks_count = db.query(func.count(BookChunk.id)).filter_by(book_id=book_id).scalar() or 0

    return {
        "book_id": book.id,
        "title": book.title,
        "rag_status": book.rag_status,
        "rag_progress": book.rag_progress,
        "chunks_count": chunks_count,
        "has_rag": book.rag_status == "completed" and chunks_count > 0,
        "rag_error": book.rag_error,
    }


@router.post("/{book_id}/rag/ask")
def ask_book_question(
    book_id: int,
    payload: BookAskRequest,
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter_by(id=book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Книгу не знайдено")

    if book.rag_status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Книга ще не проіндексована для RAG (поточний статус: {book.rag_status})",
        )

    if payload.stream:
        def event_generator() -> Generator[str, None, None]:
            try:
                yield _sse_event({
                    "stage": "embedding_query",
                    "spinner": "⠋",
                    "message": "Аналізуємо ваше запитання...",
                })

                chunks = retrieve_relevant_chunks(
                    db=db,
                    book_id=book_id,
                    question=payload.question,
                    top_k=payload.top_k,
                )

                if not chunks:
                    yield _sse_event({
                        "stage": "error",
                        "message": "Не знайдено релевантних фрагментів у книзі.",
                    })
                    return

                pages = sorted({c["page_number"] for c in chunks})
                yield _sse_event({
                    "stage": "chunks_found",
                    "spinner": "⠸",
                    "message": f"Знайдено релевантні фрагменти на сторінках: {', '.join(map(str, pages))}. Генеруємо відповідь...",
                    "pages": pages,
                    "sources": chunks,
                })

                context_text = _format_rag_context(chunks)
                user_prompt = f"Фрагменти з книги «{book.title}»:\n\n{context_text}\n\nЗапитання користувача:\n{payload.question}"

                full_answer = []
                for token in stream_ollama_chat(
                    system_prompt=RAG_SYSTEM_PROMPT,
                    user_content=user_prompt,
                    temperature=0.2,
                ):
                    full_answer.append(token)
                    yield _sse_event({
                        "stage": "generating",
                        "token": token,
                    })

                yield _sse_event({
                    "stage": "done",
                    "message": "Відповідь сформовано",
                    "answer": "".join(full_answer).strip(),
                    "pages": pages,
                })
            except Exception as e:
                logger.exception("Помилка під час RAG-відповіді для книги ID=%d", book_id)
                yield _sse_event({"stage": "error", "message": str(e)})

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    chunks = retrieve_relevant_chunks(
        db=db,
        book_id=book_id,
        question=payload.question,
        top_k=payload.top_k,
    )
    context_text = _format_rag_context(chunks)
    answer = query_ollama(
        system_prompt=RAG_SYSTEM_PROMPT,
        user_text=payload.question,
        context=context_text,
        temperature=0.2,
    )

    return {
        "status": "ok",
        "book_id": book.id,
        "question": payload.question,
        "answer": answer,
        "sources": chunks,
    }