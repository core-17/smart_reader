import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://smartreader:smartreader_password@127.0.0.1:5432/smartreader_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


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
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped[User | None] = relationship(back_populates="books")


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
    _seed_default_prompts()