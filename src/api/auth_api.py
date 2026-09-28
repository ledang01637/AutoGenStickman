# src/api/auth_api.py
import jwt
import os
from datetime import datetime, timedelta, timezone

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import APIRouter, Depends, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func,cast, Date
from fastapi import Request

from src.core.rate_limit_policy import RateLimit

from ..utils.logger import get_logger
from src.core.database.db import get_db
from src.core.middleware import limiter, get_real_ip
from src.core.database.models import User, CreditBatch
from src.core.database.schemas import (
    ApiResult, CRUDStatusCodeRes,
    LoginRequest, GoogleAuthRequest, UserProfileDTO,
)
from src.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token_package,
    decode_access_token,
    hash_token,
)
from src.api.user_api import pwd_context

logger   = get_logger(__name__)
router   = APIRouter()

COOKIE_SECURE   = os.getenv("COOKIE_SECURE", "False").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

# ── Helper: set cả 2 cookie 1 chỗ ───────────────────────────────────────────
def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_max_age: int  = 60 * 60,
    refresh_max_age: int = 7 * 24 * 3600,
):
    kw = dict(httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.set_cookie("access_token",  access_token,  max_age=access_max_age,  **kw)
    response.set_cookie("refresh_token", refresh_token, max_age=refresh_max_age, **kw)


# ── Helper: tính tổng credit còn lại của user ────────────────────────────────
async def _get_total_credits(db: AsyncSession, user_id) -> int:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.coalesce(func.sum(CreditBatch.remaining_credits), 0))
        .where(
            CreditBatch.user_id   == user_id,
            CreditBatch.expires_at > now,
            CreditBatch.remaining_credits > 0,
        )
    )
    return int(result.scalar_one())


