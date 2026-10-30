from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.database import User, get_db
from services.auth_service import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserLoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    clean_username = payload.username.strip().lower()
    clean_email = payload.email.strip().lower()

    existing = db.query(User).filter(
        or_(User.username == clean_username, User.email == clean_email)
    ).first()

    if existing:
        if existing.username == clean_username:
            raise HTTPException(status_code=400, detail="Користувач із таким нікнеймом уже існує")
        raise HTTPException(status_code=400, detail="Користувач із такою поштою уже існує")

    new_user = User(
        username=clean_username,
        email=clean_email,
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "status": "ok",
        "message": "Користувача успішно зареєстровано",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
        },
    }


@router.post("/login")
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)):
    ident = payload.identifier.strip().lower()

    user = db.query(User).filter(
        or_(User.email == ident, User.username == ident)
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Невірний логін/пошта або пароль")

    return {
        "status": "ok",
        "message": "Успішний вхід",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }