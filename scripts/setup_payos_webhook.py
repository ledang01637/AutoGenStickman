# scripts/setup_payos_webhook.py
"""
Đăng ký webhook URL với PayOS — chạy 1 lần khi setup environment mới.

PayOS yêu cầu đăng ký webhook qua API (không có UI dashboard).
Sau khi đăng ký thành công, PayOS sẽ POST callback về URL này mỗi khi
có giao dịch thay đổi trạng thái.

Cách dùng:
    # Local (qua ngrok):
    python -m scripts.setup_payos_webhook https://abc123.ngrok-free.app

    # Production:
    python -m scripts.setup_payos_webhook https://api.your-domain.com

    # Hoặc dùng default từ env:
    python -m scripts.setup_payos_webhook
"""
import asyncio
import sys
from src.core.services.payment_service import payos_client
from src.config.config import settings

WEBHOOK_PATH = "/api/v1/payments/webhook/payos"


async def main(base_url: str | None = None) -> None:
    if not base_url:
        # Fallback: lấy từ env nếu không pass argument
        base_url = getattr(settings, "API_BASE_URL", None)
        if not base_url:
            print("❌ Cần pass base URL hoặc set API_BASE_URL trong .env")
            print("   Ví dụ: python -m scripts.setup_payos_webhook https://abc.ngrok-free.app")
            sys.exit(1)
    # Strip trailing slash để tránh double slash
    base_url = base_url.rstrip("/")
    webhook_url = f"{base_url}{WEBHOOK_PATH}"

    print(f"Đăng ký webhook URL với PayOS: {webhook_url}")

    try:
        result = await payos_client.webhooks.confirm(webhook_url)
        print(f"✅ Đăng ký thành công: {result}")
    except Exception as e:
        print(f"❌ Đăng ký thất bại: {e}")
        sys.exit(1)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(arg))