"""Outillage commun des tests.

Deux garanties, qui sont la condition pour que la validation module par module
reste fiable :

1. Les migrations tournent sur la base de TEST, jamais sur la base de travail.
2. Chaque test s'exécute dans une transaction ANNULÉE à la fin. Aucun test ne
   laisse de trace, et l'ordre d'exécution n'a donc aucune influence.
"""

from collections.abc import AsyncIterator

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.core.config import get_settings
from app.core.database import get_session
from app.main import create_app


def url_base_de_test() -> str:
    reglages = get_settings()
    if reglages.TEST_DATABASE_URL is None:
        pytest.skip("TEST_DATABASE_URL n'est pas renseignée dans le .env.")
    return str(reglages.TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def migrations() -> None:
    """Monte le schéma sur la base de test, une fois pour toute la session.

    Cette fonction est volontairement synchrone : `command.upgrade` ouvre sa
    propre boucle d'événements, ce qui échouerait si une boucle tournait déjà.
    """
    configuration = Config("alembic.ini")
    configuration.set_main_option("sqlalchemy.url", url_base_de_test())
    command.upgrade(configuration, "head")


@pytest.fixture
async def moteur_de_test() -> AsyncIterator[AsyncEngine]:
    """Moteur propre à chaque test.

    Il ne peut PAS être partagé par toute la session : pytest-asyncio ouvre une
    boucle d'événements par test, et une connexion gardée en réserve appartient à
    la boucle qui l'a ouverte. La réutiliser dans un autre test échoue sur
    « attached to a different loop ». NullPool supprime la réserve : chaque
    connexion naît et meurt dans la boucle du test.
    """
    moteur = create_async_engine(url_base_de_test(), poolclass=NullPool)
    yield moteur
    await moteur.dispose()


@pytest.fixture
async def session(moteur_de_test: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session liée à une transaction annulée à la fin du test."""
    async with moteur_de_test.connect() as connexion:
        transaction = await connexion.begin()
        fabrique = async_sessionmaker(bind=connexion, expire_on_commit=False)
        async with fabrique() as session_de_test:
            yield session_de_test
        await transaction.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Client HTTP branché sur l'application, avec la session de test."""
    application = create_app()

    async def session_de_test() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = session_de_test

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client_de_test:
        yield client_de_test

    application.dependency_overrides.clear()
