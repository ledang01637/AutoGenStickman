# src/core/security/tokens.py
import jwt
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub":  str(user_id),
        "type": "access",
        "exp":  expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token_package() -> tuple[str, str, datetime]:
    raw_token   = generate_refresh_token()
    hashed      = hash_token(raw_token)
    expire_at   = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return raw_token, hashed, expire_at


def decode_access_token(token: str, verify_exp: bool = True) -> str:
    """
    Decode và validate access token. Trả về user_id (str).
    Raise ValueError với message cụ thể nếu token không hợp lệ.
    Tập trung toàn bộ logic decode tại đây — deps.py chỉ gọi hàm này.
    """
    try:
        payload = jwt.decode(
            token, SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": verify_exp}, 
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Access Token đã hết hạn.")
    except jwt.PyJWTError:
        raise ValueError("Token không hợp lệ.")

    # Chặn refresh token hoặc token loại khác gọi vào API
    if payload.get("type") != "access":
        raise ValueError("Sai loại token.")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Token không chứa user_id.")

    return str(user_id)

def decode_access_token_full(token: str) -> tuple[str, int]:
    """
    Trả về (user_id, exp) — dùng riêng cho logout blacklist.
    """
    try:
        payload = jwt.decode(
            token, SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Access Token đã hết hạn.")
    except jwt.PyJWTError:
        raise ValueError("Token không hợp lệ.")

    if payload.get("type") != "access":
        raise ValueError("Sai loại token.")

    user_id = payload.get("sub")
    exp     = payload.get("exp")  # unix timestamp

    if not user_id or not exp:
        raise ValueError("Token thiếu thông tin.")

    return str(user_id), int(exp)