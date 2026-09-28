# src/api/subscription_api.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.deps import get_current_user, get_user_plan
from src.core.database.models import User, SubscriptionPlan
from src.core.database.schemas import (
    ApiResult,
    SubscriptionPlanCreate, SubscriptionPlanResponse,
)
from src.core.database.db import get_db
from src.core.middleware import limiter, get_user_or_ip_key
from src.core.rate_limit_policy import RateLimit
from src.core.services.payment_service import PaymentService
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ admin mới được phép — dùng cho các endpoint quản lý plan."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới có quyền thực hiện thao tác này.",
        )
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# CREATE PLAN (admin only)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/create-plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription_plan(
    payload: SubscriptionPlanCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(SubscriptionPlan).where(SubscriptionPlan.plan_code == payload.plan_code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã gói '{payload.plan_code}' đã tồn tại.",
        )

    new_plan = SubscriptionPlan(
        plan_code=payload.plan_code,
        name=payload.name,
        monthly_price=payload.monthly_price,
        monthly_credits=payload.monthly_credits,
        max_video_length_seconds=payload.max_video_length_seconds,
        max_resolution=payload.max_resolution,
    )
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    return new_plan


# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIBE — tạo PaymentOrder, redirect sang PayOS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{plan_id}/subscribe", status_code=status.HTTP_200_OK)
@limiter.limit(RateLimit.WRITE_EXTERNAL, key_func=RateLimit.KEY_USER)
async def subscribe_to_plan(
    request: Request,  # Bắt buộc có cho slowapi decorator — KHÔNG xóa
    plan_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """
    Flow:
      1. Validate plan tồn tại
      2. Tạo PaymentOrder qua PaymentService (luôn tạo order_code mới,
         auto-cancel mọi PENDING order cũ của user)
      3. Trả checkout_url cho client redirect sang PayOS
      4. Subscription chỉ được kích hoạt khi webhook PAID đến

    Rate limit: 10 req/phút/user — đủ cho flow bình thường, chặn spam click
    gây tốn PayOS API quota và rác DB.
    """
    plan = await db.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.deleted_at.is_(None),
        )
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy gói cước này.",
        )

    try:
        order = await payment_service.create_order(
            user_id=current_user.id,
            plan_id=plan_id,
            top_up_credits=None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e),
        )
    except RuntimeError as e:
        logger.exception("Lỗi PayOS khi tạo order: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi kết nối cổng thanh toán. Vui lòng thử lại.",
        )

    return ApiResult.success(
        data={
            "order_id": str(order.id),
            "order_code": order.order_code,
            "checkout_url": order.checkout_url,
            "amount": order.amount,
            "plan_name": plan.name,
        },
        message=(
            "Vui lòng thanh toán để kích hoạt gói. "
            "Gói sẽ được kích hoạt tự động sau khi thanh toán thành công."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LIST PLANS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/list", response_model=ApiResult[list[dict]])
@limiter.limit(RateLimit.READ_NORMAL, key_func=RateLimit.KEY_USER)
async def get_subscription_plans(
    request: Request, 
    current_user: User = Depends(get_current_user),
    current_plan: str = Depends(get_user_plan),
    db: AsyncSession = Depends(get_db),
):
    plans = (await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.deleted_at.is_(None))
        .order_by(SubscriptionPlan.monthly_price.asc())
    )).scalars().all()

    return ApiResult.success(
        data=[
            {
                "id":                       str(p.id),
                "plan_code":                p.plan_code,
                "name":                     p.name,
                "monthly_price":            float(p.monthly_price),
                "monthly_credits":          p.monthly_credits,
                "max_video_length_seconds": p.max_video_length_seconds,
                "max_resolution":           p.max_resolution,
                "is_current_plan":          p.name == current_plan,
            }
            for p in plans
        ],
        message="Lấy danh sách gói cước thành công.",
    )