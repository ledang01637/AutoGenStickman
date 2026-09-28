# src/core/database/models/user.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, func, text, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    
    # Cho phép Null để dùng Google Login
    password_hash = Column(String(255), nullable=True) 
    
    # 2 Cột mới phục vụ OAuth
    auth_provider = Column(String(50), default='local') 
    provider_id = Column(String(255), nullable=True)     
    
    payment_customer_id = Column(String(255), nullable=True)
    role = Column(String(20), default='USER')
    
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    refresh_token = Column(String(255), nullable=True)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    full_name = Column(String(255), nullable=True)
    avatar_url = Column(Text, nullable=True)

    registration_ip = Column(String(45), nullable=True)  
    plan = Column(String(50), default='FREE', nullable=False)  

    # Dùng String name để tránh Circular Import
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("PaymentOrder", back_populates="user", cascade="all, delete-orphan")
    credit_batches = relationship("CreditBatch", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("VideoProject", back_populates="user", cascade="all, delete-orphan")