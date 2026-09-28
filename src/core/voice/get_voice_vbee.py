"""
Vbee API - Get List Voices
Tài liệu: https://api-docs.vbee.vn
"""

import requests
from dotenv import load_dotenv
import os

load_dotenv()

APP_ID       = os.getenv("VBEE_APP_ID")
ACCESS_TOKEN = os.getenv("VBEE_API_KEY")

BASE_URL = "https://vbee.vn/api"


def get_list_voices(app_id: str, access_token: str) -> dict:
    url = f"{BASE_URL}/public/v1/voices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "App-Id": app_id,
        "Content-Type": "application/json",
    }
    params = {
        "voice_ownership": "VBEE"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def print_voices(data: dict) -> None:
    """Parse và in danh sách giọng đọc từ response."""
    result     = data.get("result", {})
    voices     = result.get("voices", [])
    pagination = result.get("pagination", {})

    if not voices:
        print("Không tìm thấy giọng nào.")
        print("Response gốc:", data)
        return

    print(f"\n{'─' * 90}")
    print(f"{'STT':<5} {'Code':<45} {'Credit':<8} {'Demo URL'}")
    print(f"{'─' * 90}")

    for i, voice in enumerate(voices, start=1):
        code   = voice.get("code", "N/A")
        credit = voice.get("credit_factor", "N/A")
        demo   = voice.get("demo", "")
        print(f"{i:<5} {code:<45} {credit:<8} {demo}")

    print(f"{'─' * 90}")
    print(f"Tổng cộng trang này : {len(voices)} giọng")
    print(f"Còn trang tiếp theo : {'Có' if pagination.get('has_next_page') else 'Không'}")
    if pagination.get("next_cursor"):
        print(f"Next cursor         : {pagination['next_cursor']}")


def main():
    print("Đang lấy danh sách giọng từ Vbee API...\n")
    try:
        data = get_list_voices(APP_ID, ACCESS_TOKEN)
        print_voices(data)
    except requests.exceptions.HTTPError as e:
        print(f"Lỗi HTTP {e.response.status_code}: {e.response.text}")
    except requests.exceptions.ConnectionError:
        print("Không thể kết nối tới API. Kiểm tra lại mạng.")
    except requests.exceptions.RequestException as e:
        print(f"Lỗi request: {e}")


if __name__ == "__main__":
    main()