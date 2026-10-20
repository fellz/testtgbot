import asyncio
import socket
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from . import storage
from .config import settings
from .db import AsyncSession, Product, get_session

app = FastAPI(title="testtgbot catalog", root_path="/api")

HOSTNAME = socket.gethostname()


@app.middleware("http")
async def instance_header(request, call_next):
    # Какая реплика ответила — видно в проверке отказоустойчивости.
    response = await call_next(request)
    response.headers["X-Instance"] = HOSTNAME
    return response


EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class ProductOut(BaseModel):
    id: int
    name: str
    image_url: str
    created_at: datetime

    @classmethod
    def of(cls, p: Product) -> "ProductOut":
        return cls(id=p.id, name=p.name, image_url=storage.public_url(p.image_key), created_at=p.created_at)


def require_internal(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    if x_internal_token != settings.internal_token:
        raise HTTPException(401, "invalid internal token")


@app.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_session)]):
    await session.execute(text("select 1"))
    await asyncio.to_thread(storage.ping)
    return {"ok": True}


@app.get("/products", response_model=list[ProductOut])
async def list_products(session: Annotated[AsyncSession, Depends(get_session)]):
    rows = await session.scalars(select(Product).order_by(Product.created_at.desc(), Product.id.desc()))
    return [ProductOut.of(p) for p in rows]


@app.post("/products", response_model=ProductOut, status_code=201, dependencies=[Depends(require_internal)])
async def create_product(
    session: Annotated[AsyncSession, Depends(get_session)],
    name: Annotated[str, Form(min_length=1, max_length=200)],
    image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Form(max_length=100)] = None,
):
    name = name.strip()
    if not name:
        raise HTTPException(422, "name is empty")
    ext = EXTENSIONS.get(image.content_type or "")
    if ext is None:
        raise HTTPException(415, f"unsupported image type: {image.content_type}")

    if idempotency_key:
        existing = await session.scalar(select(Product).where(Product.idempotency_key == idempotency_key))
        if existing:
            return ProductOut.of(existing)

    data = await image.read(settings.max_image_bytes + 1)
    if len(data) > settings.max_image_bytes:
        raise HTTPException(413, "image too large")

    key = f"{uuid.uuid4().hex}.{ext}"
    await storage.put_image(key, data, image.content_type)

    # Гонка двух реплик с одним ключом решается уникальным индексом: проигравший
    # получает DO NOTHING и отдаёт запись победителя (его объект в S3 — сирота, не беда).
    stmt = (
        insert(Product)
        .values(name=name, image_key=key, idempotency_key=idempotency_key)
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(Product.id)
    )
    new_id = await session.scalar(stmt)
    await session.commit()
    if new_id is None:
        product = await session.scalar(select(Product).where(Product.idempotency_key == idempotency_key))
    else:
        product = await session.get(Product, new_id)
    return ProductOut.of(product)
