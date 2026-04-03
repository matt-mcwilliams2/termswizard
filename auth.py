import os
import bcrypt
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from database import get_db_context

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_jwt(user_id: int, email: str, is_admin: bool = False) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_jwt(token)


def require_admin(request: Request) -> dict:
    user = get_current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def generate_password(length: int = 12) -> str:
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def create_reset_token(user_id: int) -> str:
    token = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at.isoformat()),
        )
    return token


def verify_reset_token(token: str) -> int | None:
    with get_db_context() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at, used FROM password_reset_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None
        if row["used"]:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return None
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,)
        )
        return row["user_id"]
