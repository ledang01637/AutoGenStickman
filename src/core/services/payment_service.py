# src/core/services/payment_service.py

import random
import logging
import os
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional

from payos import AsyncPayOS, APIError, WebhookError
from payos.types import CreatePaymentLinkRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError

from src.core.database.models.payment import PaymentOrder, PaymentWebhookEvent
from src.core.database.models.enums import (
    PaymentOrderStatus,
    SubscriptionStatus,
    CreditTransactionType,
)
from src.core.database.models.subscription import SubscriptionPlan, UserSubscription
from src.core.database.models.user import User
from src.core.database.models.credit import CreditBatch, CreditTransaction
from src.config.config import settings

logger = logging.getLogger(__name__)

# ─── Hằng số nghiệp vụ ───────────────────────────────────────────────────────

SUBSCRIPTION_PERIOD_DAYS = 30
CREDIT_PRICE_VND = int(os.getenv("CREDIT_PRICE_VND") or 1000)   # 1000đ / credit khi top-up
PAYOS_DESCRIPTION_MAX = 25  # Giới hạn ký tự description của PayOS

# ─── PayOS async client (singleton) ──────────────────────────────────────────

payos_client = AsyncPayOS(
    client_id=settings.PAYOS_CLIENT_ID,
    api_key=settings.PAYOS_API_KEY,
    checksum_key=settings.PAYOS_CHECKSUM_KEY,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_order_code() -> int:
    """Sinh order_code 9 chữ số từ timestamp + random."""
    ts = int(datetime.now(timezone.utc).timestamp())
    rand = random.randint(10, 99)
    return int(str(ts)[-7:] + str(rand))


# ─── Service ──────────────────────────────────────────────────────────────────

class PaymentService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ════════════════════════════════════════════════════════════════════════
    # CREATE ORDER
    # ════════════════════════════════════════════════════════════════════════

    async def create_order(
        self,
        user_id: UUID,
        plan_id: Optional[UUID],
        top_up_credits: Optional[int],
    ) -> PaymentOrder:
        """
        Tạo PaymentOrder mới + checkout link PayOS.

        QUAN TRỌNG về lifecycle PayOS order_code:
          - PayOS coi mỗi order_code là single-use: sau khi user hủy/timeout
            trên PayOS, order_code đó bị PayOS đánh dấu "đã xử lý"
          - Nếu reuse checkout_url cũ → PayOS hiển thị "Đơn hàng không tồn tại
            hoặc đã được xử lý" → mất khách

        → Mỗi lần user click "Đăng ký" PHẢI tạo order_code MỚI.
        → Đồng thời auto-cancel mọi PENDING order cũ của user/plan này
          để DB không có dangling rows.
        """
        # Validate XOR: chỉ 1 trong 2 (plan_id, top_up_credits) được set
        if bool(plan_id) == bool(top_up_credits):
            raise ValueError("Chỉ được chọn plan_id HOẶC top_up_credits, không được cả hai.")

        # Auto-cancel các PENDING order cũ của user
        # Tránh DB tích tụ rác và tránh user confuse khi check lịch sử
        await self._cancel_stale_pending_orders(user_id=user_id, plan_id=plan_id)

        amount = await self._resolve_amount(plan_id, top_up_credits)
        order_code = _generate_order_code()
        description = await self._resolve_description(
            plan_id=plan_id,
            top_up_credits=top_up_credits,
            order_code=order_code,
        )

        order = PaymentOrder(
            user_id=user_id,
            order_code=order_code,
            amount=amount,
            plan_id=plan_id,
            top_up_credits=top_up_credits,
            status=PaymentOrderStatus.PENDING,
        )
        self.db.add(order)
        await self.db.flush()  # Lấy order.id, chưa commit

        checkout_url = await self._create_payos_link(
            order_code=order_code,
            amount=amount,
            description=description,
        )
        order.checkout_url = checkout_url
        await self.db.commit()
        await self.db.refresh(order)

        logger.info(
            "Tạo PayOS order thành công: order_id=%s order_code=%s amount=%s",
            order.id, order_code, amount,
        )
        return order

    async def _cancel_stale_pending_orders(
        self, user_id: UUID, plan_id: Optional[UUID],
    ) -> None:
        """
        Auto-cancel mọi PENDING order cũ của user.

        Phạm vi cancel:
          - Cùng user_id
          - Status = PENDING
          - Áp dụng cho cả order subscription và top-up

        Lý do cancel rộng (không chỉ cùng plan_id):
          - User click subscribe gói A → cancel
          - User click subscribe gói B → tạo order mới cho B
          - Order A pending còn dangling → user không thể quay lại trả tiền A
            (PayOS đã reject) → cancel luôn cho clean
        """
        await self.db.execute(
            update(PaymentOrder)
            .where(
                PaymentOrder.user_id == user_id,
                PaymentOrder.status == PaymentOrderStatus.PENDING,
            )
            .values(status=PaymentOrderStatus.CANCELLED)
        )
        # Không commit ở đây — để cùng transaction với create_order tiếp theo

    async def _create_payos_link(
        self, order_code: int, amount: int, description: str,
    ) -> str:
        # PayOS tự append: code, status, cancel, orderCode, id vào return_url
        # → frontend dùng orderCode (public identifier) để query trạng thái
        try:
            payment_link = await payos_client.payment_requests.create(
                payment_data=CreatePaymentLinkRequest(
                    order_code=order_code,
                    amount=amount,
                    description=description,
                    cancel_url=settings.PAYOS_CANCEL_URL,
                    return_url=settings.PAYOS_RETURN_URL,
                )
            )
        except APIError as e:
            raise RuntimeError(f"PayOS error [{e.error_code}]: {e.error_desc}") from e
        return payment_link.checkout_url

    # ════════════════════════════════════════════════════════════════════════
    # WEBHOOK
    # ════════════════════════════════════════════════════════════════════════

    async def handle_webhook(self, raw_body: bytes) -> dict:
        """
        Xử lý webhook PayOS với 4 lớp idempotency:
          1. Pre-check PaymentWebhookEvent: dedup nhanh 99% trường hợp
          2. SAVEPOINT + INSERT + IntegrityError catch: chống race khi 2 webhook
             INSERT cùng event_id song song (rất hiếm nhưng có thể xảy ra)
          3. with_for_update() lock PaymentOrder row
          4. order.status check: skip nếu đã ở terminal state

        PayOS có retry policy → cùng 1 event có thể được gửi nhiều lần.
        """
        try:
            webhook_data = await payos_client.webhooks.verify(raw_body)
        except WebhookError as e:
            raise ValueError(f"Invalid webhook signature: {e}") from e

        order_code = webhook_data.order_code
        transaction_id = (
            getattr(webhook_data, "transaction_id", None)
            or getattr(webhook_data, "id", None)
        )
        event_id = (
            f"{order_code}_{transaction_id}" if transaction_id else str(order_code)
        )

        # Phân loại event qua webhook code (PayOS: "00" = success)
        webhook_code = getattr(webhook_data, "code", None)
        is_success = webhook_code == "00"
        webhook_desc = (getattr(webhook_data, "desc", "") or "").lower()
        is_cancelled = ("cancel" in webhook_desc) or ("hủy" in webhook_desc)
        event_type = "PAID" if is_success else ("CANCELLED" if is_cancelled else "FAILED")

        # Lớp 1: Pre-check (optimistic, xử lý 99% case duplicate webhook)
        existing_event = await self.db.scalar(
            select(PaymentWebhookEvent).where(PaymentWebhookEvent.id == event_id)
        )
        if existing_event:
            logger.info("Webhook đã xử lý: event_id=%s", event_id)
            return {"success": True, "message": "Already processed"}

        # Lớp 2: SAVEPOINT để cô lập INSERT — nếu IntegrityError xảy ra do race,
        # chỉ rollback savepoint này, không destroy outer transaction
        try:
            async with self.db.begin_nested():  # SAVEPOINT
                self.db.add(PaymentWebhookEvent(id=event_id, event_type=event_type))
                await self.db.flush()
        except IntegrityError:
            # Webhook khác đã INSERT trước trong tích tắc giữa pre-check và flush
            logger.info("Race detected, webhook đã được xử lý song song: event_id=%s", event_id)
            return {"success": True, "message": "Already processed (race)"}

        # Lớp 3: Lock order row để tránh race với webhook trùng lặp song song
        order = await self.db.scalar(
            select(PaymentOrder)
            .with_for_update()
            .where(PaymentOrder.order_code == order_code)
        )
        if not order:
            logger.warning("Webhook order_code không tồn tại: %s", order_code)
            await self.db.commit()
            return {"success": False, "message": "Order not found"}

        # Lớp 4: skip nếu order đã ở terminal state
        if order.status != PaymentOrderStatus.PENDING:
            logger.info(
                "Order đã ở terminal state: order_code=%s status=%s",
                order_code, order.status,
            )
            await self.db.commit()
            return {"success": True, "message": f"Already {order.status.value}"}

        # Phân nhánh xử lý theo loại event
        if is_success:
            await self._handle_payment_success(order)
            logger.info(
                "Payment thành công: order_code=%s order_id=%s",
                order_code, order.id,
            )
        elif is_cancelled:
            order.status = PaymentOrderStatus.CANCELLED
            logger.info(
                "Payment bị hủy: order_code=%s desc=%s",
                order_code, webhook_desc,
            )
        else:
            order.status = PaymentOrderStatus.FAILED
            logger.warning(
                "Payment thất bại: order_code=%s code=%s desc=%s",
                order_code, webhook_code, webhook_desc,
            )

        await self.db.commit()
        return {"success": True}

    async def _handle_payment_success(self, order: PaymentOrder) -> None:
        order.status = PaymentOrderStatus.PAID
        if order.plan_id:
            await self._activate_subscription(order)
        elif order.top_up_credits:
            await self._grant_credits(
                user_id=order.user_id,
                payment_order_id=order.id,
                credits=order.top_up_credits,
                source="top_up",
                tx_type=CreditTransactionType.TOP_UP,
                description=f"Nạp {order.top_up_credits} credit",
                expires_at=None, 
            )

    # ════════════════════════════════════════════════════════════════════════
    # ACTIVATE SUBSCRIPTION
    # ════════════════════════════════════════════════════════════════════════

    async def _activate_subscription(self, order: PaymentOrder) -> None:
        """
        Kích hoạt subscription dựa trên trạng thái hiện tại của user:
          - Không có ACTIVE sub → tạo mới, period = [now, now+30d]
          - Có ACTIVE sub cùng plan → gia hạn: carry-over credit cũ + cộng 30d
          - Có ACTIVE sub khác plan → cancel sub cũ + expire credit cũ + tạo sub mới
        """
        now = datetime.now(timezone.utc)
        plan = await self.db.get(SubscriptionPlan, order.plan_id)
        if not plan:
            raise RuntimeError(f"Plan không tồn tại: {order.plan_id}")

        # Lock row để tránh race khi 2 webhook vào song song
        existing: Optional[UserSubscription] = await self.db.scalar(
            select(UserSubscription)
            .with_for_update()
            .where(
                UserSubscription.user_id == order.user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.deleted_at.is_(None),
            )
        )

        if existing and existing.plan_id == order.plan_id:

            await self._renew_same_plan(existing, plan, order, now)

        elif existing and existing.plan_id != order.plan_id:

            await self._switch_plan(existing, plan, order, now)

        else:

            await self._create_new_subscription(plan, order, now)

    # async def _renew_same_plan(
    #     self,
    #     existing: UserSubscription,
    #     plan: SubscriptionPlan,
    #     order: PaymentOrder,
    #     now: datetime,
    # ) -> None:
    #     # Carry-over: cộng credit còn lại của batch sub hiện tại vào batch mới
    #     carry_over = await self._expire_active_subscription_batches(
    #         user_id=existing.user_id,
    #         current_period_end=existing.current_period_end,
    #     )

    #     # Cộng 30 ngày từ period_end hiện tại (không phải từ now)
    #     new_period_end = existing.current_period_end + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    #     existing.current_period_end = new_period_end
    #     existing.cancel_at_period_end = False

    #     total_credits = plan.monthly_credits + carry_over
    #     await self._grant_credits(
    #         user_id=existing.user_id,
    #         payment_order_id=order.id,
    #         credits=total_credits,
    #         source="subscription_renew",
    #         tx_type=CreditTransactionType.GRANT,
    #         description=(
    #             f"Gia hạn gói {plan.name}: {plan.monthly_credits} credit"
    #             + (f" + {carry_over} credit chuyển sang" if carry_over else "")
    #         ),
    #         expires_at=new_period_end,
    #     )

    async def _renew_same_plan(self, existing, plan, order, now) -> None:
        carry_over = await self._expire_active_subscription_batches(
            user_id=existing.user_id,
            current_period_end=existing.current_period_end,
        )
        new_period_end = existing.current_period_end + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
        existing.current_period_end = new_period_end
        existing.cancel_at_period_end = False

        # ← Update users.plan cache (giữ nguyên plan, nhưng đảm bảo sync)
        await self.db.execute(
            update(User)
            .where(User.id == existing.user_id)
            .values(plan=plan.plan_code)
        )

        total_credits = plan.monthly_credits + carry_over
        await self._grant_credits(
            user_id=existing.user_id,
            payment_order_id=order.id,
            credits=total_credits,
            source="subscription_renew",
            tx_type=CreditTransactionType.GRANT,
            description=(
                f"Gia hạn gói {plan.name}: {plan.monthly_credits} credit"
                + (f" + {carry_over} credit chuyển sang" if carry_over else "")
            ),
            expires_at=new_period_end,
        )

    # async def _switch_plan(
    #     self,
    #     existing: UserSubscription,
    #     plan: SubscriptionPlan,
    #     order: PaymentOrder,
    #     now: datetime,
    # ) -> None:
    #     existing.status = SubscriptionStatus.CANCELED
    #     existing.cancel_at_period_end = False

    #     carry_over = await self._expire_active_subscription_batches(
    #         user_id=existing.user_id,
    #         current_period_end=existing.current_period_end,
    #     )

    #     await self._create_new_subscription(plan, order, now, carry_over=carry_over)

    async def _switch_plan(self, existing, plan, order, now) -> None:
        existing.status = SubscriptionStatus.CANCELED
        existing.cancel_at_period_end = False

        carry_over = await self._expire_active_subscription_batches(
            user_id=existing.user_id,
            current_period_end=existing.current_period_end,
        )

        # plan cache update xảy ra trong _create_new_subscription
        await self._create_new_subscription(plan, order, now, carry_over=carry_over)


    # async def _create_new_subscription(
    #     self,
    #     plan: SubscriptionPlan,
    #     order: PaymentOrder,
    #     now: datetime,
    #     carry_over: int = 0,  # thêm param, default=0 để không break CASE 3
    # ) -> None:
    #     period_end = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    #     sub = UserSubscription(
    #         user_id=order.user_id,
    #         plan_id=order.plan_id,
    #         status=SubscriptionStatus.ACTIVE,
    #         current_period_start=now,
    #         current_period_end=period_end,
    #         cancel_at_period_end=False,
    #     )
    #     self.db.add(sub)
    #     await self.db.flush()

    #     total_credits = plan.monthly_credits + carry_over
    #     await self._grant_credits(
    #         user_id=order.user_id,
    #         payment_order_id=order.id,
    #         credits=total_credits,
    #         source="subscription_new",
    #         tx_type=CreditTransactionType.GRANT,
    #         description=(
    #             f"Đăng ký gói {plan.name}: {plan.monthly_credits} credit"
    #             + (f" + {carry_over} credit chuyển sang" if carry_over else "")
    #         ),
    #         expires_at=period_end,
    #     )

    async def _create_new_subscription(
        self,
        plan: SubscriptionPlan,
        order: PaymentOrder,
        now: datetime,
        carry_over: int = 0,
    ) -> None:
        period_end = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
        sub = UserSubscription(
            user_id=order.user_id,
            plan_id=order.plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )
        self.db.add(sub)
        await self.db.flush()

        # ← Update users.plan cache
        await self.db.execute(
            update(User)
            .where(User.id == order.user_id)
            .values(plan=plan.plan_code)
        )

        total_credits = plan.monthly_credits + carry_over
        await self._grant_credits(
            user_id=order.user_id,
            payment_order_id=order.id,
            credits=total_credits,
            source="subscription_new",
            tx_type=CreditTransactionType.GRANT,
            description=(
                f"Đăng ký gói {plan.name}: {plan.monthly_credits} credit"
                + (f" + {carry_over} credit chuyển sang" if carry_over else "")
            ),
            expires_at=period_end,
        )

    # ════════════════════════════════════════════════════════════════════════
    # CREDIT MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════

    async def _expire_active_subscription_batches(
        self, user_id: UUID, current_period_end: datetime,
    ) -> int:
        """
        Expire toàn bộ batch subscription còn dư credit của user.
        Trả về tổng credit đã expire (để carry-over nếu cần).

        Phân biệt batch sub vs top-up qua source LIKE 'subscription%'.
        """
        batches = (await self.db.execute(
            select(CreditBatch)
            .with_for_update()
            .where(
                CreditBatch.user_id == user_id,
                CreditBatch.remaining_credits > 0,
                CreditBatch.source.in_(["subscription_new", "subscription_renew", "welcome_bonus"]),
                CreditBatch.expires_at == current_period_end,
            )
        )).scalars().all()

        total_expired = 0
        for batch in batches:
            expired_amount = batch.remaining_credits
            total_expired += expired_amount
            batch.remaining_credits = 0

            balance_after = await self._current_balance(user_id)
            self.db.add(CreditTransaction(
                user_id=user_id,
                batch_id=batch.id,
                amount=-expired_amount,  # EXPIRE phải amount âm theo CHECK constraint
                transaction_type=CreditTransactionType.EXPIRE,
                balance_after=balance_after,
                description=f"Expire {expired_amount} credit khi đổi gói/gia hạn",
            ))

        await self.db.flush()
        return total_expired

    async def _grant_credits(
        self,
        user_id: UUID,
        payment_order_id: UUID,
        credits: int,
        source: str,
        tx_type: CreditTransactionType,
        description: str,
        expires_at: Optional[datetime],
    ) -> CreditBatch:
        """Cấp credit batch mới + ghi transaction với balance_after chính xác."""
        batch = CreditBatch(
            user_id=user_id,
            payment_order_id=payment_order_id,
            total_credits=credits,
            remaining_credits=credits,
            source=source,
            expires_at=expires_at,
        )
        self.db.add(batch)
        await self.db.flush() 

        balance_after = await self._current_balance(user_id)
        self.db.add(CreditTransaction(
            user_id=user_id,
            batch_id=batch.id,
            amount=credits,
            transaction_type=tx_type,
            balance_after=balance_after,
            description=description,
        ))
        return batch

    async def _current_balance(self, user_id: UUID) -> int:
        """Tổng credit còn hiệu lực hiện tại của user."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(func.coalesce(func.sum(CreditBatch.remaining_credits), 0))
            .where(
                CreditBatch.user_id == user_id,
                CreditBatch.remaining_credits > 0,
                # expires_at NULL = không hết hạn (top-up); hoặc còn hạn
                (CreditBatch.expires_at.is_(None)) | (CreditBatch.expires_at > now),
            )
        )
        return int(result.scalar_one())

    # ════════════════════════════════════════════════════════════════════════
    # QUERY
    # ════════════════════════════════════════════════════════════════════════

    async def get_order(self, order_id: UUID, user_id: UUID) -> PaymentOrder:
        order = await self.db.scalar(
            select(PaymentOrder).where(
                PaymentOrder.id == order_id,
                PaymentOrder.user_id == user_id,
            )
        )
        if not order:
            raise ValueError("Order not found")
        return order

    async def get_order_by_code(self, order_code: int, user_id: UUID) -> PaymentOrder:
        """
        Query order theo order_code (public identifier từ PayOS).
        BẮT BUỘC check ownership user_id để tránh user A xem order của user B.
        """
        order = await self.db.scalar(
            select(PaymentOrder).where(
                PaymentOrder.order_code == order_code,
                PaymentOrder.user_id == user_id,
            )
        )
        if not order:
            raise ValueError("Order not found")
        return order

    # ════════════════════════════════════════════════════════════════════════
    # WEBHOOK SETUP
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def confirm_webhook_url(webhook_url: str) -> dict:
        try:
            return await payos_client.webhooks.confirm(webhook_url)
        except APIError as e:
            raise RuntimeError(
                f"Confirm webhook thất bại [{e.error_code}]: {e.error_desc}"
            ) from e

    # ════════════════════════════════════════════════════════════════════════
    # AMOUNT/DESCRIPTION RESOLVERS
    # ════════════════════════════════════════════════════════════════════════

    async def _resolve_amount(
        self, plan_id: Optional[UUID], top_up_credits: Optional[int],
    ) -> int:
        if top_up_credits:
            
            return top_up_credits * CREDIT_PRICE_VND
        plan = await self.db.get(SubscriptionPlan, plan_id)
        if not plan:
            raise ValueError("Plan not found")
        return int(plan.monthly_price)

    async def _resolve_description(
        self,
        plan_id: Optional[UUID],
        top_up_credits: Optional[int],
        order_code: int,
    ) -> str:
        """
        Build description chuyển khoản với order_code làm identifier unique.

        PayOS giới hạn 25 ký tự — đây cũng là nội dung user thấy khi quét QR
        và nội dung xuất hiện trên sao kê ngân hàng.

        Format: "TT {order_code}" — đủ ngắn để bank không cắt, đủ unique để
        đối soát. order_code 9 chữ số → tổng 12 ký tự, dư 13 ký tự buffer.

        KHÔNG nhúng plan name vì:
          - Trùng lặp khi user mua cùng plan nhiều lần
          - Plan name dài có thể vượt giới hạn 25 ký tự
          - Khi đối soát, chỉ cần order_code là tra ngược được mọi thông tin
        """
        # Validate format không vượt giới hạn (defensive check)
        description = f"TT {order_code}"
        if len(description) > PAYOS_DESCRIPTION_MAX:
            # Trường hợp order_code đột biến quá dài → fallback
            description = str(order_code)[:PAYOS_DESCRIPTION_MAX]
        return description