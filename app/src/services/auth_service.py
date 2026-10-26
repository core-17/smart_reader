import hashlib
import hmac
import os
import bcrypt

# Pepper зберігається у змінних середовища сервера, а не в базі даних
PEPPER = os.getenv("PASSWORD_PEPPER", "smart_reader_super_secret_pepper_2026").encode("utf-8")


def _pepper_password(raw_password: str) -> bytes:
    """Підмішує секретний pepper та нормалізує довжину до 32 байт перед bcrypt."""
    return hmac.new(PEPPER, raw_password.encode("utf-8"), hashlib.sha256).digest()


def hash_password(raw_password: str) -> str:
    """Хешує нормалізований пароль за допомогою bcrypt із сіллю."""
    prepared = _pepper_password(raw_password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(prepared, salt).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """Перевіряє відповідність пароля збереженому хешу."""
    prepared = _pepper_password(raw_password)
    try:
        return bcrypt.checkpw(prepared, hashed_password.encode("utf-8"))
    except ValueError:
        return False