# ─────────────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=ApiResult[UserProfileDTO])
@limiter.limit(RateLimit.LOGIN, key_func=RateLimit.KEY_IP)
async def login(
    request: Request,
    response:    Response,
    credentials: LoginRequest,
    db:          AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user   = result.scalars().first()

    if not user or not user.password_hash:
        return ApiResult.error("Sai tài khoản hoặc mật khẩu", code=CRUDStatusCodeRes.UNAUTHORIZED)
    if not pwd_context.verify(credentials.password[:72], user.password_hash):
        return ApiResult.error("Sai tài khoản hoặc mật khẩu", code=CRUDStatusCodeRes.UNAUTHORIZED)

    access_token                  = create_access_token(user.id)
    raw_rt, hashed_rt, expire_at  = create_refresh_token_package()
    user.refresh_token             = hashed_rt
    user.refresh_token_expires_at  = expire_at
    await db.commit()

    _set_auth_cookies(response, access_token, raw_rt)

    credits = await _get_total_credits(db, user.id)
    return ApiResult.success(
        data=UserProfileDTO(
            id=str(user.id), email=user.email,
            full_name=user.full_name, avatar_url=user.avatar_url,
            role=user.role, credit=credits,
        ),
        message="Đăng nhập thành công",
    )

# ─────────────────────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=ApiResult[None])
@limiter.limit(RateLimit.REFRESH_TOKEN, key_func=RateLimit.KEY_USER)
async def refresh_token(
    request: Request,
    response:      Response,
    refresh_token: str | None = Cookie(None),
    db:            AsyncSession = Depends(get_db),
):
    if not refresh_token:
        return ApiResult.error("Không tìm thấy Refresh Token.", code=CRUDStatusCodeRes.UNAUTHORIZED)

    hashed = hash_token(refresh_token)
    now    = datetime.now(timezone.utc)   # ✅ aware datetime, không dùng utcnow()

    result = await db.execute(
        select(User).where(
            User.refresh_token == hashed,
            User.refresh_token_expires_at > now,   # ✅ so sánh cùng type
        )
    )
    user = result.scalars().first()
    if not user:
        return ApiResult.error("Refresh Token không hợp lệ hoặc đã hết hạn.", code=CRUDStatusCodeRes.UNAUTHORIZED)

    # Token Rotation: cấp refresh token mới mỗi lần refresh
    # → nếu refresh token cũ bị đánh cắp và dùng lại, hệ thống phát hiện ngay
    new_access               = create_access_token(user.id)
    new_raw_rt, new_hashed_rt, new_expire = create_refresh_token_package()
    user.refresh_token            = new_hashed_rt
    user.refresh_token_expires_at = new_expire
    await db.commit()

    _set_auth_cookies(response, new_access, new_raw_rt)
    return ApiResult.success(message="Làm mới Token thành công")


# ─────────────────────────────────────────────────────────────────────────────
@router.post("/logout", response_model=ApiResult[None])
async def logout(
    response:     Response,
    access_token: str | None = Cookie(None),
    db:           AsyncSession = Depends(get_db),
):
    response.delete_cookie("access_token",  httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)

    if not access_token:
        return ApiResult.success(message="Đã đăng xuất")

    try:
        user_id = decode_access_token(access_token, False) 
    except ValueError:
        return ApiResult.success(message="Đăng xuất thành công")

    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalars().first()
    if user:
        user.refresh_token            = None
        user.refresh_token_expires_at = None
        await db.commit()

    return ApiResult.success(message="Đăng xuất thành công")


@router.post("/login-google", response_model=ApiResult[UserProfileDTO])
@limiter.limit(RateLimit.LOGIN, key_func=RateLimit.KEY_IP)
async def login_google(
    request: Request,
    response:    Response,
    credentials: GoogleAuthRequest,
    db:          AsyncSession = Depends(get_db),
):
    try:
        idinfo = id_token.verify_oauth2_token(
            credentials.token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except ValueError:
        return ApiResult.error("Token Google không hợp lệ hoặc đã hết hạn.", code=CRUDStatusCodeRes.UNAUTHORIZED)

    google_email  = idinfo["email"]
    google_name   = idinfo.get("name")
    google_avatar = idinfo.get("picture")
    google_id     = idinfo["sub"]

    result = await db.execute(select(User).where(User.email == google_email))
    user   = result.scalars().first()
    is_new = user is None

    if is_new:
        real_ip = get_real_ip(request)
        today   = datetime.now(timezone.utc).date()

        count_result = await db.execute(
            select(func.count(User.id)).where(
                cast(User.created_at, Date) == today,
                User.registration_ip == real_ip,
            )
        )
        daily_count = count_result.scalar_one()

        if daily_count >= 3:  
            return ApiResult.error(
                "Đã đạt giới hạn tạo tài khoản mới. Vui lòng thử lại sao.",
                code=CRUDStatusCodeRes.TOO_MANY_REQUESTS,
            )

    if is_new:
        user = User(
            email=google_email,
            full_name=google_name,
            avatar_url=google_avatar,
            auth_provider="google",
            provider_id=google_id,
            password_hash=None,
            registration_ip=get_real_ip(request),  
            plan="Free",
        )
        db.add(user)
        await db.flush()
    else:
        user.full_name     = google_name
        user.avatar_url    = google_avatar
        user.auth_provider = "google"
        user.provider_id   = google_id

    access_token                 = create_access_token(user.id)
    raw_rt, hashed_rt, expire_at = create_refresh_token_package()
    user.refresh_token            = hashed_rt
    user.refresh_token_expires_at = expire_at

    WELCOME_CREDITS = 15
    if is_new:
        db.add(CreditBatch(
            user_id=user.id,
            total_credits=WELCOME_CREDITS,
            remaining_credits=WELCOME_CREDITS,
            source="welcome bonus",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        ))

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as exc:
        await db.rollback()
        logger.exception("Lỗi Google login: %s", exc)
        return ApiResult.error("Lỗi hệ thống.", code=CRUDStatusCodeRes.INTERNAL_SERVER_ERROR)

    _set_auth_cookies(response, access_token, raw_rt)

    credits = WELCOME_CREDITS if is_new else await _get_total_credits(db, user.id)

    logger.info("Google login | user=%s | new=%s | ip=%s", user.email, is_new, get_real_ip(request))
    return ApiResult.success(
        data=UserProfileDTO(
            id=str(user.id), email=user.email,
            full_name=user.full_name, avatar_url=user.avatar_url,
            role=user.role, credit=credits, plan="Free",
        ),
        message="Tạo tài khoản thành công." if is_new else "Đăng nhập Google thành công.",
    )