import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect them
from app.db.base import Base  # noqa: F401, E402
import app.db.models.user  # noqa: F401, E402
import app.db.models.candidate  # noqa: F401, E402
import app.db.models.job  # noqa: F401, E402
import app.db.models.match  # noqa: F401, E402
import app.db.models.cv_session  # noqa: F401, E402

target_metadata = Base.metadata

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url", ""),
)
# Alembic needs psycopg2/sync driver for offline; asyncpg for online
# We convert the async URL for offline SQL generation
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
else:
    sync_url = DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
