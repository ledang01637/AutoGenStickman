# src/api/deps.py
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from src.core.database.db import get_db
from src.core.database.models import User
from src.core.database.models import SubscriptionStatus
from src.core.database.models import SubscriptionPlan, UserSubscription
from src.core.security import decode_access_token   # ← dùng hàm tập trung


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Ưu tiên Header, fallback Cookie
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy Token xác thực.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode — mọi lỗi (hết hạn, sai type, sai chữ ký) đều về đây
    try:
        user_id = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị xóa.",
        )

    # Attach user vào request.state để các middleware/decorator downstream truy cập được
    # (đặc biệt: slowapi key_func — get_user_or_ip_key đọc từ đây để rate limit theo user_id)
    request.state.user = user

    return user


async def get_user_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession  = Depends(get_db),
) -> str:
    plan_subq = (
        select(SubscriptionPlan.name)
        .join(UserSubscription, UserSubscription.plan_id == SubscriptionPlan.id)
        .where(
            UserSubscription.user_id == user.id,
            UserSubscription.status  == SubscriptionStatus.ACTIVE,
            UserSubscription.current_period_end > func.now(),
        )
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    result = await db.execute(
        select(func.coalesce(plan_subq, "Free").label("plan"))
    )
    return result.scalar_one()