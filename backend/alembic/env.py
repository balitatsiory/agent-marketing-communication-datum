"""Configuration d'Alembic.

L'URL de la base vient des réglages de l'application, pas d'alembic.ini : il n'y a
donc aucun secret dans un fichier versionné.

Tous les modèles sont importés ici : Alembic compare les tables déclarées à celles
qui existent en base. Un modèle non importé serait invisible, et sa table jamais créée.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# Import des modèles — l'ordre n'a pas d'importance.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.social_accounts import models as social_accounts_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return str(get_settings().DATABASE_URL)


def run_migrations_offline() -> None:
    """Génère le SQL sans se connecter (alembic upgrade --sql)."""
    context.configure(
        url=_url(),
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
        compare_type=True,  # détecte aussi les changements de type de colonne
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Applique les migrations sur la base."""
    engine = create_async_engine(_url(), poolclass=None)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
