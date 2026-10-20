import aiohttp
from pydantic import BaseModel

from .config import settings


class ApiError(Exception):
    pass


class Product(BaseModel):
    id: int
    name: str
    image_url: str


async def create_product(name: str, image: bytes, idempotency_key: str) -> Product:
    form = aiohttp.FormData()
    form.add_field("name", name)
    form.add_field("idempotency_key", idempotency_key)
    form.add_field("image", image, filename="photo.jpg", content_type="image/jpeg")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        async with s.post(
            f"{settings.api_url}/products", data=form, headers={"X-Internal-Token": settings.internal_token}
        ) as r:
            if r.status >= 400:
                raise ApiError(f"{r.status}: {await r.text()}")
            return Product.model_validate(await r.json())
