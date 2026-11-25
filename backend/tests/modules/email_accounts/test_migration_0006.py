"""Ce que la migration 0006 garantit, vérifié dans la base.

Ces tests n'empruntent aucun modèle : ils interrogent le schéma directement.
Une contrainte oubliée dans la migration ne serait pas rattrapée par
l'application, puisque c'est la base qui doit l'imposer — et c'est elle, et non
le service, qui empêche deux comptes par défaut.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

TABLES = ("email_accounts", "email_account_credentials", "email_account_checks")

INSERTION_COMPTE = text(
    """
    INSERT INTO email_accounts (label, host, port, security, username, from_email, is_default)
    VALUES (:label, 'smtp.ionos.fr', :port, :security, :username, :username, :defaut)
    RETURNING id_email_accounts
    """
)


async def creer_compte(
    session: AsyncSession,
    username: str,
    *,
    port: int = 465,
    security: str = "ssl_tls",
    defaut: bool = False,
) -> int:
    resultat = await session.execute(
        INSERTION_COMPTE,
        {
            "label": f"Compte {username}",
            "port": port,
            "security": security,
            "username": username,
            "defaut": defaut,
        },
    )
    return int(resultat.scalar_one())


class TestSchema:
    async def test_les_trois_tables_existent(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ANY(:tables)
                """
            ),
            {"tables": list(TABLES)},
        )
        assert sorted(resultat.scalars().all()) == sorted(TABLES)

    async def test_les_trois_tables_sont_commentees(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                """
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                  AND c.relname = ANY(:tables)
                  AND obj_description(c.oid) IS NULL
                """
            ),
            {"tables": list(TABLES)},
        )
        assert resultat.scalars().all() == []

    async def test_chaque_colonne_porte_son_commentaire(self, session: AsyncSession) -> None:
        """Aucune colonne sans commentaire, y compris les colonnes communes.

        Le dictionnaire `IAdocs/base-de-donnees.md` est produit depuis ces
        commentaires : une colonne oubliée y apparaît avec une description
        vide, et ça se voit.
        """
        resultat = await session.execute(
            text(
                """
                SELECT c.table_name || '.' || c.column_name
                FROM information_schema.columns c
                JOIN pg_class t ON t.relname = c.table_name
                JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = 'public'
                WHERE c.table_schema = 'public'
                  AND c.table_name = ANY(:tables)
                  AND col_description(t.oid, c.ordinal_position) IS NULL
                ORDER BY 1
                """
            ),
            {"tables": list(TABLES)},
        )
        assert resultat.scalars().all() == []

    async def test_le_declencheur_updated_at_existe(self, session: AsyncSession) -> None:
        """Sans lui, une modification faite directement en base laisserait
        updated_at figé à la date de création."""
        resultat = await session.execute(
            text(
                """
                SELECT event_object_table FROM information_schema.triggers
                WHERE trigger_name = 'trg_email_accounts_updated_at'
                """
            )
        )
        assert set(resultat.scalars().all()) == {"email_accounts"}

    async def test_le_droit_du_module_est_seme(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text("SELECT code FROM permissions WHERE sort_order BETWEEN 700 AND 799")
        )
        assert resultat.scalars().all() == ["manage_email_accounts"]


class TestContraintes:
    async def test_un_mode_de_chiffrement_inconnu_est_refuse(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await creer_compte(session, "mode@essai.fr", security="aucun")
        await session.rollback()

    async def test_un_port_hors_bornes_est_refuse(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await creer_compte(session, "port@essai.fr", port=70000)
        await session.rollback()

    async def test_deux_comptes_par_defaut_sont_refuses_par_la_base(
        self, session: AsyncSession
    ) -> None:
        """C'est l'index unique partiel qui le tient, et non le service : une
        requête concurrente ne peut donc pas créer un second expéditeur."""
        await creer_compte(session, "premier@essai.fr", defaut=True)
        with pytest.raises(IntegrityError):
            await creer_compte(session, "second@essai.fr", defaut=True)
        await session.rollback()

    async def test_le_meme_identifiant_actif_est_refuse_mais_pas_apres_archivage(
        self, session: AsyncSession
    ) -> None:
        id_compte = await creer_compte(session, "unique@essai.fr")
        with pytest.raises(IntegrityError):
            await creer_compte(session, "unique@essai.fr")
        await session.rollback()

        # Une fois le compte archivé, le même identifiant redevient libre.
        id_compte = await creer_compte(session, "unique@essai.fr")
        await session.execute(
            text("UPDATE email_accounts SET deleted_at = now() WHERE id_email_accounts = :id"),
            {"id": id_compte},
        )
        await creer_compte(session, "unique@essai.fr")

    async def test_un_seul_mot_de_passe_actif_par_compte(self, session: AsyncSession) -> None:
        id_compte = await creer_compte(session, "secrets@essai.fr")
        insertion = text(
            """
            INSERT INTO email_account_credentials
                (id_email_accounts, password_encrypted, password_masked)
            VALUES (:id, 'gAAAAA-chiffre', '••••••••')
            """
        )
        await session.execute(insertion, {"id": id_compte})
        with pytest.raises(IntegrityError):
            await session.execute(insertion, {"id": id_compte})
        await session.rollback()

    async def test_l_historique_des_verifications_est_en_ajout_seul(
        self, session: AsyncSession
    ) -> None:
        """UPDATE et DELETE sont retirés : une vérification passée ne se réécrit pas."""
        id_compte = await creer_compte(session, "historique@essai.fr")
        await session.execute(
            text(
                """
                INSERT INTO email_account_checks (id_email_accounts, kind, is_ok, message)
                VALUES (:id, 'connection', true, 'Connexion authentifiee.')
                """
            ),
            {"id": id_compte},
        )
        resultat = await session.execute(
            text(
                """
                SELECT privilege_type FROM information_schema.table_privileges
                WHERE table_name = 'email_account_checks' AND grantee = 'PUBLIC'
                  AND privilege_type IN ('UPDATE', 'DELETE')
                """
            )
        )
        assert resultat.scalars().all() == []

    async def test_une_nature_de_verification_inconnue_est_refusee(
        self, session: AsyncSession
    ) -> None:
        id_compte = await creer_compte(session, "nature@essai.fr")
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text(
                    """
                    INSERT INTO email_account_checks (id_email_accounts, kind, is_ok)
                    VALUES (:id, 'autre_chose', true)
                    """
                ),
                {"id": id_compte},
            )
        await session.rollback()
