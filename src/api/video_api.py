# src/api/video_api.py
"""
Thứ tự bảo vệ cho POST /generate:
  Lớp 1 — Cloudflare (ngoài code)
  Lớp 2 — Rate limit: @limiter.limit("3/day;1/minute") per IP
  Lớp 3 — JWT auth: Depends(get_current_user)
  Lớp 5 — Global cap: check_and_increment_global_cap()
  Lớp 4 — Credit: SELECT FOR UPDATE → trừ trước → tạo job
           (Refund: worker tự refund nếu job FAILED)
"""
import asyncio
import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.config.plan_features import PlanFeatureValidator
from src.core.database.db import AsyncSessionLocal, get_db
from src.core.rate_limit_policy import RateLimit
from src.core.security.global_cap import check_and_increment_global_cap
from src.core.middleware import limiter
from ..core.scripts.pace import calc_scene_params
from src.core.database.schemas import (
    ApiResult, CRUDStatusCodeRes,
    VideoProjectCreate, VideoProjectResponse,
)
from src.core.database.models import (
    User, VideoProject, RenderJob, RenderJobStatus, CreditBatch,
    CreditTransaction, CreditTransactionType
)
from src.api.deps import get_current_user, get_user_plan
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

SSE_MAX_SECONDS  = 600  
SSE_POLL_SECONDS = 1.5

PLAN_PRIORITY: dict[str, int] = {
    "Ultra": 4,
    "Pro":   3,
    "Trial": 3,
    "Basic": 2,
}
DEFAULT_PRIORITY = 1


# ==========================================
# 1. HÀM TÍNH TOÁN THUẦN TÚY
# ==========================================

def calculate_video_cost(minutes: float, total_scenes: int, use_best_model: bool) -> int:
    # Công thức: mỗi cảnh tốn 1 credit (1 lần gọi image model + 1 lần TTS),
    # cộng 2 credit cho mỗi phút thời lượng (chi phí sinh kịch bản + render).
    # Sàn 3 credit để video ngắn nhất vẫn bù được overhead cố định.
    # Tự điều chỉnh theo giá nhà cung cấp và biên lợi nhuận bạn muốn.
    return max(total_scenes + math.ceil(minutes) * 2, 3)


def calculate_video_scenes(minutes: float, pace: str = "balanced") -> int:
    return calc_scene_params(minutes, pace).num_scenes


def map_progress_pro(
    job_status:    str,
    scenes:        list,
    total_scenes:  int,
    error_message: str | None,
) -> tuple[int, str, bool, bool]:
    if job_status == RenderJobStatus.FAILED.value:
        return 0, f"Lỗi: {error_message or 'Không xác định'}", False, True
    if job_status == RenderJobStatus.COMPLETED.value:
        return 100, "Hoàn tất! Video của bạn đã sẵn sàng.", True, False
    if total_scenes == 0:
        progress = 5 if job_status == RenderJobStatus.PROCESSING.value else 2
        return progress, "Đang khởi tạo kịch bản AI...", False, False

    img_done   = sum(1 for s in scenes if s.get("status", {}).get("image")  == "completed")
    audio_done = sum(1 for s in scenes if s.get("status", {}).get("audio") == "completed")
    combined   = (img_done / total_scenes + audio_done / total_scenes) / 2
    progress   = 10 + int(combined * 70)

    if img_done < total_scenes and audio_done < total_scenes:
        msg = f"Đang xử lý song song: ảnh {img_done}/{total_scenes} · audio {audio_done}/{total_scenes}..."
    elif img_done < total_scenes:
        msg = f"Đang tạo ảnh AI ({img_done}/{total_scenes} cảnh)..."
    elif audio_done < total_scenes:
        msg = f"Đang lồng tiếng ({audio_done}/{total_scenes} cảnh)..."
    else:
        return 85, "Đang ghép và xuất video MP4...", False, False

    return progress, msg, False, False


