import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

# Імпорти з локальних сервісів
from services.databse import engine, Base, get_db
from services.user import (
    User, UserCreate, UserOut, Token,
    DictionaryEntry, DictionaryEntryCreate, UserSettings, UserSettingsUpdate, UserSettingsOut,
    get_password_hash, verify_password, create_access_token, get_current_user
)
from services.AI_api import DictionaryPromptPayload, LocalAPIService, CloudAPIService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматичне створення нових таблиць (включаючи user_settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Smart Reader API",
    version="0.2.0",
    description="Backend-архітектура з вибором AI провайдера через базу даних",
    lifespan=lifespan
)

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
    # Перевіряємо, чи існує користувач з таким email АБО username
    stmt = select(User).where(
        or_(
            User.email == user_data.email,
            User.username == user_data.username
        )
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Цей Email вже зареєстровано"
            )
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Цей Нікнейм вже зайнято"
            )

    # Створюємо користувача з урахуванням поля username
    new_user = User(
        username=user_data.username,
        email=user_data.email, 
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(new_user)
    await db.flush()  # Отримуємо id користувача перед комітом

    # Створюємо дефолтні налаштування для нового користувача (за замовчуванням локальний ШІ)
    default_settings = UserSettings(user_id=new_user.id, ai_provider="local")
    db.add(default_settings)
    
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


# --- User Settings Routes ---
@app.get("/user/settings", response_model=UserSettingsOut, tags=["User Settings"])
async def get_user_settings(current_user: User = Depends(get_current_user)):
    if not current_user.settings:
        return {"ai_provider": "local"}
    return current_user.settings

@app.put("/user/settings", response_model=UserSettingsOut, tags=["User Settings"])
async def update_user_settings(
    settings_data: UserSettingsUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if settings_data.ai_provider not in ["local", "cloud"]:
        raise HTTPException(status_code=400, detail="ai_provider має бути або 'local', або 'cloud'")
    
    if not current_user.settings:
        current_user.settings = UserSettings(user_id=current_user.id, ai_provider=settings_data.ai_provider)
        db.add(current_user.settings)
    else:
        current_user.settings.ai_provider = settings_data.ai_provider
        
    await db.commit()
    return current_user.settings


# --- ОБ'ЄДНАНИЙ AI ЕНДПОІНТ ---
@app.post("/ai/dictionary", tags=["AI Integration"])
async def explain_word_smart(
    payload: DictionaryPromptPayload,
    current_user: User = Depends(get_current_user)
):
    provider = current_user.settings.ai_provider if current_user.settings else "local"
    
    if provider == "local":
        try:
            return await local_ai_service.explain_word(payload)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Local AI Error: {str(exc)}")
    else:
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
        **entry.model_dump(),
        user_id=current_user.id
    )
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return {"status": "saved", "word": new_entry.word}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)