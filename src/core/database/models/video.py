# src/core/database/models/video.py
import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base
from .enums import RenderJobStatus


class VideoProject(Base):
    __tablename__ = 'video_projects'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    project_metadata = Column(JSONB, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="projects")
    jobs = relationship("RenderJob", back_populates="project", cascade="all, delete-orphan")


class RenderJob(Base):
    __tablename__ = 'render_jobs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('video_projects.id', ondelete='CASCADE'), nullable=False)
    status = Column(Enum(RenderJobStatus, name="render_job_status"), default=RenderJobStatus.PENDING, nullable=False)
    render_config = Column(JSONB, default=dict, nullable=False)

    scenes_count     = Column(Integer, default=0,  nullable=False)
    duration_seconds = Column(Integer, default=0,  nullable=False)
    cost_credits     = Column(Integer, nullable=False)

    idempotency_key = Column(String(255), unique=True, nullable=True)
    worker_id       = Column(String(100), nullable=True)
    locked_at       = Column(DateTime(timezone=True), nullable=True)

    # Retry control — BẮT BUỘC cho fetch_and_lock_job + finalize_job_atomic
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=1, nullable=False)

    started_at    = Column(DateTime(timezone=True), nullable=True)
    completed_at  = Column(DateTime(timezone=True), nullable=True)
    output_url    = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    priority   = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("VideoProject", back_populates="jobs")