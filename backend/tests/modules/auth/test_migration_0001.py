"""Ce que la migration 0001 garantit, vérifié dans la base.

Ces tests ne passent par aucun modèle : ils interrogent le schéma directement.
C'est voulu — ils vérifient la MIGRATION, pas le code qui s'en sert. Une
contrainte oubliée dans la migration ne serait pas rattrapée par l'application,
puisque c'est justement la base qui doit l'imposer.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

INSERTION_UTILISATEUR = text(
    """
    INSERT INTO users (email, password_hash, first_name, last_name)
    VALUES (:email, 'empreinte-de-test', 'Prenom', 'Nom')
    RETURNING id_users
    """
)


async def creer_utilisateur(session: AsyncSession, email: str) -> int:
    resultat = await session.execute(INSERTION_UTILISATEUR, {"email": email})
    return int(resultat.scalar_one())


class TestSchema:
    async def test_les_quatre_tables_existent(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('users', 'permissions',
                                     'user_permissions', 'refresh_tokens')
                """
            )
        )
        assert len(resultat.scalars().all()) == 4

    async def test_toutes_les_tables_sont_commentees(self, session: AsyncSession) -> None:
        """Le modèle de données exige un commentaire par table."""
        resultat = await session.execute(
            text(
                """
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                  AND c.relname <> 'alembic_version'
                  AND obj_description(c.oid) IS NULL
                """
            )
        )
        assert resultat.scalars().all() == []


class TestDroitsAmorces:
    """`permissions` est une table PARTAGÉE : chaque module y insère les siens.

    Les assertions sont donc bornées à la plage de CE module, 200 à 299. Une
    assertion sur le contenu entier de la table casserait à chaque module
    suivant, ce qui est arrivé le 19 novembre avec la migration 0002.
    """

    async def test_les_deux_droits_du_module_sont_presents(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                "SELECT code FROM permissions "
                "WHERE sort_order BETWEEN 200 AND 299 ORDER BY sort_order"
            )
        )
        assert resultat.scalars().all() == ["manage_users", "manage_permissions"]

    async def test_le_sort_order_suit_la_convention(self, session: AsyncSession) -> None:
        """Numero du module x 100, par pas de 10 : aucune collision possible
        avec les droits qu'inséreront les modules suivants."""
        resultat = await session.execute(
            text(
                "SELECT sort_order FROM permissions "
                "WHERE sort_order BETWEEN 200 AND 299 ORDER BY sort_order"
            )
        )
        assert resultat.scalars().all() == [200, 210]

    async def test_chaque_droit_porte_une_description(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text("SELECT count(*) FROM permissions WHERE description IS NULL")
        )
        assert resultat.scalar_one() == 0


class TestUniciteDeLEmail:
    async def test_l_email_est_unique_a_la_casse_pres(self, session: AsyncSession) -> None:
        """Sans index sur lower(email), deux comptes existeraient pour la même
        personne, et elle ne se connecterait qu'une fois sur deux."""
        await creer_utilisateur(session, "balita@iagora.example.com")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await creer_utilisateur(session, "Balita@IAGORA.EXAMPLE.COM")

    async def test_un_compte_archive_libere_son_email(self, session: AsyncSession) -> None:
        """L'index est PARTIEL : sinon un départ interdirait définitivement de
        recréer un compte à la même adresse."""
        id_users = await creer_utilisateur(session, "repris@iagora.example.com")
        await session.execute(
            text("UPDATE users SET deleted_at = now() WHERE id_users = :i"), {"i": id_users}
        )
        nouveau = await creer_utilisateur(session, "repris@iagora.example.com")
        assert nouveau != id_users


