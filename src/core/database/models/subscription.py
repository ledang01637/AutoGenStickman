# src/core/database/models/subscription.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Enum, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from .enums import SubscriptionStatus

class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plans'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_code = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), unique=True, nullable=False)
    monthly_price = Column(Numeric(10, 2), nullable=False)
    monthly_credits = Column(Integer, nullable=False)
    max_video_length_seconds = Column(Integer, nullable=False)
    max_resolution = Column(String(50), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class UserSubscription(Base):
    __tablename__ = 'user_subscriptions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('subscription_plans.id'), nullable=False)
    payment_subscription_id = Column(String(255), unique=True, nullable=True)
    status = Column(Enum(SubscriptionStatus, name="subscription_status"), nullable=False)
    
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan")