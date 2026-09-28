#!/bin/bash
# Usage: docker compose exec api bash migrate.sh
set -euo pipefail

echo "[migrate] Chờ database..."
python -c "
import asyncio, asyncpg, os, sys

async def wait():
    url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg', 'postgresql')
    for i in range(30):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print('[migrate] Database sẵn sàng')
            return
        except Exception as e:
            print(f'[migrate] Thử lần {i+1}/30: {e}')
            await asyncio.sleep(2)
    sys.exit(1)

asyncio.run(wait())
"

echo "[migrate] Chạy alembic upgrade head..."
alembic upgrade head
echo "[migrate] Hoàn tất"