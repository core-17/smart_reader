from fastapi import APIRouter

from api.analysis import router as analysis_router
from api.auth import router as auth_router
from api.books import router as books_router
from api.rag import router as rag_router
from api.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(books_router)
api_router.include_router(rag_router)
api_router.include_router(analysis_router)