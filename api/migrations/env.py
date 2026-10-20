import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, text

from app.db import Base, engine

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def run(connection: Connection) -> None:
    # Advisory-lock: если migrate всё же запустят параллельно, второй подождёт первого.
    connection.execute(text("select pg_advisory_lock(727001)"))
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    async with engine.connect() as conn:
        await conn.run_sync(run)
        await conn.commit()
    await engine.dispose()


asyncio.run(main())
