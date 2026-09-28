# src/core/database/schemas.py
from enum import IntEnum
import uuid

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_serializer, field_validator
from typing import Generic, Optional, Dict, Any, List, TypeVar
from datetime import datetime, timezone
from uuid import UUID

from .models.enums import RenderJobStatus, SubscriptionStatus, PaymentOrderStatus, CreditTransactionType

# ==========================================
# 2. USER SCHEMAS
# ==========================================
from pydantic import BaseModel, Field, EmailStr, ConfigDict, model_validator

class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8, description="Mật khẩu (có thể null nếu dùng Google Login)")
    auth_provider: str = Field(default="local", description="'local', 'google', 'facebook'")
    provider_id: Optional[str] = Field(None, description="ID do Google/Facebook cấp")
    full_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=255)

    @model_validator(mode='after')
    def check_password_or_provider(self):
        # 1. Nếu login thường (local) mà không truyền password -> Chặn!
        if self.auth_provider == 'local' and not self.password:
            raise ValueError('Đăng ký tài khoản thường bắt buộc phải có mật khẩu (password)')
        
        # 2. Nếu login bằng Google mà không có ID của Google -> Chặn!
        if self.auth_provider != 'local' and not self.provider_id:
            raise ValueError(f'Đăng nhập qua {self.auth_provider} bắt buộc phải có provider_id')
        
        return self

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    payment_customer_id: Optional[str] = None 
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 3. PAYMENT ORDER SCHEMAS (MỚI - Cho PayOS)
# ==========================================
class PaymentOrderCreate(BaseModel):
    # Khách chỉ được truyền 1 trong 2: hoặc id gói, hoặc số điểm nạp lẻ
    plan_id: Optional[UUID] = None
    top_up_credits: Optional[int] = Field(None, gt=0, description="Số điểm muốn nạp thêm")

class PaymentOrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    order_code: int # Chữ ký sinh mã QR của PayOS
    amount: int
    plan_id: Optional[UUID] = None
    top_up_credits: Optional[int] = None
    status: PaymentOrderStatus
    checkout_url: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 4. VIDEO PROJECT SCHEMAS
# ==========================================
class VideoProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    topic: str = Field(..., min_length=1, max_length=255)
    minutes: float = Field(..., gt=0, description="Độ dài video mong muốn tính bằng phút")
    total_scenes: Optional[int] = Field(None, gt=0, description="Số lượng cảnh video mong muốn")
    tone: str = Field("genz_meme", description="Tone của video, ví dụ: genz_meme, cinematic, storytelling...")
    main_character: str = Field("a quirky cat", description="Nhân vật chính trong video")
    pace: str = Field("balanced", description="Nhịp điệu video, ví dụ: fast_cut, dynamic, balanced, storytelling, cinematic")
    story_structure: str = Field("hook_twist", description="Cấu trúc câu chuyện, ví dụ: iceberg, hero_journey, three_act...")
    use_best_model: bool = Field(False, description="Có sử dụng model tốt nhất (claude-opus-4-7) hay không")
    use_color_image: bool = Field(False, description="Có sử dụng hình ảnh màu hay không")
    voice_code: str = Field("hn_female_ngochuyen_full_48k-fhg", description="Mã giọng nói cho phần voiceover, ví dụ: hn_female_ngochuyen_full_48k-fhg")
    is_speed: bool = Field(False, description="Có ưu tiên tốc độ render hơn chất lượng hay không (only free)")
    render_type: str = Field("static", description="Loại render, ví dụ: static, fast (chỉ free), animation")

    @field_validator("pace",mode="before")
    @classmethod
    def validate_pace(cls, v):
        from ...config.plan_features import AllowedPace
        values = {e.value for e in AllowedPace}
        if v not in values:
            raise ValueError(f"pace phải là một trong: {values}")
        return v

    @field_validator("tone",mode="before")
    @classmethod
    def validate_tone(cls, v):
        from ...config.plan_features import AllowedTone
        values = {e.value for e in AllowedTone}
        if v not in values:
            raise ValueError(f"tone phải là một trong: {values}")
        return v

    @field_validator("story_structure",mode="before")
    @classmethod
    def validate_story_structure(cls, v):
        if v is None:
            return v
        from ...config.plan_features import AllowedStoryStructure
        values = {e.value for e in AllowedStoryStructure}
        if v not in values:
            raise ValueError(f"story_structure phải là một trong: {values}")
        return v

    @field_validator("topic", mode="before")
    @classmethod
    def sanitize_topic(cls, v):
        if not v:
            return v
        import re
        _PATTERNS = [
            r"ignore\s+(all\s+)?previous",
            r"system\s*:",
            r"you\s+are\s+now\s+a",
            r"forget\s+(everything|all)",
            r"new\s+instruction",
            r"</?(system|instruction|prompt)>",
        ]
        lower = str(v).lower()
        for pattern in _PATTERNS:
            if re.search(pattern, lower):
                raise ValueError("Chủ đề video chứa nội dung không hợp lệ.")
        return v.strip()

class VideoProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    project_metadata: Optional[Dict[str, Any]] = None

# ==========================================
# 5. RENDER JOB SCHEMAS
# ==========================================

class RenderJobResponse(BaseModel):
    """Schema trả về trạng thái và kết quả của một render job."""

    id: uuid.UUID
    status: RenderJobStatus          
    output_url: Optional[str] = None
    cost_credits: int
    duration_seconds: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0        
    max_retries: int = 1

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info: Any) -> str:
        """Serialize created_at thành YYYY-MM-DD string."""
        return dt.strftime("%Y-%m-%d")


# ==========================================
# 4. VIDEO PROJECT SCHEMAS (class Response)
# ==========================================

class VideoProjectResponse(BaseModel):
    """Schema trả về thông tin project kèm job mới nhất."""

    id: uuid.UUID
    title: str
    created_at: datetime
    latest_job: Optional[RenderJobResponse] = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info: Any) -> str:
        """
        Serialize created_at thành ISO 8601 UTC string.
        
        Thay thế: json_encoders = {datetime: lambda v: v.astimezone(timezone.utc).isoformat()}
        """
        return dt.astimezone(timezone.utc).isoformat()

    @classmethod
    def from_orm_with_job(cls, project: Any) -> "VideoProjectResponse":
        """
        Construct response từ ORM project object.

        Warning:
            Sort `project.jobs` in-memory — chỉ an toàn khi số jobs nhỏ.
            TODO: Chuyển logic lấy latest_job về tầng Repository với
            ORDER BY created_at DESC LIMIT 1 để tránh load toàn bộ list.
        """
        latest = (
            sorted(project.jobs, key=lambda j: j.created_at, reverse=True)[0]
            if project.jobs
            else None
        )
        return cls(
            id=project.id,
            title=project.title,
            created_at=project.created_at,
            latest_job=RenderJobResponse.model_validate(latest) if latest else None,
        )

# ==========================================
# 6. SUBSCRIPTION PLAN SCHEMAS
# ==========================================
class SubscriptionPlanCreate(BaseModel):
    plan_code: str 
    name: str
    monthly_price: float 
    monthly_credits: int
    max_video_length_seconds: int
    max_resolution: str
    
    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanResponse(BaseModel):
    id: UUID
    plan_code: str 
    name: str
    monthly_price: float 
    monthly_credits: int
    max_video_length_seconds: int
    max_resolution: str
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 7. USER SUBSCRIPTION SCHEMAS
# ==========================================
class UserSubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    plan_id: UUID
    payment_subscription_id: Optional[str] = None
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 8. CREDIT SCHEMAS (Billing & Ledger)
# ==========================================
class CreditBalanceResponse(BaseModel):
    user_id: UUID
    total_balance: int

class CreditBatchResponse(BaseModel):
    id: UUID
    total_credits: int
    remaining_credits: int
    source: str
    expires_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class CreditTransactionResponse(BaseModel):
    id: UUID
    amount: int
    transaction_type: CreditTransactionType
    balance_after: Optional[int] = None
    render_job_id: Optional[UUID] = None
    description: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 9. AUTHENTICATION
# ==========================================
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expires_in: int

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ==========================================
# 10. AUTHENTICATION CHO GOOGLE OAUTH
# ==========================================
class GoogleAuthRequest(BaseModel):
    token: str = Field(..., description="Cục JWT nhận được từ Google Popup")

# ==========================================
# 11. LOGIN RESPONSE CHO GOOGLE OAUTH
# ==========================================
class UserProfileDTO(BaseModel):
    id: Optional[UUID] = None
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    plan: Optional[str] = None
    credit: Optional[int] = None


class LoginResponse(BaseModel):
    msg: str
    user: UserProfileDTO

# ==========================================
# 12. API RESULT
# ==========================================

T = TypeVar("T")

class CRUDStatusCodeRes(IntEnum):
    SUCCESS = 200
    CREATED = 201
    NO_DATA = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    PAYMENT_REQUIRED = 402
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500


class ApiResult(BaseModel, Generic[T]):
    code: int
    message: str
    is_success: bool
    data: Optional[T] = None
    errors: Optional[Dict[str, List[str]]] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "Success"):
        return cls(code=CRUDStatusCodeRes.SUCCESS, is_success=True, message=message, data=data)

    @classmethod
    def created(cls, data: Any = None, message: str = "Created"):
        return cls(code=CRUDStatusCodeRes.CREATED, is_success=True, message=message, data=data)

    @classmethod
    def error(cls, message: str = "An error occurred", code: int = CRUDStatusCodeRes.INTERNAL_SERVER_ERROR):
        return cls(code=code, is_success=False, message=message)

    @classmethod
    def validation_error(cls, errors: Dict[str, List[str]], message: str = "Validation error"):
        return cls(code=CRUDStatusCodeRes.UNPROCESSABLE_ENTITY, is_success=False, message=message, errors=errors)    