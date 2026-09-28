# src/main.py
"""
Điểm khởi động app — gắn tất cả các lớp bảo mật vào đúng thứ tự.

Luồng request POST /api/videos/generate:
  [Internet]
    → Lớp 1: Cloudflare (DDoS, IP hide, WAF, geo-block)
    → Lớp 2: security_middleware (size limit, security headers)
    → Lớp 2: CORSMiddleware (chặn origin lạ)
    → Lớp 2: @limiter.limit("3/day;1/minute") per real IP
    → Lớp 3: get_current_user (JWT decode + verify type)
    → Lớp 5: check_and_increment_global_cap() (cầu dao chi phí)
    → Lớp 4: SELECT FOR UPDATE → trừ credit → tạo job
    → [Worker xử lý AI]
"""
import os

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse

from src.core.middleware import setup_middleware
from src.core.security.global_cap import get_cap_status
from src.api.deps import get_current_user
from src.core.database.models import User
from src.config.config import settings

# Import routers
from src.api.auth_api         import router as auth_router
from src.api.user_api         import router as user_router
from src.api.video_api        import router as video_router
from src.api.subscription_api import router as subscription_router
from src.api.payment_api      import router as payment_router

app = FastAPI(
    title="AI Video SaaS",
    docs_url=None if settings.ENV == "production" else "/docs",
    redoc_url=None if settings.ENV == "production" else "/redoc",
)

# ── Lớp 2: Middleware (gọi trước khi mount router) ───────────────────────────
setup_middleware(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router,         prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(user_router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(video_router,        prefix="/api/v1/videos",        tags=["Videos"])
app.include_router(payment_router,      prefix="/api/v1/payments",      tags=["Payments"])
app.include_router(subscription_router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])

# ── Health check (không cần auth — Cloudflare / load balancer dùng) ──────────
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

# ── Admin: trạng thái cầu dao (cần auth + admin role) ────────────────────────
@app.get("/api/v1/admin/cap-status", include_in_schema=False)
async def cap_status(
    _: User = Depends(get_current_user),  
    # TODO: thêm Depends(require_admin) khi có role admin
):
    return JSONResponse(content=await get_cap_status())