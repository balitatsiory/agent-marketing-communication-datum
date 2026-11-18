"""Outillage commun des tests.

Deux garanties, qui sont la condition pour que la validation module par module
reste fiable :

1. Les migrations tournent sur la base de TEST, jamais sur la base de travail.
2. Chaque test s'exécute dans une transaction ANNULÉE à la fin. Aucun test ne
   laisse de trace, et l'ordre d'exécution n'a donc aucune influence.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, select
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


# ---------------------------------------------------------------------------
# Fabriques pour les tests d'API
# ---------------------------------------------------------------------------
# Déclarées en fixtures plutôt qu'en module importable : avec
# --import-mode=importlib et sans __init__.py dans les dossiers de tests, une
# fixture est le moyen le plus simple de partager un outil entre fichiers.


@pytest.fixture
def fabrique_utilisateur(session: AsyncSession):  # type: ignore[no-untyped-def]
    """Crée un utilisateur en base, avec ses droits, son état et son mot de passe."""
    from app.core.security import hash_password
    from app.modules.users.models import Permission, User, UserPermission

    compteur = {"n": 0}

    async def fabriquer(
        mot_de_passe: str = "Dev-Mot-De-Passe-2026",
        droits: list[str] | None = None,
        is_active: bool = True,
        archive: bool = False,
        email: str | None = None,
    ) -> User:
        compteur["n"] += 1
        utilisateur = User(
            email=email or f"essai{compteur['n']}@iagora.example.com",
            password_hash=hash_password(mot_de_passe),
            first_name="Essai",
            last_name=f"Numero{compteur['n']}",
            is_active=is_active,
            deleted_at=datetime.now(UTC) if archive else None,
        )
        session.add(utilisateur)
        await session.flush()

        for code in droits or []:
            id_permissions = (
                await session.execute(
                    select(Permission.id_permissions).where(Permission.code == code)
                )
            ).scalar_one()
            session.add(
                UserPermission(id_users=utilisateur.id_users, id_permissions=id_permissions)
            )
        await session.flush()
        return utilisateur

    return fabriquer


@pytest.fixture
def connexion(client: AsyncClient):  # type: ignore[no-untyped-def]
    """Ouvre une session et renvoie le couple de jetons."""

    async def se_connecter(
        email: str, mot_de_passe: str = "Dev-Mot-De-Passe-2026"
    ) -> dict[str, str]:
        reponse = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": mot_de_passe}
        )
        assert reponse.status_code == 200, reponse.text
        return dict(reponse.json())

    return se_connecter


def entete(jetons: dict[str, str]) -> dict[str, str]:
    """En-tête d'autorisation à partir d'un couple de jetons."""
    return {"Authorization": f"Bearer {jetons['access_token']}"}
