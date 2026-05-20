from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ConfigDict
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, select
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

# Враховуючи ваш специфічний імпорт 'databse'
from services.databse import Base, get_db
from services.config import settings

# --- 1. БЕЗПЕКА ТА AUTH КОНТЕКСТ ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# --- 2. SQLALCHEMY МОДЕЛІ (Таблиці) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Зв'язок: один користувач має багато слів у словнику
    dictionary_entries = relationship("DictionaryEntry", back_populates="owner", cascade="all, delete-orphan")
    # Зв'язки
    dictionary_entries = relationship("DictionaryEntry", back_populates="owner", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Налаштування ШІ: 'local' або 'cloud'
    ai_provider = Column(String, default="local", nullable=False) 

    user = relationship("User", back_populates="settings")


class DictionaryEntry(Base):
    __tablename__ = "dictionary_entries"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, index=True, nullable=False)
    translation = Column(String, nullable=False)
    context = Column(Text, nullable=True)  # Текст з оригінального джерела (PDF тощо)
    notes = Column(Text, nullable=True)    # Пояснення від AI
    context = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="dictionary_entries")


# --- 3. PYDANTIC СХЕМИ (Валідація) ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class UserSettingsUpdate(BaseModel):
    ai_provider: str = Field(..., description="Тип провайдера: 'local' або 'cloud'")

class UserSettingsOut(BaseModel):
    ai_provider: str
    model_config = ConfigDict(from_attributes=True)

class DictionaryEntryCreate(BaseModel):
    word: str
    translation: str
    context: str | None = None
    notes: str | None = None

class DictionaryEntryOut(DictionaryEntryCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- 4. ЗАЛЕЖНОСТІ (Dependencies) ---
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося перевірити токен доступу",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Правильне підвантаження зв'язаної таблиці settings
    from sqlalchemy.orm import selectinload
    stmt = select(User).where(User.email == email).options(selectinload(User.settings))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user