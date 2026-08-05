import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app import models  # noqa: F401
from app.config import get_settings
from app.database import Base

config=context.config
config.set_main_option("sqlalchemy.url",get_settings().database_url)
if config.config_file_name:fileConfig(config.config_file_name)
target_metadata=Base.metadata
def offline():
 context.configure(url=config.get_main_option("sqlalchemy.url"),target_metadata=target_metadata,literal_binds=True);context.run_migrations()
async def online_run():
    engine=async_engine_from_config(config.get_section(config.config_ini_section),prefix="sqlalchemy.")
    def run_migrations(connection):
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()
if context.is_offline_mode():offline()
else:asyncio.run(online_run())
