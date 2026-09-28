# src/api/user_api.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

from src.api.deps import get_current_user, get_user_plan
from src.core.middleware import limiter
from src.core.database.models import User, CreditBatch, user
from src.core.database.models.enums import SubscriptionStatus
from src.core.database.models.subscription import SubscriptionPlan, UserSubscription
from src.core.database.schemas import (
    ApiResult, CRUDStatusCodeRes,
    UserCreate, UserResponse, UserProfileDTO,
)
from fastapi import Request
from src.core.database.db import get_db
from src.core.rate_limit_policy import RateLimit
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:72])

WELCOME_CREDITS = 15
WELCOME_DAYS    = 30


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimit.REGISTER, key_func=RateLimit.KEY_IP)
async def register_user(
    request: Request,
    user_in: UserCreate,
    db:      AsyncSession = Depends(get_db),
):
    # 1. Validate: local auth bắt buộc phải có password
    if user_in.auth_provider == "local" and not user_in.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Đăng ký tài khoản thường yêu cầu mật khẩu.",
        )

    # 2. Kiểm tra email trùng
    result       = await db.execute(select(User).where(User.email == user_in.email))
    existing     = result.scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký trong hệ thống.",
        )

    # 3. Hash password (chỉ khi local)
    hashed_pwd = get_password_hash(user_in.password) if user_in.auth_provider == "local" else None

    # 4. Tạo user
    new_user = User(
        email=user_in.email,
        password_hash=hashed_pwd,
        auth_provider=user_in.auth_provider,
        provider_id=user_in.provider_id,
    )
    db.add(new_user)
    await db.flush()  # lấy new_user.id

    # 5. Welcome bonus
    db.add(CreditBatch(
        user_id=new_user.id,
        total_credits=WELCOME_CREDITS,
        remaining_credits=WELCOME_CREDITS,
        source="welcome_bonus",
        expires_at=datetime.now(timezone.utc) + timedelta(days=WELCOME_DAYS),
    ))

    # 6. Commit — KHÔNG leak lỗi DB ra ngoài
    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception:
        await db.rollback()
        logger.exception("Lỗi khi tạo tài khoản: email=%s", user_in.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống. Vui lòng thử lại.",  # ✅ không có str(e)
        )

    return new_user

@router.get("/me", response_model=ApiResult[UserProfileDTO])
@limiter.limit(RateLimit.READ_HOT, key_func=RateLimit.KEY_USER)
async def get_my_profile(
    request: Request,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    if current_user.plan != "FREE":
        active_sub = await db.scalar(
            select(UserSubscription).where(
                UserSubscription.user_id == current_user.id,
                UserSubscription.status  == SubscriptionStatus.ACTIVE,
                UserSubscription.current_period_end > func.now(),
            ).limit(1)
        )
        if not active_sub:
            current_user.plan = "FREE"
            await db.commit()
            await db.refresh(current_user)

    # ── Credit ────────────────────────────────────────────────────────────
    credit_result = await db.scalar(
        select(func.coalesce(func.sum(CreditBatch.remaining_credits), 0))
        .where(
            CreditBatch.user_id == current_user.id,
            CreditBatch.remaining_credits > 0,
            or_(
                CreditBatch.expires_at.is_(None),
                CreditBatch.expires_at > func.now(),
            ),
        )
    )

    return ApiResult.success(
        data=UserProfileDTO(
            id=str(current_user.id),
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role,
            avatar_url=current_user.avatar_url,
            plan=current_user.plan,
            credit=int(credit_result or 0),
        ),
        message="Lấy thông tin profile thành công",
    )