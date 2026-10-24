from datetime import datetime
from sqlalchemy import create_engine, String, Integer, DateTime, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = "postgresql+psycopg://smartreader:smartreader_password@127.0.0.1:5432/smartreader_db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Book(Base):
    """Метадані книги та посилання на файли в SeaweedFS (S3)."""
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    s3_raw_key: Mapped[str] = mapped_column(String(512))
    s3_ocr_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromptTemplate(Base):
    """Гнучкі шаблони промтів у форматі NoSQL (JSONB)."""
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # translate, explain, vocabulary
    name: Mapped[str] = mapped_column(String(128))
    # У config лежить будь-яка JSON-структура: system_prompt, variables, model_settings, examples
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class LexiconEntry(Base):
    """
    Кеш/база всіх уже перекладених або пояснених слів та фраз.
    Якщо слово вже питали — береться звідси без повторного звернення до ШІ.
    """
    __tablename__ = "lexicon_entries"
    __table_args__ = (
        UniqueConstraint("normalized_text", "action", name="uq_lexicon_text_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(String(512), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    # Гнучка JSONB-відповідь ШІ (переклад, граматика, приклади, синоніми тощо)
    ai_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db():
    with engine.begin() as conn:
        # Вмикаємо векторне розширення pgvector для майбутнього RAG по книзі
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # Додаємо дефолтні промти в JSONB, якщо таблиця порожня
    with SessionLocal() as db:
        if db.query(PromptTemplate).count() == 0:
            default_prompts = [
                PromptTemplate(
                    action_key="translate",
                    name="Контекстний переклад",
                    config={
                        "system_prompt": "Переклади фрагмент українською мовою та дай коротке пояснення значення.",
                        "temperature": 0.2,
                        "variables": ["selected_text", "context"],
                    },
                ),
                PromptTemplate(
                    action_key="explain",
                    name="Пояснення простими словами",
                    config={
                        "system_prompt": "Поясни суть цього речення або терміна простими словами.",
                        "temperature": 0.3,
                        "variables": ["selected_text"],
                    },
                ),
                PromptTemplate(
                    action_key="vocabulary",
                    name="Словникова картка",
                    config={
                        "system_prompt": "Сформуй картку: Слово | Переклад | Частина мови | Приклад речення.",
                        "temperature": 0.2,
                        "variables": ["selected_text"],
                    },
                ),
            ]
            db.add_all(default_prompts)
            db.commit()
