"""Tests du module Comptes d'envoi : chiffrement, rotation, défaut, vérifications.

Aucun test n'ouvre de connexion SMTP réelle : `smtp_client` est substitué. Ce
qui est vérifié ici, c'est ce que le module écrit en base et ce qu'il renvoie —
pas le dialogue avec IONOS, qui ne dépend pas de nous.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token
from app.modules.email_accounts.constants import MANAGE_EMAIL_ACCOUNTS
from app.modules.email_accounts.models import EmailAccount, EmailAccountCredential
from app.modules.email_accounts.schemas import EmailAccountTestMessage
from app.modules.email_accounts.service import _message_de_test
from app.modules.email_accounts.smtp_client import SmtpResult
from tests.conftest import entete

pytestmark = pytest.mark.asyncio

MOT_DE_PASSE_IONOS = "Secret-Boite-IONOS-2026"

CONNEXION_OK = SmtpResult(
    ok=True, message="Connexion authentifiée sur smtp.ionos.fr:465 (SSL/TLS).", latency_ms=142
)
CONNEXION_REFUSEE = SmtpResult(
    ok=False, message="Le serveur a refusé l'identifiant ou le mot de passe.", latency_ms=95
)


def compte_a_creer(**surcharges: object) -> dict[str, object]:
    """Corps de création, aux valeurs IONOS par défaut."""
    corps: dict[str, object] = {
        "label": "Datum Academy — contact",
        "username": "Contact@datum-academy.FR",
        "password": MOT_DE_PASSE_IONOS,
        "from_email": "Contact@datum-academy.FR",
        "from_name": "Datum Academy",
    }
    corps.update(surcharges)
    return corps


def _verification(resultat: SmtpResult) -> object:
    return patch(
        "app.modules.email_accounts.smtp_client.verify_connection",
        new=AsyncMock(return_value=resultat),
    )


def _envoi(resultat: SmtpResult) -> object:
    return patch(
        "app.modules.email_accounts.smtp_client.send_message",
        new=AsyncMock(return_value=resultat),
    )


class TestEnregistrement:
    async def test_creation_chiffre_le_mot_de_passe_et_ne_le_renvoie_jamais(
        self,
        client: AsyncClient,
        session: AsyncSession,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Le mot de passe est stocké chiffré par Fernet et ne sort dans aucune réponse."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            reponse = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )

        assert reponse.status_code == 201, reponse.text
        corps = reponse.json()
        assert corps["verified"] is True
        assert corps["latency_ms"] == 142
        assert MOT_DE_PASSE_IONOS not in reponse.text

        compte = corps["account"]
        assert compte["host"] == "smtp.ionos.fr"
        assert compte["port"] == 465
        assert compte["security"] == "ssl_tls"
        # Identifiant et adresses sont rangés en minuscules, comme users.email.
        assert compte["username"] == "contact@datum-academy.fr"
        assert compte["from_email"] == "contact@datum-academy.fr"
        assert compte["has_password"] is True
        assert compte["password_masked"] == "••••••••"
        # Premier compte enregistré : il devient l'expéditeur sans qu'on le demande.
        assert compte["is_default"] is True
        assert compte["last_verify_ok"] is True

        identifiants = (
            (
                await session.execute(
                    select(EmailAccountCredential).where(
                        EmailAccountCredential.id_email_accounts == compte["id_email_accounts"]
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(identifiants) == 1
        assert MOT_DE_PASSE_IONOS not in identifiants[0].password_encrypted
        assert decrypt_token(identifiants[0].password_encrypted) == MOT_DE_PASSE_IONOS

    async def test_le_meme_identifiant_sur_le_meme_serveur_est_refuse(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            premier = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
            assert premier.status_code == 201, premier.text
            second = await client.post(
                "/api/v1/email-accounts",
                headers=entete(jetons),
                json=compte_a_creer(label="Doublon"),
            )

        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "conflict"

    async def test_sans_le_droit_la_creation_est_refusee_mais_la_lecture_reste_permise(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """La boîte d'envois doit pouvoir afficher l'expéditeur sans droit d'administration."""
        simple = await fabrique_utilisateur()
        jetons = await connexion(simple.email)

        refus = await client.post(
            "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
        )
        assert refus.status_code == 403
        assert refus.json()["error"]["code"] == "permission_denied"

        lecture = await client.get("/api/v1/email-accounts", headers=entete(jetons))
        assert lecture.status_code == 200
        assert lecture.json() == []

    async def test_sans_jeton_la_lecture_est_refusee(self, client: AsyncClient) -> None:
        reponse = await client.get("/api/v1/email-accounts")
        assert reponse.status_code == 401


