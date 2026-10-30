from datetime import datetime, timezone
from typing import Generator

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    books: Mapped[list["Book"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    s3_raw_key: Mapped[str] = mapped_column(String(512))
    s3_ocr_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ocr_status: Mapped[str] = mapped_column(String(32), default="not_started")
    ocr_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    rag_status: Mapped[str] = mapped_column(String(32), default="not_indexed")
    rag_progress: Mapped[int] = mapped_column(Integer, default=0)
    rag_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped[User | None] = relationship(back_populates="books")
    chunks: Mapped[list["BookChunk"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class BookChunk(Base):
    __tablename__ = "book_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    book: Mapped[Book] = relationship(back_populates="chunks")


class PromptTemplate(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class LexiconEntry(Base):
    __tablename__ = "lexicon_entries"
    __table_args__ = (
        UniqueConstraint("normalized_text", "action", name="uq_lexicon_text_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(String(512), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    ai_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


DEFAULT_PROMPTS = [
    {
        "action_key": "translate",
        "name": "Контекстний переклад",
        "config": {
            "system_prompt": "Переклади фрагмент українською мовою та дай коротке пояснення значення.",
            "temperature": 0.2,
            "variables": ["selected_text", "context"],
        },
    },
    {
        "action_key": "explain",
        "name": "Пояснення простими словами",
        "config": {
            "system_prompt": "Поясни суть цього речення або терміна простими словами.",
            "temperature": 0.3,
            "variables": ["selected_text"],
        },
    },
    {
        "action_key": "vocabulary",
        "name": "Словникова картка",
        "config": {
            "system_prompt": "Сформуй картку: Слово | Переклад | Частина мови | Приклад речення.",
            "temperature": 0.2,
            "variables": ["selected_text"],
        },
    },
]


def _seed_default_prompts() -> None:
    with SessionLocal() as db:
        if db.query(PromptTemplate).count() > 0:
            return
        db.add_all(PromptTemplate(**prompt) for prompt in DEFAULT_PROMPTS)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS rag_status VARCHAR(32) DEFAULT 'not_indexed'"))
        conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS rag_progress INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS rag_error TEXT"))
    _seed_default_prompts()