# ==========================================
# 2. SSE GENERATOR
# ==========================================

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def generate_progress_events(job_id: str, user_id: str):
    elapsed = 0.0
    while elapsed < SSE_MAX_SECONDS:
        async with AsyncSessionLocal() as session:
            job: RenderJob | None = (await session.execute(
                select(RenderJob)
                .where(RenderJob.id == job_id)
                .options(selectinload(RenderJob.project))
            )).scalar_one_or_none()

        if job is None:
            yield _sse({"progress": 0, "message": "Không tìm thấy Job.", "is_done": False, "is_error": True})
            return

        if str(job.project.user_id) != user_id:
            yield _sse({"progress": 0, "message": "Không có quyền truy cập.", "is_done": False, "is_error": True})
            return

        config       = json.loads(job.render_config) if isinstance(job.render_config, str) else (job.render_config or {})
        scenes       = config.get("scenes", [])
        total_scenes = len(scenes)
        job_status   = job.status.value if isinstance(job.status, RenderJobStatus) else str(job.status)

        progress, message, is_done, is_error = map_progress_pro(
            job_status=job_status, scenes=scenes,
            total_scenes=total_scenes, error_message=job.error_message,
        )

        payload = {"progress": progress, "message": message, "is_done": is_done, "is_error": is_error}
        if is_done and job.output_url:
            payload["video_url"] = job.output_url

        logger.debug("SSE | job=%s | status=%s | progress=%d%%", job_id, job_status, progress)
        yield _sse(payload)

        if is_done or is_error:
            return

        await asyncio.sleep(SSE_POLL_SECONDS)
        elapsed += SSE_POLL_SECONDS

    yield _sse({
        "progress": -1,
        "message":  "Timeout theo dõi. Vui lòng tải lại trang.",
        "is_done":  False,
        "is_error": True,
    })


# ==========================================
# 3. ENDPOINTS
# ==========================================

# @limiter.limit(RateLimit.EXPENSIVE, key_func=RateLimit.KEY_USER)       
@router.post("/generate", response_model=ApiResult[dict], status_code=status.HTTP_201_CREATED)
async def create_video_project(
    request:      Request,
    project_in:   VideoProjectCreate,
    current_user: User         = Depends(get_current_user),
    plan:         str          = Depends(get_user_plan),
    db:           AsyncSession = Depends(get_db),
):
    validator      = PlanFeatureValidator(plan)
    project_in     = validator.apply_defaults(project_in)
    effective_pace = project_in.pace or "balanced"
    total_scenes   = project_in.total_scenes or calculate_video_scenes(project_in.minutes, effective_pace)
    cost           = calculate_video_cost(project_in.minutes, total_scenes, project_in.use_best_model)

    balance: int = (await db.execute(
        select(func.coalesce(func.sum(CreditBatch.remaining_credits), 0))
        .where(
            CreditBatch.user_id == current_user.id,
            CreditBatch.remaining_credits > 0,
            or_(
                CreditBatch.expires_at.is_(None),
                CreditBatch.expires_at > func.now(),
            ),
        )
    )).scalar_one()

    if balance < cost:
        return ApiResult.error(
            message=f"Bạn cần thêm {cost - balance} Credits để bắt đầu render.",
            code=CRUDStatusCodeRes.PAYMENT_REQUIRED,
        )

    batches = (await db.execute(
        select(CreditBatch)
        .with_for_update()
        .where(
            CreditBatch.user_id == current_user.id,
            CreditBatch.remaining_credits > 0,
            or_(
                CreditBatch.expires_at.is_(None),
                CreditBatch.expires_at > func.now(),
            ),
        )
        .order_by(CreditBatch.expires_at.asc())
    )).scalars().all()

    deducted_amounts: list[tuple[CreditBatch, int]] = []
    remaining = cost
    for batch in batches:
        if remaining <= 0:
            break
        deduct                   = min(batch.remaining_credits, remaining)
        batch.remaining_credits -= deduct
        remaining               -= deduct
        deducted_amounts.append((batch, deduct))

    if remaining > 0:
        await db.rollback()
        return ApiResult.error(
            message="Số dư Credit thay đổi. Vui lòng thử lại.",
            code=CRUDStatusCodeRes.PAYMENT_REQUIRED,
        )

    metadata = {
        "topic":           project_in.topic,
        "minutes":         project_in.minutes,
        "total_scenes":    total_scenes,
        "tone":            project_in.tone,
        "main_character":  project_in.main_character,
        "pace":            project_in.pace,
        "story_structure": project_in.story_structure,
        "claude_model":    validator.model,
        "user_plan":       plan,
        "use_best_model":  project_in.use_best_model,
        "use_color_image": project_in.use_color_image,
        "voice_code":      project_in.voice_code,
        "is_speed":        project_in.is_speed,
        "render_type":     project_in.render_type,
    }

    new_project = VideoProject(
        user_id=current_user.id,
        title=project_in.title,
        project_metadata=metadata,
    )
    db.add(new_project)
    await db.flush()

    new_job = RenderJob(
        project_id=new_project.id,
        status=RenderJobStatus.PENDING,
        render_config=metadata,
        duration_seconds=int(project_in.minutes * 60),
        cost_credits=cost,
        scenes_count=total_scenes,
        priority=PLAN_PRIORITY.get(plan, DEFAULT_PRIORITY),
    )
    db.add(new_job)
    await db.flush()  

    balance_tracker = int(balance)
    for batch, deducted in deducted_amounts:
        balance_tracker -= deducted
        db.add(CreditTransaction(
            user_id=current_user.id,
            batch_id=batch.id,
            amount=-deducted,
            transaction_type=CreditTransactionType.CONSUME,
            render_job_id=new_job.id,
            balance_after=balance_tracker,
            description="Job render consume",
        ))

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Lỗi tạo video project: user=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi tạo Job. Vui lòng thử lại.",
        )

    return ApiResult.success(
        data={
            "project_id":   str(new_project.id),
            "job_id":       str(new_job.id),
            "cost_credits": cost,
            "status":       RenderJobStatus.PENDING.value,
        },
        message="Đã đưa video vào hàng đợi xử lý AI.",
    )

