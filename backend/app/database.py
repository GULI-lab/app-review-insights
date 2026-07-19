"""数据库连接配置"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from pathlib import Path

from app.config import DATABASE_URL

# SQLite 用 StaticPool（单连接复用），避免并发写入冲突和连接泄漏警告
# aiosqlite + StaticPool 是 SQLite 异步场景的推荐配置
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    """初始化数据库表"""
    from app.models.db import Base  # noqa: 确保模型已加载
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
