# src/core/database/models/credit.py

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, CheckConstraint, Index, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from .enums import CreditTransactionType

class CreditBatch(Base):
    __tablename__ = 'credit_batches'
    __table_args__ = (
        CheckConstraint('remaining_credits >= 0 AND remaining_credits <= total_credits', name='chk_remaining_non_negative'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    total_credits = Column(Integer, nullable=False)
    remaining_credits = Column(Integer, nullable=False)
    source = Column(String(50), nullable=False)
    payment_order_id = Column(UUID(as_uuid=True), ForeignKey('payment_orders.id'), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="credit_batches")
    order = relationship("PaymentOrder")

class CreditTransaction(Base):
    __tablename__ = 'credit_transactions'
    __table_args__ = (
        CheckConstraint(
            "((transaction_type IN ('CONSUME', 'EXPIRE') AND amount <= 0) OR "
            "(transaction_type IN ('GRANT', 'TOP_UP', 'REFUND') AND amount > 0))",
            name="chk_transaction_sign"
        ),
        Index('idx_unique_job_consume', 'render_job_id', unique=True, postgresql_where=text("transaction_type = 'CONSUME' AND render_job_id IS NOT NULL"))
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey('credit_batches.id', ondelete='RESTRICT'), nullable=True)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(Enum(CreditTransactionType, name="credit_transaction_type"), nullable=False)
    render_job_id = Column(UUID(as_uuid=True), ForeignKey('render_jobs.id'), nullable=True)
    balance_after = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))

    user = relationship("User")
    batch = relationship("CreditBatch")
    render_job = relationship("RenderJob")