@router.get("/my-videos", response_model=ApiResult[list[VideoProjectResponse]])
async def get_my_video_projects(
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    projects = (await db.execute(
        select(VideoProject)
        .options(selectinload(VideoProject.jobs))
        .where(
            VideoProject.user_id == current_user.id,
            VideoProject.deleted_at.is_(None),
        )
        .order_by(VideoProject.created_at.desc())
    )).scalars().all()

    return ApiResult.success(
        data=[VideoProjectResponse.from_orm_with_job(p) for p in projects],
        message="Lấy danh sách video thành công.",
    )


@router.get("/estimate-cost", response_model=ApiResult[dict])
async def estimate_video_cost(
    minutes:      float         = Query(..., gt=0, le=5),
    pace:         str           = Query("balanced"),
    use_best_model: bool         = Query(False),
    total_scenes: Optional[int] = Query(None, gt=0),
    current_user: User          = Depends(get_current_user),
    plan:         str           = Depends(get_user_plan),
    db:           AsyncSession  = Depends(get_db),
):
    validator      = PlanFeatureValidator(plan)
    plan_config    = validator.config
    effective_pace = pace if pace in plan_config.allowed_paces else plan_config.default_pace

    if total_scenes is None:
        total_scenes = calculate_video_scenes(minutes, effective_pace)

    cost    = calculate_video_cost(minutes, total_scenes, use_best_model)
    balance = (await db.execute(
        select(func.coalesce(func.sum(CreditBatch.remaining_credits), 0))
        .where(
            CreditBatch.user_id == current_user.id,
            CreditBatch.remaining_credits > 0,
            or_(
                CreditBatch.expires_at.is_(None),
                CreditBatch.expires_at > func.now(),
            ),
        )
    )).scalar_one()

    return ApiResult.success(
        data={
            "cost_credits":    cost,
            "total_scenes":    total_scenes,
            "minutes":         minutes,
            "effective_pace":  effective_pace,
            "pace_locked":     pace not in plan_config.allowed_paces,
            "current_balance": balance,
            "can_afford":      balance >= cost,
            "missing_credits": max(0, cost - balance),
        },
        message="Ước tính cost",
    )


@router.get("/progress/{job_id}")
async def get_video_progress(
    job_id:       str,
    current_user: User = Depends(get_current_user),    # Lớp 3
):
    return StreamingResponse(
        generate_progress_events(job_id, user_id=str(current_user.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )