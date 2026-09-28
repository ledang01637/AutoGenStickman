# AutoGenStickMan

> Biến một dòng ý tưởng thành video kể chuyện hoàn chỉnh: kịch bản AI → hình ảnh AI → lồng tiếng AI → ghép video tự động.

Một nền tảng SaaS tạo video ngắn (TikTok / Reels / YouTube Shorts) cho thị trường Việt Nam. Người dùng nhập chủ đề, chọn độ dài và phong cách kể chuyện — hệ thống tự sinh kịch bản nhiều cảnh, tạo ảnh cho từng cảnh, lồng tiếng Việt, rồi ghép thành file MP4 dọc 9:16 có phụ đề karaoke.

**Stack:** FastAPI · Blazor WebAssembly · PostgreSQL · Redis · MoviePy · Claude · FLUX · Vbee

> [!IMPORTANT]
> Đây là mã nguồn của một sản phẩm đang chạy thật. Repo **không kèm** API key, chứng chỉ TLS, dữ liệu người dùng hay cấu hình production. Bạn cần tự đăng ký các dịch vụ bên thứ ba (xem [mục 8](#8-biến-môi-trường)) để chạy được. Một số tính năng còn dở — đọc [mục 12](#12-trạng-thái-hoàn-thiện) trước khi bắt tay vào.

---

## Mục lục

1. [Tính năng](#1-tính-năng)
2. [Kiến trúc](#2-kiến-trúc)
3. [Pipeline render](#3-pipeline-render)
4. [Các lớp bảo vệ request](#4-các-lớp-bảo-vệ-request)
5. [Tech stack](#5-tech-stack)
6. [Cấu trúc thư mục](#6-cấu-trúc-thư-mục)
7. [Yêu cầu hệ thống](#7-yêu-cầu-hệ-thống)
8. [Biến môi trường](#8-biến-môi-trường)
9. [Cài đặt & chạy](#9-cài-đặt--chạy)
10. [API Endpoints](#10-api-endpoints)
11. [Credit, gói cước & database](#11-credit-gói-cước--database)
12. [Trạng thái hoàn thiện](#12-trạng-thái-hoàn-thiện)
13. [Vận hành](#13-vận-hành)
14. [Đóng góp](#14-đóng-góp)
15. [License](#15-license)

---

## 1. Tính năng

| Nhóm | Chi tiết |
| --- | --- |
| **Sinh kịch bản** | Claude (Anthropic) sinh JSON nhiều cảnh: `voiceover`, `image_prompt`, timing. Có 5 pace, 5 tone, 14 story structure, 3 chế độ ngôn ngữ (`vi` / `en` / `vi_en`). |
| **Sinh hình ảnh** | FAL — FLUX.1 [schnell] cho chế độ nhanh, `grok-imagine-image` khi bật `use_best_model`. Ảnh 576×1024 (9:16), chạy song song có giới hạn concurrency. |
| **Lồng tiếng** | Vbee AIVoice — 8 giọng Việt (Bắc / Trung / Nam, thêm giọng đọc truyện và giọng tin tức). |
| **Ghép video** | MoviePy: hiệu ứng Ken Burns pan-zoom, fade transition, phụ đề **karaoke highlight từng từ** (timestamp lấy từ `faster-whisper`, fallback chia đều thời lượng nếu Whisper lỗi). |
| **Credit & gói cước** | 5 tier (Free / Basic / Trial / Pro / Ultra) gate theo tính năng. Credit theo lô có hạn dùng, tiêu FIFO theo ngày hết hạn, tự hoàn khi job fail. |
| **Thanh toán** | PayOS — mua gói và nạp credit lẻ, webhook idempotent. |
| **Xác thực** | Email/password + Google OAuth. JWT trong httpOnly cookie, refresh token rotation. |
| **Hàng đợi** | Job queue trên PostgreSQL (`SELECT … FOR UPDATE`) + Redis queue cho bước render, worker tách vai trò I/O và CPU. |
| **Theo dõi tiến độ** | SSE stream `progress %` + message realtime cho frontend. |
| **Vận hành** | Cleanup job hết TTL, distributed semaphore giới hạn render/VPS, maintenance mode bật/tắt qua flag file của Nginx. |

---

## 2. Kiến trúc

```
                      ┌────────────────────────┐
                      │  CDN / WAF (tuỳ chọn)  │
                      └───────────┬────────────┘
                                  ↓
                      ┌────────────────────────┐
                      │   Nginx (TLS, gzip)    │
                      └────┬──────────────┬────┘
                           │              │
         ┌─────────────────┘              └──────────────┐
         ↓                                              ↓
┌────────────────────┐                        ┌────────────────────┐
│  Blazor WASM SPA   │ ───── fetch / SSE ───▶ │  FastAPI :8000     │
│  (static + .wasm)  │                        │  src/main.py       │
└────────────────────┘                        └───┬────────────┬───┘
                                                  │            │
                                    ┌─────────────┘            │
                                    ↓                          ↓
                          ┌───────────────────┐      ┌───────────────────┐
                          │  PostgreSQL 15    │      │     Redis 7       │
                          │  job queue + data │      │  render queue,    │
                          └─────────┬─────────┘      │  semaphore, lock  │
                                    │                └─────────┬─────────┘
             ┌──────────────────────┴───────────┐              │
             ↓                                  ↓              │
   ┌────────────────────┐            ┌────────────────────┐    │
   │  worker-io  (×N)   │─ LPUSH ───▶│  worker-cpu  (×N)  │◀───┘
   │  Stage 1 · 2 · 3   │            │  Stage 4 (MoviePy) │
   │  Claude/FAL/Vbee   │            │  chạy process riêng│
   └────────────────────┘            └─────────┬──────────┘
                                                ↓
                                     ┌────────────────────┐
                                     │  /app/jobs/….mp4   │
                                     │  volume chia sẻ,   │
                                     │  Nginx serve       │
                                     └────────────────────┘

   ┌──────────────────────┐
   │  worker-primary (×1) │  = worker-io + vòng lặp cleanup (có Redis lock)
   └──────────────────────┘
```

Worker chọn vai trò bằng biến môi trường `WORKER_ROLE`:

| `WORKER_ROLE` | Việc làm | Concurrency mặc định |
| --- | --- | --- |
| `io` | Poll DB lấy job `PENDING` → Stage 1, 2, 3 → đẩy vào Redis render queue | 5 job / container |
| `cpu` | `BRPOP` Redis render queue → Stage 4 (MoviePy) | 1 job / container |
| `primary` | Như `io`, cộng thêm vòng lặp cleanup | 2 job / container |

Tách I/O khỏi CPU vì hai loại việc này có profile tài nguyên trái ngược: Stage 1–3 chủ yếu chờ mạng (nhẹ RAM, chạy song song nhiều được), Stage 4 ngốn CPU và RAM (phải giới hạn chặt).

---

## 3. Pipeline render

```
POST /api/v1/videos/generate
  └── trừ credit (SELECT FOR UPDATE) → tạo RenderJob status=PENDING
        ↓
worker-io: fetch_and_lock_job()  → status=PROCESSING
  ├── Stage 1  ClaudeEngine.generate_video_script()  → scenes JSON vào render_config (JSONB)
  ├── Stage 2 ∥ Stage 3  (asyncio.TaskGroup)
  │     ├── FalImageEngine   → jobs/<id>/images/*.png   [Redis semaphore: fal_slot]
  │     └── Vbee TTS         → jobs/<id>/audios/*.mp3   [Redis semaphore: vbee_slot]
  └── status=RENDER_QUEUED → LPUSH worker:render_queue
        ↓
worker-cpu: BRPOP worker:render_queue → status=PROCESSING
  └── Stage 4  render_final_video()   [Redis semaphore: render_slot — mặc định 2 slot/VPS]
        ├── chạy trong multiprocessing.Process riêng → kill cứng được khi quá hạn
        ├── Ken Burns pan-zoom + fade transition
        ├── phụ đề karaoke (faster-whisper "medium", int8, CPU)
        └── → jobs/<id>/video/<name>_final.mp4
        ↓
finalize_job_atomic()  → COMPLETED (ghi output_url)  |  FAILED (+ hoàn credit)
```

**Chi tiết đáng chú ý**

- **Quality gate:** nếu dưới 90% số cảnh hợp lệ (có đủ cả file ảnh và file audio tồn tại trên disk), Stage 4 fail thẳng và hoàn credit — thà không có video hơn là giao video thiếu cảnh.
- **Timeout động:** timeout I/O tính theo số cảnh (`60s + 15s × số_cảnh`, kẹp trong 600–1800s); timeout render tính theo thời lượng video × số cảnh (sàn 180s). Quá hạn thì `SIGTERM` → `SIGKILL` process con, không để zombie ăn CPU.
- **Semaphore phân tán:** `asyncio.Semaphore` chỉ có tác dụng trong một process, nên nhiều container sẽ cùng render và vượt RAM. `src/worker/redis_semaphore.py` dùng Redis `SET NX EX` làm slot counter dùng chung, TTL tự nhả slot nếu worker crash.
- **Refund atomic:** hoàn credit chạy qua PostgreSQL function (xem `alembic/versions/…postgresql_functions.py`), có unique index trên `credit_transactions` chống double-consume / double-refund cho cùng một job.

---

## 4. Các lớp bảo vệ request

| Lớp | Cơ chế | Trạng thái |
| --- | --- | --- |
| 1 | CDN / WAF trước Nginx (DDoS, geo-block, ẩn IP gốc) | Ngoài code — tuỳ hạ tầng bạn dùng |
| 2 | `security_middleware`: giới hạn body (mặc định 2 MB), security headers, HSTS khi `ENV=production` | ✅ |
| 2 | `CORSMiddleware` chỉ whitelist domain trong `ALLOWED_ORIGINS` | ✅ |
| 2 | SlowAPI rate-limit theo IP thật (`CF-Connecting-IP` → `X-Forwarded-For` → `client.host`) hoặc theo `user_id` | ✅ trên auth / payment / subscription / user — ❌ **chưa bật** trên `POST /videos/generate` |
| 3 | `get_current_user`: decode + verify JWT (Bearer header hoặc cookie) | ✅ |
| 4 | `SELECT … FOR UPDATE` trên `credit_batches` → trừ credit atomic trước khi tạo job | ✅ |
| 5 | `check_and_increment_global_cap()`: cầu dao chặn khi vượt trần chi phí AI/ngày | ❌ **code có, chưa được gọi** |
| 6 | Sanitize `topic` chống prompt injection (regex chặn `ignore previous`, `system:`, …) | ✅ |

Docstring trong `src/main.py` và `src/api/video_api.py` vẫn mô tả đầy đủ 5 lớp — thực tế lớp 5 và rate-limit của `/generate` chưa hoạt động. Xem [mục 12](#12-trạng-thái-hoàn-thiện).

---

## 5. Tech stack

| Layer | Công nghệ |
| --- | --- |
| Frontend | Blazor WebAssembly (.NET 8), MudBlazor |
| Backend API | FastAPI 0.135, Python 3.12, Uvicorn (dev) / Gunicorn + UvicornWorker (prod) |
| Worker | Python 3.12 asyncio, MoviePy 2.2, FFmpeg, ImageMagick |
| Database | PostgreSQL 15, SQLAlchemy 2.0 async (`asyncpg`), Alembic |
| Cache / Queue | Redis 7 |
| AI — kịch bản | Anthropic Claude (mặc định `claude-sonnet-4-6`) |
| AI — hình ảnh | FAL: `fal-ai/flux/schnell`, `xai/grok-imagine-image` |
| AI — giọng nói | Vbee AIVoice (TTS tiếng Việt) |
| AI — phụ đề | `faster-whisper` (model `medium`, int8, chạy CPU) |
| Auth | PyJWT + httpOnly cookie, Google OAuth 2.0 (`google-auth`) |
| Payment | PayOS (`payos==1.1.0`) |
| Rate limit | SlowAPI |
| Reverse proxy | Nginx — TLS, `gzip_static` cho Blazor WASM, serve file video |
| Triển khai | Docker Compose (dev + prod) |

---

## 6. Cấu trúc thư mục

```
AutoGenStickMan/
├── src/
│   ├── main.py                     # Entrypoint FastAPI, mount routers, /health
│   ├── api/
│   │   ├── auth_api.py             # login, login-google, refresh, logout
│   │   ├── user_api.py             # register, me
│   │   ├── video_api.py            # generate, my-videos, estimate-cost, progress (SSE)
│   │   ├── payment_api.py          # top-up, tạo order, tra cứu order, webhook PayOS
│   │   ├── subscription_api.py     # subscribe, list, create-plans (admin)
│   │   └── deps.py                 # get_current_user, get_user_plan
│   ├── config/
│   │   ├── config.py               # Pydantic Settings — đọc .env
│   │   └── plan_features.py        # Ma trận tính năng theo gói + validator
│   ├── core/
│   │   ├── middleware.py           # CORS, rate limit, security headers, body limit
│   │   ├── base_ai_engine.py       # Base class cho mọi AI engine (retry, cost tracking)
│   │   ├── rate_limit_policy.py    # Các policy rate limit dùng chung
│   │   ├── database/
│   │   │   ├── db.py               # Async engine + AsyncSessionLocal
│   │   │   ├── schemas.py          # Pydantic DTO (ApiResult, VideoProjectCreate, …)
│   │   │   └── models/             # ORM: User, VideoProject, RenderJob, CreditBatch,
│   │   │                           #      CreditTransaction, PaymentOrder, Subscription…
│   │   ├── security/
│   │   │   ├── tokens.py           # Tạo / decode JWT, refresh rotation
│   │   │   └── global_cap.py       # Cầu dao chi phí ngày (Redis, fallback file JSON)
│   │   ├── services/
│   │   │   └── payment_service.py  # Tích hợp PayOS + xử lý webhook
│   │   ├── scripts/                # Stage 1 — sinh kịch bản
│   │   │   ├── claude_engine.py
│   │   │   ├── base_text_engine.py
│   │   │   ├── script_config.py    # Preset tone / structure / language / platform
│   │   │   ├── pace.py             # Tính số cảnh + thời lượng theo pace
│   │   │   └── calibrate_tts.py    # Hiệu chỉnh WPM cho TTS
│   │   ├── images/                 # Stage 2 — sinh ảnh
│   │   │   ├── fal_image_engine.py         # ĐANG DÙNG
│   │   │   ├── nano_banana_engine.py       # Gemini — chưa nối vào worker
│   │   │   └── browser2api/                # Browser automation — thử nghiệm, chưa nối
│   │   ├── voice/                  # Stage 3 — TTS
│   │   │   ├── vbee_engine.py
│   │   │   ├── audio_step.py       # Orchestrator Stage 3
│   │   │   └── get_voice_vbee.py   # Helper liệt kê giọng đọc
│   │   ├── moviepy/                # Stage 4 — ghép video
│   │   │   ├── video_engine.py
│   │   │   ├── caption_engine.py   # Phụ đề karaoke + faster-whisper
│   │   │   └── animation_engine.py # Ken Burns pan-zoom
│   │   └── animation/              # Pipeline stickman vẽ bằng code — BETA, chưa nối
│   │       ├── animation_pipeline.py
│   │       ├── claude_animation_engine.py
│   │       ├── stickman_animation_engine.py
│   │       ├── renderer.py · motion.py · validators.py · props.py · constants.py
│   │       ├── poses_old.py        # 10 pose — bản ĐANG được dùng
│   │       ├── poses/              # 8 pose IK-based — bản refactor, chưa wire
│   │       └── backgrounds/        # 7 background × 3 variant
│   ├── worker/
│   │   ├── main.py                 # Vòng lặp io / cpu / primary
│   │   ├── db_helpers.py           # fetch_and_lock_job, finalize_job_atomic, patch JSONB
│   │   ├── cleanup.py              # Xoá job hết TTL (có Redis lock)
│   │   ├── redis_client.py
│   │   └── redis_semaphore.py      # Slot render / fal / vbee dùng chung toàn VPS
│   └── utils/                      # logger, file_manager, path_utils, voiceover_trimmer…
├── frontend/                       # Blazor WebAssembly SPA
│   ├── Program.cs · App.razor
│   ├── Pages/                      # Home, Studio, History, Login, Pricing, Topup,
│   │                               # PaymentResult, Maintenance, NotFound
│   ├── Layout/ · Common/ · Models/ · Services/ · Themes/
│   └── wwwroot/                    # appsettings*.json, index.html, css, fonts, sitemap
├── alembic/versions/               # 8 migration
├── nginx/                          # nginx.conf (prod), nginx.local.conf, maintenance.conf
├── scripts/setup_payos_webhook.py  # Đăng ký webhook PayOS (chạy 1 lần / môi trường)
├── Dockerfile                      # base / development / worker / production
├── Dockerfile.frontend             # Build Blazor WASM + Nginx
├── docker-compose.yml              # Dev: nginx, api, worker, worker-cpu, db, redis
├── docker-compose.prod.yml         # Prod: worker-io ×2, worker-cpu ×2, worker-primary ×1
├── deploy.sh · migrate.sh
├── requirements.txt · pytest.ini · alembic.ini · global.json
└── .env.prod.example               # Template biến môi trường
```

---

## 7. Yêu cầu hệ thống

- **Docker** + **Docker Compose v2** — cách chạy được khuyến nghị cho mọi môi trường.
- Python **3.12** (chỉ khi chạy backend ngoài Docker).
- .NET SDK **8.0.202** (chỉ khi build frontend ngoài Docker — xem `global.json`).
- PostgreSQL 15 và Redis 7 — đã có sẵn trong `docker-compose.yml`.
- FFmpeg + ImageMagick — đã cài trong base image của `Dockerfile`.
- Tài khoản / API key: **Anthropic**, **FAL**, **Vbee**, **Google OAuth**, **PayOS** (thêm **Gemini** nếu muốn bật `NanoBananaEngine`).

**Về tài nguyên:** Stage 4 và model `faster-whisper medium` là phần ngốn RAM nhất. Cấu hình prod mẫu đặt limit 3 GB RAM / 2 CPU cho mỗi `worker-cpu` và tối đa 2 render đồng thời trên toàn VPS. Máy dưới 4 GB RAM sẽ swap và render rất chậm.

---

## 8. Biến môi trường

Copy template rồi điền giá trị của bạn:

```bash
cp .env.prod.example .env
```

### Bắt buộc — thiếu là app không khởi động

`src/config/config.py` khai báo các biến này không có default, Pydantic sẽ raise lỗi ngay khi import:

| Key | Ý nghĩa |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude — Stage 1 sinh kịch bản |
| `FAL_KEY` | FAL — Stage 2 sinh ảnh |
| `GEMINI_API_KEY` | Google Gemini — hiện chỉ `NanoBananaEngine` dùng (chưa nối vào worker) |
| `CHATGPT_API_KEY` | **Không dùng ở đâu cả** nhưng vẫn bắt buộc — xem [mục 12](#12-trạng-thái-hoàn-thiện) |
| `VBEE_API_KEY`, `VBEE_APP_ID` | Vbee AIVoice — Stage 3 |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `SECRET_KEY` | Secret ký JWT (HS256) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 |
| `ENV` | `development` \| `production` — bật/tắt `/docs`, `/redoc`, HSTS |
| `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` | Credential PayOS |
| `PAYOS_RETURN_URL`, `PAYOS_CANCEL_URL` | URL frontend nhận redirect sau thanh toán |

### Có default — chỉnh khi cần

| Key | Default | Ý nghĩa |
| --- | --- | --- |
| `REDIS_URL` | `redis://redis:6379/0` | Kết nối Redis |
| `APP_ENV` / `APP_NAME` | `development` / `autogen` | Nhãn phục vụ logging |
| `ALLOWED_ORIGINS` | *(rỗng)* | Whitelist CORS, phân cách bằng dấu phẩy. **Để rỗng là browser bị chặn hết** |
| `CLIENT_URL` | `http://localhost` | Dùng để dựng absolute URL cho file video output |
| `COOKIE_SECURE` | `true` | Đặt `false` khi dev local qua HTTP |
| `COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |

### Đọc trực tiếp qua `os.getenv` (không qua Settings)

| Key | Default | Nơi dùng |
| --- | --- | --- |
| `WORKER_ROLE` | `io` | `src/worker/main.py` — `io` \| `cpu` \| `primary` |
| `FAL_CONCURRENCY` | `2` | Số job gọi FAL song song toàn hệ thống |
| `VBEE_CONCURRENCY` | `2` | Số job gọi Vbee song song toàn hệ thống |
| `MAX_BODY_SIZE_MB` | `2` | Giới hạn body request |
| `COST_PER_VIDEO_VND` | `5000` | Chi phí ước tính / video, dùng cho global cap |
| `MAX_DAILY_COST_VND` | `600000` | Trần chi phí AI / ngày |
| `ANIMATION_OUTPUT_DIR` | `/app/jobs` | Output pipeline animation |
| `ANIMATION_MAX_RETRIES` | `1` | Retry pipeline animation |

`docker-compose.prod.yml` còn cần `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PASSWORD` trong `.env.prod` để dựng container db/redis.

> [!WARNING]
> Không commit `.env`, `.env.prod`, chứng chỉ TLS hay database dump. `.gitignore` đã chặn các file này — nhưng vẫn nên kiểm tra `git status` trước mỗi lần push.

---

## 9. Cài đặt & chạy

### 9.1. Development

```bash
git clone <repo-url> AutoGenStickMan
cd AutoGenStickMan
cp .env.prod.example .env
docker compose up --build
```

Sau khi container lên:

| Thành phần | Địa chỉ |
| --- | --- |
| Frontend (qua Nginx) | http://localhost |
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs *(tự tắt khi `ENV=production`)* |
| PostgreSQL | `localhost:5433` (trong container vẫn là 5432) |
| Redis | `localhost:6379` |

Lệnh hay dùng:

```bash
docker compose up -d
docker compose logs -f api worker
docker compose restart worker
docker compose down
docker compose down -v
```

### 9.2. Migrate database

Lần đầu:

```bash
docker compose exec api bash migrate.sh
```

Hoặc gọi trực tiếp Alembic:

```bash
docker compose exec api alembic upgrade head
```

Tạo migration mới sau khi sửa model SQLAlchemy (chạy từ host, trỏ vào port 5433):

```bash
DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5433/mydb" alembic revision --autogenerate -m "mo_ta_ngan"
```

### 9.3. Đăng ký webhook PayOS

PayOS yêu cầu đăng ký webhook URL qua API, không có UI. Chạy một lần cho mỗi môi trường:

```bash
python -m scripts.setup_payos_webhook https://api.your-domain.com
```

Khi dev local, dùng tunnel (ngrok, cloudflared…) và truyền URL public của tunnel vào.

### 9.4. Production

Cần chứng chỉ TLS đặt tại `nginx/certs/fullchain.pem` và `nginx/certs/privkey.pem`, cùng file `.env.prod` đã điền đủ.

```bash
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` sẽ: pull code → copy cert từ Let's Encrypt → build lại (no cache) → **chạy migration trước khi deploy** → `up -d --force-recreate` → prune image cũ.

> Script đang hardcode đường dẫn cert và tên domain của bản deploy gốc. Sửa lại cho domain của bạn trước khi chạy.

Khác biệt so với dev: API không expose port (chỉ đi qua Nginx), 4 Gunicorn worker, chia worker thành `worker-io` ×2 / `worker-cpu` ×2 / `worker-primary` ×1, có resource limit, HSTS bật, `/docs` tắt.

### 9.5. Build frontend ngoài Docker

```bash
cd frontend
dotnet restore
dotnet run
```

Sửa `frontend/wwwroot/appsettings.json` để trỏ `ApiUrl` về backend của bạn.

### 9.6. Chạy test

```bash
pytest
```

> `pytest.ini` đang trỏ `testpaths = tests`, trong khi thư mục thực tế tên `test/` và **không được commit**. Chạy `pytest` trên bản clone sạch sẽ thu được 0 test. Xem [mục 12](#12-trạng-thái-hoàn-thiện).

---

## 10. API Endpoints

Prefix `/api/v1`. Xác thực bằng JWT trong httpOnly cookie hoặc header `Authorization: Bearer <token>`. Mọi response bọc trong `ApiResult<T>`: `is_success`, `code`, `message`, `data`, `errors`.

### Auth — `src/api/auth_api.py`

| Method | Path | Mô tả |
| --- | --- | --- |
| POST | `/auth/login` | Đăng nhập email + password (rate-limit theo IP) |
| POST | `/auth/login-google` | Đăng nhập Google (verify `id_token`) |
| POST | `/auth/refresh` | Refresh access token, rotate refresh token |
| POST | `/auth/logout` | Xoá cookie + clear refresh token trong DB |

### Users — `src/api/user_api.py`

| Method | Path | Mô tả |
| --- | --- | --- |
| POST | `/users/register` | Đăng ký local, cấp lô credit chào mừng có hạn |
| GET | `/users/me` | Profile + gói hiện tại + số dư credit |

### Videos — `src/api/video_api.py`

| Method | Path | Mô tả |
| --- | --- | --- |
| POST | `/videos/generate` | Trừ credit + tạo job → `{project_id, job_id, cost_credits, status}` |
| GET | `/videos/my-videos` | Danh sách project của user (kèm job) |
| GET | `/videos/estimate-cost` | Ước tính credit theo `minutes` + `pace`, kèm số dư và `can_afford` |
| GET | `/videos/progress/{job_id}` | **SSE stream** tiến độ, trả `video_url` khi xong |

### Payments — `src/api/payment_api.py`

| Method | Path | Mô tả |
| --- | --- | --- |
| POST | `/payments/top-up` | Nạp credit lẻ → trả `checkout_url` |
| POST | `/payments` | Tạo payment order (mua gói hoặc nạp lẻ) |
| GET | `/payments/{order_id}` | Tra cứu order theo UUID |
| GET | `/payments/by-code/{order_code}` | Tra cứu theo `order_code` — frontend dùng sau khi PayOS redirect |
| POST | `/payments/webhook/payos` | Webhook PayOS (ẩn khỏi schema, không rate-limit, verify checksum + idempotent) |

### Subscriptions — `src/api/subscription_api.py`

| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/subscriptions/list` | Liệt kê gói, đánh dấu `is_current_plan` |
| POST | `/subscriptions/{plan_id}/subscribe` | Tạo order cho gói → `checkout_url` PayOS |
| POST | `/subscriptions/create-plans` | Tạo gói mới — cần role admin |

### Khác

| Method | Path | Mô tả |
| --- | --- | --- |
| GET | `/health` | Healthcheck, không cần auth |
| GET | `/api/v1/admin/cap-status` | Trạng thái cầu dao chi phí — **hiện chỉ yêu cầu đăng nhập, chưa check role admin** |

---

## 11. Credit, gói cước & database

### Công thức credit

```python
cost_credits = max(total_scenes + ceil(minutes) * 2, 3)
```

`total_scenes` do `calc_scene_params(minutes, pace)` tính, hoặc do client truyền thẳng. Bảng giá bán và tỉ lệ quy đổi tiền tệ không nằm trong repo này — bạn tự quyết định theo chi phí nhà cung cấp của mình.

### Ma trận tính năng theo gói

Định nghĩa tại `src/config/plan_features.py`. Đây là giới hạn **kỹ thuật**, không phải bảng giá:

| Gói | Thời lượng tối đa | Pace | Tone | Story structure | Ngôn ngữ | Giọng đọc |
| --- | --- | --- | --- | --- | --- | --- |
| Free | 0.5 phút | balanced, dynamic | serious | 2 | `vi` | 1 |
| Basic | 1 phút | + storytelling | + storytelling, motivational | 6 | `vi` | 3 |
| Trial | 3 phút | + fast_cut | + genz_meme | 11 | `vi`, `en` | tất cả |
| Pro | 3 phút | 4 pace | 4 tone | 11 | + `vi_en` | tất cả |
| Ultra | 5 phút | + cinematic | tất cả (gồm dark_humor) | tất cả (14) | `vi`, `en`, `vi_en` | tất cả |

`PlanFeatureValidator` có hai chế độ: `validate()` raise HTTP 403 kèm gợi ý nâng cấp, còn `apply_defaults()` âm thầm hạ tham số về mức hợp lệ. Endpoint `/generate` hiện dùng `apply_defaults()` — người dùng gửi tham số vượt gói sẽ bị hạ xuống chứ không nhận lỗi.

### Database

| Bảng | Vai trò |
| --- | --- |
| `users` | email, `password_hash` (nullable cho OAuth), `auth_provider`, `role`, `plan`, `registration_ip`, refresh token |
| `subscription_plans` | `plan_code`, giá tháng, credit tháng, giới hạn độ dài / resolution |
| `user_subscriptions` | Liên kết user ↔ gói, `status` (ACTIVE / PAST_DUE / CANCELED / TRIALING), kỳ hạn |
| `payment_orders` | `order_code` (BigInt của PayOS), `amount`, XOR giữa `plan_id` và `top_up_credits`, `status` |
| `payment_webhook_events` | Log idempotency cho webhook |
| `credit_batches` | Lô credit có hạn (welcome / subscription / top-up), tiêu FIFO theo `expires_at ASC` |
| `credit_transactions` | Ledger: GRANT / CONSUME / REFUND / TOP_UP / EXPIRE — unique index chống double-consume theo job |
| `video_projects` | Tiêu đề + `project_metadata` (JSONB) |
| `render_jobs` | `status`, `render_config` (JSONB chứa scenes), `worker_id` + `locked_at` để claim atomic, `retry_count`, `priority` theo gói |

`RenderJobStatus`: `PENDING` → `PROCESSING` → `RENDER_QUEUED` → `PROCESSING` → `COMPLETED` | `FAILED` (còn `INSUFFICIENT_CREDITS` dành cho trường hợp thiếu credit).

---

## 12. Trạng thái hoàn thiện

Phần này ghi lại đúng những gì **chưa xong** hoặc **chưa khớp với docstring/tài liệu trong code**, để bạn không mất thời gian debug những thứ vốn chưa được nối.

### 🔴 Tính năng lớn chưa nối vào hệ thống

**1. Pipeline stickman animation (vẽ nhân vật bằng code) — chưa dùng được từ sản phẩm**

Toàn bộ `src/core/animation/` đã viết xong và chạy được độc lập: engine sinh JSON kịch bản animation, renderer matplotlib pipe trực tiếp sang FFmpeg (không ghi PNG trung gian), 7 background × 3 variant, 10 pose, 18 prop, validator schema. Nhưng:

- `run_animation_workflow()` (`src/worker/main.py:559`) **không được gọi** từ `io_worker_loop()` hay `cpu_worker_loop()` — không có nhánh `if render_type == "animation"` nào trong worker.
- Frontend hardcode `render_type = "static"` (`frontend/Pages/Studio.razor.cs:485`).

Vì vậy video hiện tại luôn là ảnh AI tĩnh + Ken Burns, chưa phải stickman chuyển động thật. Cần làm: thêm nhánh rẽ theo `render_type` trong worker loop, cho frontend chọn, test end-to-end với Vbee key thật.

**2. Package `poses/` mới chưa được wire**

`src/core/animation/poses/` là bản refactor 8 pose theo hướng IK, chia thành `locomotion` / `standing` / `interaction`. Nhưng `renderer.py:26` và `stickman_animation_engine.py:41` vẫn import từ `poses_old.py`. Hiện `poses_old.py` là bản đang chạy; `poses/` là code chết cho tới khi đổi import và map lại tên pose.

**3. Cầu dao chi phí (global cap) chưa bật**

`check_and_increment_global_cap()` đã viết đầy đủ (Redis INCR + TTL, fallback file JSON) và được import vào `src/api/video_api.py:25`, nhưng **không được gọi ở bất kỳ đâu**. Nghĩa là hiện không có gì chặn chi phí AI vượt trần trong ngày, dù docstring `src/main.py` mô tả đây là "Lớp 5". Endpoint `/admin/cap-status` vẫn đọc được số liệu, nhưng số liệu đó không bao giờ tăng.

**4. Rate limit của endpoint đắt nhất đang bị comment**

`src/api/video_api.py:205`: `# @limiter.limit(RateLimit.EXPENSIVE, key_func=RateLimit.KEY_USER)`. Docstring nói `3/day;1/minute` per IP — thực tế `POST /videos/generate` **không có rate limit nào**. Hàng rào duy nhất còn lại là số dư credit.

**5. Role admin chưa hoàn chỉnh**

`require_admin` chỉ được định nghĩa cục bộ trong `src/api/subscription_api.py:30`, dùng cho đúng một endpoint. `/api/v1/admin/cap-status` trong `src/main.py:59` còn nguyên `# TODO: thêm Depends(require_admin)` — mọi user đã đăng nhập đều gọi được.

### 🟡 Cấu hình khai báo nhưng không có tác dụng

| Thứ | Vấn đề |
| --- | --- |
| `CHATGPT_API_KEY` | Bắt buộc trong `Settings` nhưng không có code nào dùng. Thiếu là app không start — phải điền giá trị giả hoặc xoá khỏi `config.py`. |
| `claude_model` theo gói | `plan_features.py` định nghĩa model riêng cho từng tier (Haiku cho Free/Basic, Sonnet cho Pro/Ultra) và ghi vào metadata, nhưng worker gọi `ClaudeEngine()` không truyền model → **luôn dùng `claude-sonnet-4-6`**. Trong `script_config.py:47` tier `"fast"` cũng đã bị comment. Gói Free hiện tiêu model đắt như gói Ultra. |
| `max_credits_per_video` | Khai báo cho cả 5 gói, không được đọc ở đâu cả. |
| `is_speed` | Nhận từ API, lưu vào metadata, worker không đọc. |
| `ANTHROPIC_MODEL_NAME` | Docstring `claude_engine.py:98` nói đọc từ env — thực tế default hardcode `claude-sonnet-4-6`. |
| `JOB_TTL_HOURS`, `CLEANUP_INTERVAL_S` | Hardcode trong `cleanup.py:20-21` (1 giờ / 30 phút), **không đọc env**, nên set trong `docker-compose.yml` không có tác dụng. |
| `WORKER_PRIMARY` | Có trong `docker-compose.prod.yml`, không code nào đọc. Vai trò worker quyết định bởi `WORKER_ROLE`. |
| `GLOBAL_RENDER_SLOTS` | Hardcode `= 2` trong `redis_semaphore.py:32`, trong khi `FAL_SLOTS` / `VBEE_SLOTS` đọc được từ env. Muốn đổi số render đồng thời phải sửa code. |

### 🟡 Module chưa nối / code chết

| Đường dẫn | Tình trạng |
| --- | --- |
| `src/core/images/nano_banana_engine.py` | Engine Gemini viết xong, worker chỉ dùng `FalImageEngine`. `GEMINI_API_KEY` vẫn bắt buộc. |
| `src/core/images/browser2api/` | Module browser-automation (Playwright) độc lập, chưa nối vào pipeline. **`playwright` không có trong `requirements.txt`** → import sẽ fail nếu gọi tới. |
| `src/utils/concurrency_gate.py` | Không được import ở đâu. Đã bị `redis_semaphore.py` thay thế. |

### 🟡 Test & CI

- Thư mục test thực tế là `test/`, nhưng `pytest.ini` và `pyproject.toml` đều trỏ `testpaths = ["tests"]` → sai tên.
- `test/` nằm trong `.gitignore`, nên **bản public gần như không có test**. Vài file test animation vẫn còn trong lịch sử git do được commit trước khi thêm vào `.gitignore`.
- Chưa có CI — không có workflow GitHub Actions nào trong repo.

### 🟢 Dự định làm tiếp

- Thêm `animate_fn` (background động) cho `bedroom`, `cafe`, `city_day`, `park_day`, `street_food` — hiện chỉ `office` có.
- Backgrounds đợt 2: `city_night`, `kitchen`, `convenience_store`, `bus_stop`, `home_cozy`, `classroom`, `supermarket`, `mindspace`.
- Bổ sung 12 prop (`wallet_empty`, `graph_up`, `graph_down`, `lightbulb`, `board`, `chair`, `key`, `gift`, `arrow_up`, `arrow_down`, `wall`, `box`) — thêm vào `props.py` và `VALID_PROPS` trong `validators.py`.
- SSE progress riêng cho pipeline animation.
- Retry theo từng scene thay vì fail cả job (quality gate 90% hiện là all-or-nothing).

### ⚠️ Trước khi bạn deploy bản của mình

Repo này là snapshot đã được dọn, **không kèm lịch sử git** của bản private gốc. Những chỗ cần thay giá trị thật trước khi chạy production:

- `nginx/certs/` — **để trống có chủ ý**, chỉ có `.gitkeep` và hướng dẫn. Tự sinh cert (dev) hoặc để `deploy.sh` copy từ Let's Encrypt (prod). Xem `nginx/certs/README.md`.
- `your-domain.com` — placeholder, còn trong `nginx/nginx.conf`, `deploy.sh`, `frontend/wwwroot/appsettings.Production.json`, `sitemap.xml`, `robots.txt`, `.env.prod.example`, `scripts/setup_payos_webhook.py`.
- `YOUR_GOOGLE_OAUTH_CLIENT_ID` — trong `frontend/wwwroot/appsettings*.json` và `.env.prod.example`. Client ID không phải secret (nó nằm trong bundle browser), nhưng Client Secret thì chỉ được để trong `.env`.
- `calculate_video_cost()` trong `src/api/video_api.py` — công thức credit giữ nguyên, nhưng hệ số được chọn theo giá nhà cung cấp và biên lợi nhuận của bản gốc. Tính lại theo chi phí của bạn.
- Thư mục test không có trong snapshot này — xem phần Test & CI ở trên.

Và đừng bao giờ commit: `.env*` (trừ `.example`), file `.pem`, database dump (`.gitignore` đã chặn `*.sql`, `*.dump`, `*.sql.gz`).
---

## 13. Vận hành

### Log

`src/utils/logger.py` cung cấp logger thống nhất, log structured dạng key-value qua `extra` dict — ingest được vào ELK / Loki mà không cần parse thêm. Event name theo quy ước `<stage>.<action>`: `stage1.start`, `io_job.timeout`, `cpu_job.slot_acquired`, `render_process.kill`…

### File output

- Worker ghi vào `/app/jobs/<job_folder>/video/<name>_final.mp4`.
- Volume `jobs_data` share giữa `api`, các `worker` và `nginx`.
- Nginx serve `/app/jobs/` với `Accept-Ranges: bytes` và `Content-Disposition: attachment`.

### Cleanup

Chỉ worker `primary` chạy `cleanup_loop()`. Có Redis lock (`SET NX EX`) để nhiều primary không dọn trùng. Job `COMPLETED` / `FAILED` quá **1 giờ** sẽ bị xoá folder và soft-delete record; chu kỳ 30 phút. Hai giá trị này hardcode trong `cleanup.py`.

### Maintenance mode

Nginx đọc một flag file, không cần rebuild image:

```bash
docker compose -f docker-compose.prod.yml exec nginx touch /etc/nginx/maintenance.flag
```

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

Xoá flag (`rm /etc/nginx/maintenance.flag`) rồi reload lại để tắt. Khi bật: frontend trả trang `maintenance.html`, API trả HTTP 503 kèm JSON.

### Giới hạn concurrency

| Cơ chế | Mặc định | Nơi cấu hình |
| --- | --- | --- |
| Job I/O song song / container | 5 | `_CONCURRENCY_MAP` trong `worker/main.py` |
| Job CPU song song / container | 1 | `_CONCURRENCY_MAP` |
| Render đồng thời toàn hệ thống | 2 | `GLOBAL_RENDER_SLOTS` (hardcode) |
| Gọi FAL đồng thời | 2 | `FAL_CONCURRENCY` |
| Gọi Vbee đồng thời | 2 | `VBEE_CONCURRENCY` |
| Body request | 2 MB | `MAX_BODY_SIZE_MB` |

---

## 14. Đóng góp

Rất hoan nghênh PR, đặc biệt cho các phần nêu ở [mục 12](#12-trạng-thái-hoàn-thiện).

1. **Nhánh:** tạo từ `main`, tên `feature/<mô-tả-ngắn>` hoặc `fix/<mô-tả-ngắn>`.
2. **Code style:**
   - Python: async/await xuyên suốt, dependency injection của FastAPI, SQLAlchemy 2.0 style `select()` — không dùng `session.query()`. Comment giải thích **vì sao**, không describe lại code.
   - C# / Blazor: theo pattern MudBlazor + service injection sẵn có trong `frontend/Common/`.
3. **Migration:** mọi thay đổi schema phải kèm migration Alembic mới. Không sửa migration cũ.
4. **Test:** thêm test cho logic mới (async pytest). Sửa được vụ `testpaths` sai tên thì càng tốt.
5. **PR:** mô tả rõ thay đổi, nêu tác động tới credit / payment / security, kèm screenshot nếu chạm UI.
6. **Không commit:** `.env*` (trừ `.example`), chứng chỉ, `jobs/`, database dump, `frontend/bin/`, `frontend/obj/`.

---

## 15. License

Repo hiện **chưa kèm file LICENSE**. Theo mặc định của luật bản quyền, điều đó nghĩa là chưa ai được phép sao chép, sửa hay phân phối lại — kể cả khi mã nguồn đã công khai.

Nếu muốn mở thật sự cho cộng đồng, hãy thêm file `LICENSE` ở thư mục gốc. Vài lựa chọn phổ biến:

- **MIT** — dễ dãi nhất, ai cũng dùng được kể cả thương mại.
- **Apache-2.0** — như MIT nhưng có thêm điều khoản về patent.
- **AGPL-3.0** — buộc ai chạy bản sửa đổi dưới dạng dịch vụ web phải công khai source; phù hợp nếu muốn tránh người khác dựng SaaS cạnh tranh từ chính code này.

---

## Ghi nhận

Dự án dùng: [FastAPI](https://fastapi.tiangolo.com/) · [Blazor](https://dotnet.microsoft.com/apps/aspnet/web-apps/blazor) · [MudBlazor](https://mudblazor.com/) · [MoviePy](https://zulko.github.io/moviepy/) · [Anthropic Claude](https://www.anthropic.com/) · [FAL](https://fal.ai/) · [Vbee AIVoice](https://aivoice.com.vn/) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [PayOS](https://payos.vn/) · [Alembic](https://alembic.sqlalchemy.org/)