class TestDeclencheurUpdatedAt:
    """Le declencheur existe parce que l'administrateur modifie certaines
    valeurs directement en base : l'application ne peut pas etre seule
    responsable d'updated_at.

    Attention a la facon de le tester. En PostgreSQL, `now()` renvoie l'heure
    de DEBUT DE TRANSACTION, constante jusqu'au commit : comparer updated_at
    avant et apres une modification faite dans la meme transaction ne montre
    aucun ecart, meme quand le declencheur fonctionne. On vieillit donc la
    colonne a la main avant de la modifier.
    """

    async def test_le_declencheur_rajeunit_une_valeur_vieillie(self, session: AsyncSession) -> None:
        id_users = await creer_utilisateur(session, "declencheur@iagora.example.com")
        await session.execute(
            text("UPDATE users SET updated_at = '2020-01-01T00:00:00Z' WHERE id_users = :i"),
            {"i": id_users},
        )

        await session.execute(
            text("UPDATE users SET first_name = 'Change' WHERE id_users = :i"), {"i": id_users}
        )
        apres = (
            await session.execute(
                text("SELECT updated_at FROM users WHERE id_users = :i"), {"i": id_users}
            )
        ).scalar_one()
        assert apres.year > 2020

    async def test_le_declencheur_ignore_une_valeur_imposee(self, session: AsyncSession) -> None:
        """Ecrire updated_at a la main ne doit servir a rien : c'est ce qui rend
        la colonne digne de confiance, quelle que soit l'origine de l'ecriture.
        """
        id_users = await creer_utilisateur(session, "impose@iagora.example.com")
        await session.execute(
            text(
                "UPDATE users SET first_name = 'X', updated_at = '2019-06-01T00:00:00Z' "
                "WHERE id_users = :i"
            ),
            {"i": id_users},
        )
        valeur = (
            await session.execute(
                text("SELECT updated_at FROM users WHERE id_users = :i"), {"i": id_users}
            )
        ).scalar_one()
        assert valeur.year > 2019


class TestContraintesDesJetons:
    async def _inserer_jeton(self, session: AsyncSession, id_users: int, **extra: object) -> None:
        colonnes = {
            "id_users": id_users,
            "token_hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "family_id": uuid.uuid4(),
            "revoked_at": None,
            "revoked_reason": None,
        }
        colonnes.update(extra)
        await session.execute(
            text(
                """
                INSERT INTO refresh_tokens
                    (id_users, token_hash, family_id, expires_at,
                     revoked_at, revoked_reason)
                VALUES
                    (:id_users, :token_hash, :family_id, now() + interval '7 days',
                     :revoked_at, :revoked_reason)
                """
            ),
            colonnes,
        )

    async def test_un_jeton_valide_s_insere(self, session: AsyncSession) -> None:
        id_users = await creer_utilisateur(session, "jeton@iagora.example.com")
        await self._inserer_jeton(session, id_users)

    async def test_une_raison_de_revocation_inconnue_est_refusee(
        self, session: AsyncSession
    ) -> None:
        id_users = await creer_utilisateur(session, "raison@iagora.example.com")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await self._inserer_jeton(
                    session, id_users, revoked_at=datetime.now(UTC), revoked_reason="inventee"
                )

    async def test_une_revocation_sans_raison_est_refusee(self, session: AsyncSession) -> None:
        """Une ligne révoquée sans raison serait impossible à interpréter le jour
        où quelqu'un demande pourquoi il a été déconnecté."""
        id_users = await creer_utilisateur(session, "sansraison@iagora.example.com")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await session.execute(
                    text(
                        """
                        INSERT INTO refresh_tokens
                            (id_users, token_hash, family_id, expires_at, revoked_at)
                        VALUES (:i, :h, :f, now() + interval '7 days', now())
                        """
                    ),
                    {"i": id_users, "h": uuid.uuid4().hex * 2, "f": uuid.uuid4()},
                )

    async def test_une_raison_sans_revocation_est_refusee(self, session: AsyncSession) -> None:
        id_users = await creer_utilisateur(session, "inverse@iagora.example.com")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await self._inserer_jeton(session, id_users, revoked_reason="logout")


class TestAttributionDesDroits:
    async def _attribuer(self, session: AsyncSession, id_users: int, code: str) -> None:
        await session.execute(
            text(
                """
                INSERT INTO user_permissions (id_users, id_permissions)
                SELECT :i, id_permissions FROM permissions WHERE code = :c
                """
            ),
            {"i": id_users, "c": code},
        )

    async def test_un_droit_ne_peut_etre_attribue_deux_fois(self, session: AsyncSession) -> None:
        id_users = await creer_utilisateur(session, "doublon@iagora.example.com")
        await self._attribuer(session, id_users, "manage_users")
        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                await self._attribuer(session, id_users, "manage_users")

    async def test_un_droit_revoque_peut_etre_reattribue(self, session: AsyncSession) -> None:
        """L'unicité est partielle : réattribuer crée une NOUVELLE ligne, et
        l'historique garde la trace du droit passé."""
        id_users = await creer_utilisateur(session, "reattribue@iagora.example.com")
        await self._attribuer(session, id_users, "manage_users")
        await session.execute(
            text("UPDATE user_permissions SET deleted_at = now() WHERE id_users = :i"),
            {"i": id_users},
        )
        await self._attribuer(session, id_users, "manage_users")

        total = (
            await session.execute(
                text("SELECT count(*) FROM user_permissions WHERE id_users = :i"), {"i": id_users}
            )
        ).scalar_one()
        assert total == 2, "l'historique doit conserver l'attribution révoquée"
