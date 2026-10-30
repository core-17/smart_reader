import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import api_router
from core.config import settings
from core.database import init_db
from services.storage_service import init_s3_bucket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("smart_reader")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ініціалізація бази даних та сховища S3...")
    init_db()
    init_s3_bucket()
    yield
    logger.info("Завершення роботи застосунку...")


app = FastAPI(title="Smart Reader API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(api_router)