"""Accès à PostgreSQL : moteur, session par requête, classe de base des modèles.

La convention de nommage des contraintes est déclarée ici, une fois pour toutes :
sans elle, PostgreSQL invente des noms qui changent d'une base à l'autre, et les
migrations Alembic deviennent impossibles à écrire proprement.
"""

import logging
from collections.abc import AsyncIterator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# pk_publications · fk_publications_id_users_author_users · uq_users_email
# ix_publications_scheduled_at · ck_publications_status
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    """Classe de base de tous les modèles. Alembic s'appuie sur ses métadonnées."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


settings = get_settings()

engine = create_async_engine(
    str(settings.DATABASE_URL),
    # Vérifie que la connexion est vivante avant de la réutiliser : évite les erreurs
    # après une coupure réseau ou un redémarrage de la base.
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Ouvre une session pour la durée d'une requête.

    Une requête HTTP = une transaction : tout est validé à la fin, ou rien ne l'est.
    C'est ce qui garantit qu'un changement de statut et sa ligne d'historique sont
    écrits ensemble, ou pas du tout.
    """
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database() -> bool:
    """Indique si la base répond. Utilisé par /health."""
    try:
        async with engine.connect() as connexion:
            await connexion.execute(text("SELECT 1"))
    except Exception:
        logger.exception("La base de données ne répond pas")
        return False
    return True
