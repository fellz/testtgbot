import asyncio
import io
import json

from minio import Minio

from .config import settings

client = Minio(
    settings.s3_endpoint,
    access_key=settings.s3_access_key,
    secret_key=settings.s3_secret_key,
    secure=settings.s3_secure,
)


def public_url(key: str) -> str:
    return f"{settings.media_public_url}/{key}"


async def put_image(key: str, data: bytes, content_type: str) -> None:
    # SDK minio синхронный — уводим в поток, чтобы не блокировать event loop.
    await asyncio.to_thread(
        client.put_object, settings.s3_bucket, key, io.BytesIO(data), len(data), content_type=content_type
    )


def ensure_bucket() -> None:
    """Бакет с анонимным чтением объектов (каталог публичный). Идемпотентно."""
    if not client.bucket_exists(settings.s3_bucket):
        client.make_bucket(settings.s3_bucket)
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{settings.s3_bucket}/*"],
        }],
    }
    client.set_bucket_policy(settings.s3_bucket, json.dumps(policy))


def ping() -> None:
    client.bucket_exists(settings.s3_bucket)
