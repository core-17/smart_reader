import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Імпорти з ваших сервісів

# Імпорти з ваших сервісів
from services.databse import engine, Base, get_db
from services.user import (
    User, UserCreate, UserOut, Token,
    DictionaryEntry, DictionaryEntryCreate,
    get_password_hash, verify_password, create_access_token, get_current_user
)

# Імпорти з об'єднаного файлу AI 
from services.AI_api import DictionaryPromptPayload, LocalAPIService, CloudAPIService
# --- Lifecycle (Керування життєвим циклом) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Створення таблиць при запуску
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Тут можна додати логіку закриття з'єднань, якщо потрібно

app = FastAPI(
    title="Smart Reader API",
    version="0.1.0",
    description="Backend-архітектура для обробки текстового контексту через ШІ",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ініціалізація AI сервісів
local_ai_service = LocalAPIService()
cloud_ai_service = CloudAPIService()

# --- System Routes ---
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "message": "Backend is running flawlessly"}


# --- Auth Routes ---
@app.post("/auth/register", response_model=UserOut, tags=["Auth"], status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Цей Email вже зареєстровано"
        )

    new_user = User(
        email=user_data.email, 
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.post("/auth/login", response_model=Token, tags=["Auth"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невірний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- AI Integration Routes ---
@app.post("/ai/local/dictionary", tags=["AI Integration"])
async def local_dictionary_explain(payload: DictionaryPromptPayload):
    try:
        return await local_ai_service.explain_word(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Local AI Error: {str(exc)}")

@app.post("/ai/cloud/dictionary", tags=["AI Integration"])
async def cloud_dictionary_explain(payload: DictionaryPromptPayload):
    try:
        return await cloud_ai_service.explain_word(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cloud AI Error: {str(exc)}")


# --- Dictionary Routes ---
@app.post("/dictionary/", tags=["Dictionary"], status_code=status.HTTP_201_CREATED)
async def add_to_dictionary(
    entry: DictionaryEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_entry = DictionaryEntry(
        **entry.model_dump(),  # Оновлено з dict() для повної підтримки Pydantic v2
        user_id=current_user.id
    )
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return {"status": "saved", "word": new_entry.word}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)