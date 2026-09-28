# src/api/payment_api.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from src.core.database.db import get_db
from src.core.rate_limit_policy import RateLimit
from fastapi import Request
from src.core.services.payment_service import PaymentService
from src.core.database.schemas import (
    ApiResult,
    PaymentOrderCreate,
    PaymentOrderResponse,
)
from src.core.middleware import limiter, get_user_or_ip_key
from src.api.deps import get_current_user
from src.core.database.models.user import User
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)



# Topup
class TopUpRequest(BaseModel):
    """Request body cho endpoint top-up."""
    credits: int = Field(
        ...,
        ge=20,      # khớp FE MIN_CREDITS = 20
        le=4_000,   # khớp FE MAX_CREDITS = 4_000
        description="Số credit muốn nạp (1 credit = 2.500đ)",
    )
 
 
@router.post("/top-up", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute", key_func=get_user_or_ip_key)
async def top_up_credits(
    request: Request,
    body: TopUpRequest,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """
    Tạo order top-up credit. Trả về checkout_url của PayOS để FE redirect.
 
    Flow giống subscribe nhưng dùng top_up_credits thay vì plan_id.
    Webhook PayOS sẽ kích hoạt _handle_payment_success → _grant_credits với
    source='top_up', expires_at=None (credit top-up không hết hạn).
    """
    try:
        order = await service.create_order(
            user_id=current_user.id,
            plan_id=None,
            top_up_credits=body.credits,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        logger.exception("Lỗi PayOS khi tạo top-up order: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi kết nối cổng thanh toán. Vui lòng thử lại.",
        )
 
    return ApiResult.success(
        data={
            "order_id":     str(order.id),
            "order_code":   order.order_code,
            "checkout_url": order.checkout_url,
            "amount":       order.amount,
            "credits":      body.credits,
        },
        message=(
            f"Vui lòng thanh toán {order.amount:,}đ để nhận {body.credits} credit. "
            "Credit sẽ được cộng tự động sau khi thanh toán thành công."
        ),
    )

# ── Tạo đơn thanh toán ────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ApiResult[PaymentOrderResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RateLimit.WRITE_EXTERNAL, key_func=RateLimit.KEY_USER)
async def create_payment_order(
    request: Request, 
    body: PaymentOrderCreate,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    try:
        order = await service.create_order(
            user_id=current_user.id,
            plan_id=body.plan_id,
            top_up_credits=body.top_up_credits,
        )
        return ApiResult.created(
            data=PaymentOrderResponse.model_validate(order),
            message="Tạo đơn thanh toán thành công",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.exception("Lỗi kết nối PayOS: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi kết nối cổng thanh toán. Vui lòng thử lại.",
        )


# ── Polling theo order_id (internal — admin/debug) ───────────────────────────

@router.get("/{order_id}", response_model=ApiResult[PaymentOrderResponse])
@limiter.limit(RateLimit.WRITE_EXTERNAL, key_func=RateLimit.KEY_USER)
async def get_payment_status(
    request: Request, 
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    try:
        order = await service.get_order(order_id, current_user.id)
        return ApiResult.success(
            data=PaymentOrderResponse.model_validate(order),
            message="Lấy trạng thái đơn hàng thành công",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng.",
        )


# ── Polling theo order_code (public — frontend dùng sau khi PayOS redirect) ──

@router.get("/by-code/{order_code}", response_model=ApiResult[PaymentOrderResponse])
@limiter.limit("30/minute", key_func=get_user_or_ip_key)
async def get_payment_status_by_code(
    request: Request,  # Bắt buộc có để slowapi decorator hoạt động — KHÔNG xóa
    order_code: int,
    current_user: User = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """
    Frontend gọi endpoint này sau khi PayOS redirect về /payment/result
    với query string ?orderCode=xxx.

    Rate limit: 30 req/phút/user (override default IP-based để không block oan
    user share IP). Polling FE thực tế: 24 req/30s = 48 req/phút khi retry,
    nhưng polling chỉ chạy 30s rồi timeout → trong 1 phút tối đa ~30 req.

    Bảo mật:
      - JWT bắt buộc qua get_current_user
      - Ownership check ngay trong query (user_id == current_user.id)
      - order_code là public identifier (đã hiển thị trên QR PayOS),
        nhưng vẫn cần ownership check + rate limit để chặn enumeration.
    """
    try:
        order = await service.get_order_by_code(order_code, current_user.id)
        return ApiResult.success(
            data=PaymentOrderResponse.model_validate(order),
            message="Lấy trạng thái đơn hàng thành công",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng.",
        )


# ── Webhook PayOS ─────────────────────────────────────────────────────────────

@router.post("/webhook/payos", include_in_schema=False)
async def payos_webhook(
    request: Request,
    service: PaymentService = Depends(get_payment_service),
):
    """
    KHÔNG dùng response_model=ApiResult vì PayOS chỉ cần nhận 200 OK.
    Phải đọc raw bytes để SDK verify signature đúng.
    KHÔNG rate-limit endpoint này — PayOS retry là behavior hợp lệ.
    """
    try:
        raw_body = await request.body()
        result = await service.handle_webhook(raw_body)
        return result
    except ValueError as e:
        logger.warning("Webhook signature không hợp lệ: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    except Exception:
        logger.exception("Lỗi xử lý webhook PayOS")
        # Trả 200 để PayOS không retry liên tục
        return {"success": False, "message": "Internal error"}