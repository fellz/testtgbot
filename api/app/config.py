from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://shop:shop@postgres:5432/shop"
    s3_endpoint: str = "minio:9000"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio-secret"
    s3_bucket: str = "products"
    s3_secure: bool = False
    # Картинки отдаются балансировщиком с того же домена: /media/<key> → minio/<bucket>/<key>.
    media_public_url: str = "/media"
    # Создавать товары может только бот (и другие внутренние сервисы) — по общему токену.
    internal_token: str = "change-me"
    max_image_bytes: int = 10 * 1024 * 1024


settings = Settings()
