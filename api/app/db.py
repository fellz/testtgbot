from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    image_key: Mapped[str] = mapped_column(String(200))
    # Ключ идемпотентности от клиента (бот кладёт chat_id:message_id): повтор того же
    # апдейта Telegram или ретрай балансировщика не создаёт дубль товара.
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def get_session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session


__all__ = ["AsyncSession", "Base", "Product", "Session", "engine", "get_session"]
