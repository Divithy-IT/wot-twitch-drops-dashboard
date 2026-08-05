import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

ph = PasswordHasher()


def hash_password(value: str) -> str:
    return ph.hash(value)


def verify_password(stored: str, value: str) -> bool:
    try:
        return ph.verify(stored, value)
    except Exception:
        return False


def encrypt_token(value: str) -> str:
    return Fernet(get_settings().token_encryption_key.encode()).encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    return Fernet(get_settings().token_encryption_key.encode()).decrypt(value.encode()).decode()


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="wot-session")


def make_session(admin_id: int, version: int) -> str:
    return serializer().dumps({"admin_id": admin_id, "version": version})


def read_session(request: Request) -> dict:
    token = request.cookies.get("wot_session")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wymagane logowanie")
    try:
        return serializer().loads(token, max_age=get_settings().session_hours * 3600)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesja wygasła") from exc


def csrf_token(request: Request) -> str:
    return request.cookies.get("wot_csrf") or secrets.token_urlsafe(32)


def require_csrf(request: Request) -> None:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        cookie = request.cookies.get("wot_csrf")
        header = request.headers.get("x-csrf-token")
        if not cookie or not header or not secrets.compare_digest(cookie, header):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Nieprawidłowy token CSRF")


def expiry(seconds: int) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=seconds)
