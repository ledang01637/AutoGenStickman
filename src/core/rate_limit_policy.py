# src/core/rate_limit_policy.py
"""
Rate limit policy phân tier cho toàn project.

Triết lý: limit phải phản ánh đúng cost (DB/CPU/external API/$$) và risk
(brute-force, abuse, DDoS) của từng endpoint, KHÔNG áp 1 config cho mọi nơi.

Cách dùng:
    from src.core.middleware import limiter
    from src.core.rate_limit_policy import RateLimit

    @router.get("/me")
    @limiter.limit(RateLimit.READ_HOT, key_func=RateLimit.KEY_USER)
    async def get_me(request: Request, ...):
        ...
"""
from src.core.middleware import get_user_or_ip_key, get_real_ip


class RateLimit:
    # ── Key functions ────────────────────────────────────────────────────────
    KEY_USER = get_user_or_ip_key  # Endpoint authenticated → theo user_id
    KEY_IP = get_real_ip          # Endpoint public → theo IP

    # ── TIER 1: READ — query nhanh, idempotent, ít tốn tài nguyên ───────────
    # VD: GET /users/me, GET /plans/list, GET /credits/balance
    READ_HOT = "120/minute"   # Endpoint gọi liên tục theo page navigation
    READ_NORMAL = "60/minute"  # Endpoint thông thường

    # ── TIER 2: POLLING — gọi đều đặn theo interval ngắn ────────────────────
    # VD: GET /payments/by-code, GET /jobs/{id}/status
    POLLING = "30/minute"

    # ── TIER 3: WRITE NORMAL — DB write nhẹ, không tốn external API ─────────
    # VD: PATCH /users/profile, POST /jobs/cancel
    WRITE_NORMAL = "30/minute"

    # ── TIER 4: WRITE EXTERNAL — tốn quota external API (PayOS, email…) ─────
    # VD: POST /subscriptions/{id}/subscribe, POST /payments
    WRITE_EXTERNAL = "10/minute"

    # ── TIER 5: EXPENSIVE — tốn $$ AI inference, render heavy ───────────────
    # VD: POST /videos/generate, POST /scripts/generate
    # Format: daily cap để chặn abuse + minute cap để chặn burst
    EXPENSIVE = "3/day;1/minute"

    # ── TIER 6: AUTH PUBLIC — endpoint chưa auth, target brute-force ────────
    # Theo IP vì chưa có user_id. Strict để chặn credential stuffing.
    LOGIN = "5/minute"
    REGISTER = "3/minute"
    PASSWORD_RESET = "3/hour"  # Email/SMS tốn tiền

    # ── TIER 7: AUTH REFRESH — endpoint authenticated nhưng nhạy cảm ────────
    REFRESH_TOKEN = "20/minute"

    # ── KHÔNG limit ──────────────────────────────────────────────────────────
    # Webhook bên thứ 3 (PayOS, Stripe) — retry là behavior hợp lệ
    # Health check — load balancer ping liên tục