class TestMotDePasse:
    async def test_le_remplacement_cree_une_ligne_et_marque_la_precedente(
        self,
        client: AsyncClient,
        session: AsyncSession,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """L'historique est en ajout seul : l'ancien mot de passe est daté, pas écrasé."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)
        nouveau = "Nouveau-Secret-IONOS-2027"

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
            id_compte = creation.json()["account"]["id_email_accounts"]
            rotation = await client.post(
                f"/api/v1/email-accounts/{id_compte}/password",
                headers=entete(jetons),
                json={"password": nouveau},
            )

        assert rotation.status_code == 200, rotation.text
        assert nouveau not in rotation.text

        lignes = (
            (
                await session.execute(
                    select(EmailAccountCredential)
                    .where(EmailAccountCredential.id_email_accounts == id_compte)
                    .order_by(EmailAccountCredential.id_email_account_credentials)
                )
            )
            .scalars()
            .all()
        )
        assert len(lignes) == 2
        assert lignes[0].superseded_at is not None
        assert lignes[1].superseded_at is None
        assert decrypt_token(lignes[0].password_encrypted) == MOT_DE_PASSE_IONOS
        assert decrypt_token(lignes[1].password_encrypted) == nouveau

    async def test_tester_un_compte_sans_mot_de_passe_actif_est_refuse(
        self,
        client: AsyncClient,
        session: AsyncSession,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]

        # Le mot de passe est retiré sans remplacement : le compte ne peut plus rien envoyer.
        await session.execute(
            text(
                "UPDATE email_account_credentials SET revoked_at = now() "
                "WHERE id_email_accounts = :id"
            ),
            {"id": id_compte},
        )
        await session.flush()

        reponse = await client.post(
            f"/api/v1/email-accounts/{id_compte}/verify", headers=entete(jetons)
        )
        assert reponse.status_code == 409, reponse.text
        assert reponse.json()["error"]["code"] == "email_account_without_password"


class TestCompteParDefaut:
    async def test_un_seul_compte_par_defaut_a_la_fois(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            premier = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
            second = await client.post(
                "/api/v1/email-accounts",
                headers=entete(jetons),
                json=compte_a_creer(
                    label="Datum Academy — information",
                    username="info@datum-academy.fr",
                    from_email="info@datum-academy.fr",
                    is_default=True,
                ),
            )

        assert premier.status_code == 201, premier.text
        assert second.status_code == 201, second.text
        id_second = second.json()["account"]["id_email_accounts"]
        assert second.json()["account"]["is_default"] is True

        liste = await client.get("/api/v1/email-accounts", headers=entete(jetons))
        defauts = [compte for compte in liste.json() if compte["is_default"]]
        assert len(defauts) == 1
        assert defauts[0]["id_email_accounts"] == id_second
        # Le compte par défaut est en tête de liste.
        assert liste.json()[0]["id_email_accounts"] == id_second

        actif = await client.get("/api/v1/email-accounts/default", headers=entete(jetons))
        assert actif.json()["id_email_accounts"] == id_second

    async def test_archiver_revoque_le_mot_de_passe_et_libere_le_defaut(
        self,
        client: AsyncClient,
        session: AsyncSession,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Un compte archivé ne doit pas laisser un secret utilisable en base."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]

        archivage = await client.delete(
            f"/api/v1/email-accounts/{id_compte}", headers=entete(jetons)
        )
        assert archivage.status_code == 204

        assert (await client.get("/api/v1/email-accounts", headers=entete(jetons))).json() == []
        assert (
            await client.get("/api/v1/email-accounts/default", headers=entete(jetons))
        ).json() is None
        assert (
            await client.get(f"/api/v1/email-accounts/{id_compte}", headers=entete(jetons))
        ).status_code == 404

        lignes = (
            (
                await session.execute(
                    select(EmailAccountCredential).where(
                        EmailAccountCredential.id_email_accounts == id_compte
                    )
                )
            )
            .scalars()
            .all()
        )
        assert all(ligne.revoked_at is not None for ligne in lignes)


class TestVerifications:
    async def test_un_mot_de_passe_refuse_est_un_resultat_pas_une_erreur(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """IONOS qui refuse l'authentification se lit dans la réponse, en 200."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]

        with _verification(CONNEXION_REFUSEE):
            essai = await client.post(
                f"/api/v1/email-accounts/{id_compte}/verify", headers=entete(jetons)
            )

        assert essai.status_code == 200, essai.text
        assert essai.json()["verified"] is False
        assert "refusé" in essai.json()["message"]
        assert essai.json()["account"]["last_verify_ok"] is False

        historique = await client.get(
            f"/api/v1/email-accounts/{id_compte}/checks", headers=entete(jetons)
        )
        lignes = historique.json()
        # Création puis essai : deux lignes, la plus récente en tête.
        assert [ligne["is_ok"] for ligne in lignes] == [False, True]
        assert lignes[0]["kind"] == "connection"
        assert lignes[0]["checked_by_name"] == f"{admin.first_name} {admin.last_name}"

    async def test_le_message_de_test_consigne_son_destinataire(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]

        with _envoi(
            SmtpResult(ok=True, message="Le serveur a accepté le message.", latency_ms=310)
        ):
            envoi = await client.post(
                f"/api/v1/email-accounts/{id_compte}/test-message",
                headers=entete(jetons),
                json={"recipient_email": "Essai@datum-academy.FR"},
            )

        assert envoi.status_code == 200, envoi.text
        assert envoi.json()["verified"] is True

        historique = await client.get(
            f"/api/v1/email-accounts/{id_compte}/checks", headers=entete(jetons)
        )
        dernier = historique.json()[0]
        assert dernier["kind"] == "test_message"
        assert dernier["recipient_email"] == "essai@datum-academy.fr"
        assert dernier["latency_ms"] == 310

    async def test_changer_de_serveur_annule_la_derniere_verification(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Un feu vert obtenu sur l'ancien serveur ne dit rien du nouveau."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]
        assert creation.json()["account"]["last_verify_ok"] is True

        modification = await client.patch(
            f"/api/v1/email-accounts/{id_compte}",
            headers=entete(jetons),
            json={"port": 587, "security": "starttls"},
        )
        assert modification.status_code == 200, modification.text
        corps = modification.json()
        assert corps["port"] == 587
        assert corps["security"] == "starttls"
        assert corps["last_verify_ok"] is None
        assert corps["last_verified_at"] is None


class TestCorrectionsDeRelecture:
    """Les cas relevés en relecture : chacun aurait dû être couvert d'emblée."""

    async def test_renommer_un_compte_vers_un_identifiant_pris_renvoie_409(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Le conflit doit sortir en 409, et non en 500.

        Le compte porte déjà ses nouvelles valeurs en mémoire quand le contrôle
        s'exécute : sans `no_autoflush`, la requête de contrôle les écrirait en
        base d'abord, et l'index unique les refuserait avant qu'on ait pu lever
        l'erreur métier.
        """
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            premier = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
            second = await client.post(
                "/api/v1/email-accounts",
                headers=entete(jetons),
                json=compte_a_creer(
                    label="Datum Academy — information",
                    username="info@datum-academy.fr",
                    from_email="info@datum-academy.fr",
                ),
            )
        assert premier.status_code == 201, premier.text
        id_second = second.json()["account"]["id_email_accounts"]

        collision = await client.patch(
            f"/api/v1/email-accounts/{id_second}",
            headers=entete(jetons),
            json={"username": "contact@datum-academy.fr"},
        )
        assert collision.status_code == 409, collision.text
        assert collision.json()["error"]["code"] == "conflict"

    async def test_changer_le_mot_de_passe_sans_test_annule_la_verification(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Un feu vert obtenu avec l'ancien mot de passe ne vaut pas pour le nouveau."""
        admin = await fabrique_utilisateur(droits=[MANAGE_EMAIL_ACCOUNTS])
        jetons = await connexion(admin.email)

        with _verification(CONNEXION_OK):
            creation = await client.post(
                "/api/v1/email-accounts", headers=entete(jetons), json=compte_a_creer()
            )
        id_compte = creation.json()["account"]["id_email_accounts"]
        assert creation.json()["account"]["last_verify_ok"] is True

        rotation = await client.post(
            f"/api/v1/email-accounts/{id_compte}/password",
            headers=entete(jetons),
            json={"password": "Autre-Secret-IONOS-2027", "verify_immediately": False},
        )
        assert rotation.status_code == 200, rotation.text
        compte = rotation.json()["account"]
        assert rotation.json()["verified"] is False
        assert compte["last_verify_ok"] is None
        assert compte["last_verified_at"] is None
        assert compte["last_verify_message"] is None

    async def test_un_nom_affiche_avec_virgule_ne_casse_pas_l_expediteur(self) -> None:
        """« Datum Academy, SARL » ne doit pas devenir deux adresses.

        aiosmtplib tire l'expéditeur de l'enveloppe de cet en-tête : une virgule
        laissée nue y ferait passer la fin du nom pour un second destinataire.
        """
        compte = EmailAccount(
            label="Essai",
            host="smtp.ionos.fr",
            port=465,
            security="ssl_tls",
            username="contact@datum-academy.fr",
            from_email="contact@datum-academy.fr",
            from_name="Datum Academy, SARL",
            reply_to_email=None,
            timeout_seconds=20,
        )
        message = _message_de_test(
            compte, EmailAccountTestMessage(recipient_email="essai@datum-academy.fr")
        )
        expediteurs = message["From"].addresses
        assert len(expediteurs) == 1
        assert expediteurs[0].addr_spec == "contact@datum-academy.fr"
        assert expediteurs[0].display_name == "Datum Academy, SARL"
        assert '"Datum Academy, SARL"' in str(message["From"])
