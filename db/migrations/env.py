"""Alembic environment for the warehouse database.

Migrations are plain SQL through op.execute (ARCHITECTURE.md section 2), so there
is no SQLAlchemy model metadata here and no autogenerate.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    # Tests set sqlalchemy.url to a throwaway database; normal runs use WAREHOUSE_URL.
    return config.get_main_option("sqlalchemy.url") or os.environ["WAREHOUSE_URL"]


def run_migrations() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
