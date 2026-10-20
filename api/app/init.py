"""Одноразовый шаг перед стартом реплик: миграции БД + бакет MinIO.

Запускается отдельным контейнером `migrate`, а не на старте каждой реплики API —
реплики не гоняются за схему. Повторный запуск безопасен.
"""
import time

from alembic import command
from alembic.config import Config

from . import storage


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    for attempt in range(30):
        try:
            storage.ensure_bucket()
            break
        except Exception as e:  # minio ещё стартует
            print(f"bucket not ready ({attempt + 1}/30): {e}", flush=True)
            time.sleep(1)
    else:
        raise SystemExit("minio unavailable")
    print("init done", flush=True)


if __name__ == "__main__":
    main()
