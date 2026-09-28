# src/core/database/models/enums.py
import enum

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    PAST_DUE = 'PAST_DUE'
    CANCELED = 'CANCELED'
    TRIALING = 'TRIALING'

class PaymentOrderStatus(str, enum.Enum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'

class CreditTransactionType(str, enum.Enum):
    GRANT = 'GRANT'
    CONSUME = 'CONSUME'
    REFUND = 'REFUND'
    TOP_UP = 'TOP_UP'
    EXPIRE = 'EXPIRE'

class RenderJobStatus(str, enum.Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    RENDER_QUEUED = 'RENDER_QUEUED'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    INSUFFICIENT_CREDITS = 'INSUFFICIENT_CREDITS'

class AuthProvider(str, enum.Enum):
    LOCAL = 'local'
    GOOGLE = 'google'
    FACEBOOK = 'facebook'    