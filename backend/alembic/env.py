"""Configuration d'exécution d'Alembic.

L'URL de la base vient des réglages de l'application, jamais d'alembic.ini :
une seule source de vérité évite qu'une migration tourne sur la mauvaise base.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# --- Les modèles doivent être importés pour que leurs tables soient connues ---
# Une ligne par module, ajoutée au fur et à mesure. Sans cet import, Alembic ne
# voit pas la table et l'autogénération proposerait de la supprimer.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.media import models as media_models  # noqa: F401
from app.modules.platforms import models as platforms_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Les tests imposent l'URL de la base de test avant d'appeler Alembic. Sans ce
# garde-fou, une migration lancée par pytest tournerait sur la base de travail.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", str(get_settings().DATABASE_URL))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Produit le SQL sans se connecter, pour relecture."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Les commentaires de tables et de colonnes font partie du schéma.
        include_schemas=False,
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
