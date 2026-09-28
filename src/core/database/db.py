# src/core/database/db.py
import os
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()
    
DATABASE_URL = os.getenv("DATABASE_URL")

# Lấy tên app từ biến môi trường, mặc định là "fastapi_api"
APP_NAME = os.getenv("APP_NAME", "fastapi_api") 

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False, 
    # Báo cho Postgres biết ai đang kết nối
    connect_args={
        "server_settings": {
            "application_name": APP_NAME
        }
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session