import logging
import re
import time
from typing import Any

import pymupdf
from sqlalchemy import delete
from sqlalchemy.orm import Session

from core.config import settings
from core.database import Book, BookChunk, SessionLocal
from services.ollama_api import get_embeddings
from services.storage_service import get_pdf_from_s3

logger = logging.getLogger("smart_reader.rag")
BATCH_SIZE = 16


def extract_chunks_from_pdf(
    pdf_bytes: bytes,
    chunk_size: int = settings.RAG_CHUNK_SIZE,
    overlap: int = settings.RAG_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    chunks: list[dict[str, Any]] = []
    chunk_idx = 0

    try:
        for page_num in range(len(doc)):
            raw_text = doc[page_num].get_text("text")
            clean_text = re.sub(r"\s+", " ", raw_text).strip()
            if len(clean_text) < 30:
                continue

            start = 0
            text_len = len(clean_text)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                if end < text_len:
                    last_space = clean_text.rfind(" ", start + chunk_size // 2, end)
                    if last_space != -1:
                        end = last_space

                snippet = clean_text[start:end].strip()
                if len(snippet) >= 30:
                    chunks.append(
                        {
                            "page_number": page_num + 1,
                            "chunk_index": chunk_idx,
                            "content": snippet,
                        }
                    )
                    chunk_idx += 1

                if end >= text_len:
                    break
                start = max(end - overlap, start + 1)
    finally:
        doc.close()

    return chunks


def index_book_background(book_id: int) -> None:
    start_ts = time.perf_counter()
    with SessionLocal() as db:
        book = db.query(Book).filter_by(id=book_id).first()
        if not book:
            return

        try:
            s3_key = book.s3_ocr_key if (book.ocr_status == "completed" and book.s3_ocr_key) else book.s3_raw_key
            logger.info("📚 [RAG Index] Початок індексації книги ID=%d ('%s'), джерело=%s", book_id, book.title, s3_key)

            book.rag_status = "indexing"
            book.rag_progress = 5
            book.rag_error = None
            db.commit()

            pdf_bytes = get_pdf_from_s3(s3_key)
            raw_chunks = extract_chunks_from_pdf(pdf_bytes)

            if not raw_chunks:
                raise ValueError("У книзі не знайдено текстового шару. Спочатку виконайте OCR.")

            total_chunks = len(raw_chunks)
            logger.info("✂️ [RAG Index] Книгу ID=%d розбито на %d текстових фрагментів", book_id, total_chunks)

            db.execute(delete(BookChunk).where(BookChunk.book_id == book_id))
            db.commit()

            for i in range(0, total_chunks, BATCH_SIZE):
                batch = raw_chunks[i : i + BATCH_SIZE]
                texts = [item["content"] for item in batch]
                vectors = get_embeddings(texts)

                db_chunks = [
                    BookChunk(
                        book_id=book_id,
                        page_number=item["page_number"],
                        chunk_index=item["chunk_index"],
                        content=item["content"],
                        embedding=vec,
                    )
                    for item, vec in zip(batch, vectors)
                ]
                db.add_all(db_chunks)

                processed = min(i + BATCH_SIZE, total_chunks)
                progress = min(99, int((processed / total_chunks) * 95) + 5)
                book.rag_progress = progress
                db.commit()

                logger.info(
                    "📊 [RAG Index] Книга ID=%d: оброблено %d/%d чанків (%d%%)",
                    book_id,
                    processed,
                    total_chunks,
                    progress,
                )

            book.rag_status = "completed"
            book.rag_progress = 100
            book.rag_error = None
            db.commit()

            elapsed = time.perf_counter() - start_ts
            logger.info("🎉 [RAG Index] Індексацію книги ID=%d успішно завершено за %.2f сек!", book_id, elapsed)

        except Exception as e:
            logger.exception("❌ [RAG Index] Помилка індексації книги ID=%d", book_id)
            book.rag_status = "failed"
            book.rag_error = str(e)
            db.commit()


def retrieve_relevant_chunks(
    db: Session,
    book_id: int,
    question: str,
    top_k: int = settings.RAG_TOP_K,
) -> list[dict[str, Any]]:
    logger.info("🔍 [RAG Search] Пошук фрагментів для книги ID=%d: '%s'", book_id, question[:80])
    query_vec = get_embeddings([question])[0]

    distance_col = BookChunk.embedding.cosine_distance(query_vec).label("distance")
    rows = (
        db.query(BookChunk, distance_col)
        .filter(BookChunk.book_id == book_id)
        .order_by(distance_col.asc())
        .limit(top_k)
        .all()
    )

    results = []
    for chunk, distance in rows:
        similarity = round(max(0.0, 1.0 - float(distance)), 4)
        results.append(
            {
                "chunk_id": chunk.id,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "similarity": similarity,
            }
        )

    pages = sorted({r["page_number"] for r in results})
    logger.info("📑 [RAG Search] Знайдено %d фрагментів на сторінках: %s", len(results), pages)
    return results