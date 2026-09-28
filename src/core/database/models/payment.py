# src/core/database/models/payment.py

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Enum, CheckConstraint, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from .enums import PaymentOrderStatus

class PaymentWebhookEvent(Base):
    __tablename__ = 'payment_webhook_events'
    id = Column(String(255), primary_key=True)
    event_type = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))

class PaymentOrder(Base):
    __tablename__ = 'payment_orders'
    __table_args__ = (
        CheckConstraint(
            "(plan_id IS NOT NULL AND top_up_credits IS NULL) OR (plan_id IS NULL AND top_up_credits IS NOT NULL)",
            name="chk_order_type_xor"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    order_code = Column(BigInteger, unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    
    plan_id = Column(UUID(as_uuid=True), ForeignKey('subscription_plans.id'), nullable=True)
    top_up_credits = Column(Integer, nullable=True)
    
    status = Column(Enum(PaymentOrderStatus, name="payment_order_status"), default=PaymentOrderStatus.PENDING)
    checkout_url = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="orders")
    plan = relationship("SubscriptionPlan")