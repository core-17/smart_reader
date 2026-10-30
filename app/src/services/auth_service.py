import hashlib
import hmac

import bcrypt

from core.config import settings

PEPPER = settings.PASSWORD_PEPPER.encode("utf-8")


def _pepper_password(raw_password: str) -> bytes:
    return hmac.new(PEPPER, raw_password.encode("utf-8"), hashlib.sha256).digest()


def hash_password(raw_password: str) -> str:
    prepared = _pepper_password(raw_password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(prepared, salt).decode("utf-8")


def verify_password(raw_password: str, hashed_password: str) -> bool:
    prepared = _pepper_password(raw_password)
    try:
        return bcrypt.checkpw(prepared, hashed_password.encode("utf-8"))
    except ValueError:
        return False