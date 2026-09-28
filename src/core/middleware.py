# src/core/middleware.py
"""
Lớp 2 — FastAPI Middleware: Cổng API
Áp dụng theo thứ tự:
  1. Security headers (mọi response)
  2. Request size limit (trước khi body được đọc)
  3. CORS whitelist (chỉ frontend domain)
  4. Rate limiting per real IP (sau Cloudflare)
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from src.config.config import settings

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Lấy IP thật sau Cloudflare ────────────────────────────────────────────────
def get_real_ip(request: Request) -> str:
    """
    Cloudflare inject CF-Connecting-IP = IP thật của client.
    Fallback về X-Forwarded-For rồi mới về client.host (dev local).
    KHÔNG dùng X-Forwarded-For trực tiếp khi có Cloudflare
    vì header đó có thể bị spoof — CF-Connecting-IP thì không.
    """
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


# ── Key function theo user_id (cho endpoint cần auth) ────────────────────────
def get_user_or_ip_key(request: Request) -> str:
    """
    Key function dùng cho các endpoint đã qua auth — rate-limit theo user_id
    để tránh false positive khi nhiều user share IP (văn phòng, quán cafe, 4G).

    JWT user phải được attach vào request.state.user bởi get_current_user.
    Fallback IP nếu chưa có (request đến trước khi qua auth dependency).

    Cách dùng trong router:
        from src.core.middleware import limiter, get_user_or_ip_key

        @router.get("/path")
        @limiter.limit("30/minute", key_func=get_user_or_ip_key)
        async def endpoint(request: Request, ...):
            ...
    """
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None):
        return f"user:{user.id}"
    return f"ip:{get_real_ip(request)}"


# ── Rate Limiter (singleton) ─────────────────────────────────────────────────
# Default key_func = IP, có thể override per-endpoint qua get_user_or_ip_key
limiter = Limiter(key_func=get_real_ip)


# ── Custom handler: trả ApiResult format chuẩn của project ───────────────────
async def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Override default slowapi handler để trả về JSON đúng format ApiResult,
    giúp frontend parse nhất quán (IsSuccess=false, Code=429, Message=...).
    """
    # exc.detail có dạng "30 per 1 minute" — extract retry-after nếu có
    retry_after = getattr(exc, "retry_after", None)

    response_body = {
        "code": 429,
        "is_success": False,
        "message": f"Quá nhiều request. Giới hạn: {exc.detail}. Vui lòng thử lại sau.",
        "data": None,
        "errors": None,
    }
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)

    return JSONResponse(status_code=429, content=response_body, headers=headers)


def setup_middleware(app: FastAPI) -> None:
    """
    Gọi hàm này 1 lần trong main.py khi khởi tạo app.
    Thứ tự add_middleware quan trọng: FastAPI wrap ngược từ dưới lên.
    """

    # ── 1. Rate limiter state + custom handler ───────────────────────────────
    app.state.limiter = limiter
    # Dùng custom handler thay vì _rate_limit_exceeded_handler mặc định
    # để response đúng format ApiResult cho frontend parse được
    app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)

    # ── 2. CORS — chỉ cho phép domain frontend ───────────────────────────────
    allowed_origins = settings.allowed_origins_list

    if not allowed_origins:
        logger.warning("ALLOWED_ORIGINS chưa được cấu hình — CORS sẽ chặn mọi request từ browser!")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,       
        allow_credentials=True,             
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["X-Request-ID"],
    )

    # ── 3. Request size limit + Security headers ──────────────────────────────
    MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE_MB", "2")) * 1024 * 1024

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # 3a. Chặn body quá lớn trước khi framework đọc
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body vượt quá giới hạn cho phép."},
            )

        response = await call_next(request)

        # 3b. Security headers cho mọi response
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["X-Frame-Options"]         = "DENY"
        response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"]        = "1; mode=block"
        # Bật HSTS chỉ khi production (đã có HTTPS)
        if os.getenv("ENV", "dev") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response