import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://smartreader:smartreader_password@127.0.0.1:5432/smartreader_db"
    )

    PASSWORD_PEPPER: str = Field(
        default="smart_reader_super_secret_pepper_2026",
        min_length=16,
    )

    # S3 / SeaweedFS
    S3_ENDPOINT: str = Field(default="http://127.0.0.1:8333")
    S3_ACCESS_KEY: str = Field(default="smartreader_key")
    S3_SECRET_KEY: str = Field(default="smartreader_secret")
    S3_BUCKET: str = Field(default="smart-reader-books")
    S3_REGION: str = Field(default="us-east-1")

    # Ollama
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434")
    OLLAMA_MODEL: str = Field(default="gemma4:12b")
    OLLAMA_EMBED_MODEL: str = Field(default="bge-m3")

    # RAG
    RAG_CHUNK_SIZE: int = Field(default=900)
    RAG_CHUNK_OVERLAP: int = Field(default=150)
    RAG_TOP_K: int = Field(default=5)

    # Завантаження та CORS
    MAX_UPLOAD_MB: int = Field(default=150, gt=0)
    CORS_ORIGINS_RAW: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.CORS_ORIGINS_RAW.split(",") if item.strip()]

    @field_validator("PASSWORD_PEPPER")
    @classmethod
    def validate_pepper(cls, value: str) -> str:
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production" and value == "smart_reader_super_secret_pepper_2026":
            raise ValueError("У production заборонено використовувати стандартний PASSWORD_PEPPER!")
        return value

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH if ENV_FILE_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()