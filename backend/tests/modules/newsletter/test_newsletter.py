"""Tests du module Newsletter : modèles de mail, rendu et envois.

Aucun test n'ouvre de connexion SMTP : le lot d'envoi est substitué. Ce qui est
vérifié ici, c'est ce que le module écrit en base et ce qu'il compose — pas le
dialogue avec IONOS, qui ne dépend pas de nous.
"""

import re
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_accounts.constants import MANAGE_EMAIL_ACCOUNTS
from app.modules.email_accounts.smtp_client import SmtpResult
from app.modules.newsletter import renderer
from app.modules.newsletter.constants import (
    MANAGE_MAIL_TEMPLATES,
    MODELES_STANDARDS,
    SEND_NEWSLETTERS,
    VALEURS_EXEMPLE,
)
from tests.conftest import entete

pytestmark = pytest.mark.asyncio

ACCEPTE = SmtpResult(ok=True, message="Le serveur a accepté le message.", latency_ms=120)
REFUSE = SmtpResult(ok=False, message="Adresse inconnue chez le destinataire.", latency_ms=80)


async def compte_d_envoi(client: AsyncClient, jetons: dict[str, str]) -> int:
    """Crée un compte d'envoi actif, sans toucher au réseau."""
    with patch(
        "app.modules.email_accounts.smtp_client.verify_connection",
        new=AsyncMock(
            return_value=SmtpResult(ok=True, message="Connexion authentifiée.", latency_ms=90)
        ),
    ):
        reponse = await client.post(
            "/api/v1/email-accounts",
            headers=entete(jetons),
            json={
                "label": "Datum Academy — contact",
                "username": "contact@iagora.example.com",
                "password": "Secret-Boite-IONOS-2026",
                "from_email": "contact@iagora.example.com",
                "from_name": "Datum Academy",
            },
        )
    assert reponse.status_code == 201, reponse.text
    return int(reponse.json()["account"]["id_email_accounts"])


class TestRendu:
    async def test_les_cinq_modeles_standards_se_rendent_sans_trou(self) -> None:
        """Chaque corps livré doit s'assembler avec la coquille, sans variable oubliée."""
        for standard in MODELES_STANDARDS:
            corps = renderer.corps_standard(standard["fichier"])
            rendu = renderer.rendre_html(
                corps, standard["subject"], standard["preheader"], VALEURS_EXEMPLE
            )
            restantes = re.findall(r"\{\{\s*([a-z0-9_]+)\s*\}\}", rendu)
            # `lien_desinscription` vit dans le pied légal, resté en commentaire
            # tant que ces courriels sont transactionnels.
            assert restantes == ["lien_desinscription"], standard["fichier"]
            assert "Datum Academy" in rendu
            assert "logo-datum-blanc" in rendu

    async def test_une_valeur_ne_peut_pas_injecter_de_html(self) -> None:
        """Un titre qui referme une balise casserait la mise en page de tous."""
        rendu = renderer.rendre_html(
            "<tr><td>{{titre_webinaire}}</td></tr>",
            "Objet",
            None,
            {"titre_webinaire": '</td></tr><script>alert("x")</script>'},
        )
        assert "<script>" not in rendu
        assert "&lt;script&gt;" in rendu

    async def test_une_variable_sans_valeur_reste_visible(self) -> None:
        """Un trou béant se voit ; une chaîne vide ne se voit pas."""
        rendu = renderer.rendre_html("<tr><td>{{inconnue}}</td></tr>", "Objet", None, {})
        assert "{{inconnue}}" in rendu

    async def test_la_version_texte_garde_les_liens(self) -> None:
        texte = renderer.rendre_texte(
            '<p><a href="https://example.com/acces">Rejoindre la séance</a></p>'
        )
        assert "Rejoindre la séance (https://example.com/acces)" in texte


class TestModeles:
    async def test_installer_les_standards_est_sans_effet_la_seconde_fois(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Un modèle standard modifié depuis ne doit pas être réécrit."""
        admin = await fabrique_utilisateur(droits=[MANAGE_MAIL_TEMPLATES])
        jetons = await connexion(admin.email)

        premiere = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )
        assert premiere.status_code == 200, premiere.text
        assert len(premiere.json()) == len(MODELES_STANDARDS)

        seconde = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )
        assert seconde.json() == []

        liste = await client.get("/api/v1/newsletter/mail-templates", headers=entete(jetons))
        assert liste.json()["total"] == len(MODELES_STANDARDS)
        premier = liste.json()["items"][0]
        assert premier["category_code"] == "registration_confirmation"
        assert premier["status"] == "published"
        assert "titre_webinaire" in premier["variables"]

    async def test_modifier_le_corps_depose_l_etat_precedent_en_version(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_MAIL_TEMPLATES])
        jetons = await connexion(admin.email)

        creation = await client.post(
            "/api/v1/newsletter/mail-templates",
            headers=entete(jetons),
            json={
                "category_code": "reminder",
                "name": "Rappel maison",
                "subject": "Demain : {{titre_webinaire}}",
                "body_html": "<tr><td>Bonjour {{prenom}}</td></tr>",
                "status": "draft",
            },
        )
        assert creation.status_code == 201, creation.text
        id_modele = creation.json()["id_mail_templates"]
        assert creation.json()["version_label"] == "v1"

        modification = await client.patch(
            f"/api/v1/newsletter/mail-templates/{id_modele}",
            headers=entete(jetons),
            json={
                "body_html": "<tr><td>Bonjour {{prenom}}, c'est {{echeance}}</td></tr>",
                "status": "published",
                "change_note": "Ajout de l'échéance.",
            },
        )
        assert modification.status_code == 200, modification.text
        assert modification.json()["version_label"] == "v2"
        # Les variables sont relues du corps : la nouvelle y figure.
        assert "echeance" in modification.json()["variables"]

        versions = await client.get(
            f"/api/v1/newsletter/mail-templates/{id_modele}/versions", headers=entete(jetons)
        )
        # Une ligne par version rendue vivante, la plus récente en tête.
        assert [version["label"] for version in versions.json()] == ["v2", "v1"]
        assert versions.json()[0]["change_note"] == "Ajout de l'échéance."
        assert versions.json()[0]["author_name"] == f"{admin.first_name} {admin.last_name}"

    async def test_un_nom_deja_pris_est_refuse(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_MAIL_TEMPLATES])
        jetons = await connexion(admin.email)
        corps = {
            "category_code": "report",
            "name": "Compte rendu maison",
            "subject": "Compte rendu",
            "body_html": "<tr><td>Merci</td></tr>",
        }
        premier = await client.post(
            "/api/v1/newsletter/mail-templates", headers=entete(jetons), json=corps
        )
        assert premier.status_code == 201
        second = await client.post(
            "/api/v1/newsletter/mail-templates", headers=entete(jetons), json=corps
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "conflict"

    async def test_sans_le_droit_la_creation_est_refusee(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        simple = await fabrique_utilisateur()
        jetons = await connexion(simple.email)
        refus = await client.post(
            "/api/v1/newsletter/mail-templates",
            headers=entete(jetons),
            json={
                "category_code": "reminder",
                "name": "Interdit",
                "subject": "Objet",
                "body_html": "<tr><td>x</td></tr>",
            },
        )
        assert refus.status_code == 403

    async def test_l_apercu_signale_les_variables_sans_valeur(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(droits=[MANAGE_MAIL_TEMPLATES])
        jetons = await connexion(admin.email)
        creation = await client.post(
            "/api/v1/newsletter/mail-templates",
            headers=entete(jetons),
            json={
                "category_code": "replay",
                "name": "Visionnage maison",
                "subject": "Rediffusion de {{titre_webinaire}}",
                "body_html": "<tr><td>{{prenom}} — {{code_promo}}</td></tr>",
                "status": "published",
            },
        )
        id_modele = creation.json()["id_mail_templates"]

        apercu = await client.post(
            f"/api/v1/newsletter/mail-templates/{id_modele}/preview",
            headers=entete(jetons),
            json={"variables": {"prenom": "Mialy"}},
        )
        assert apercu.status_code == 200, apercu.text
        corps = apercu.json()
        assert corps["missing_variables"] == ["code_promo"]
        assert "Mialy" in corps["html"]
        assert corps["subject"].startswith("Rediffusion de ")


class TestEnvois:
    async def test_un_envoi_ecrit_le_detail_et_en_deduit_ses_cumuls(
        self,
        client: AsyncClient,
        session: AsyncSession,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Deux acceptés, un refusé : l'envoi est « envoyé en partie »."""
        admin = await fabrique_utilisateur(
            droits=[MANAGE_EMAIL_ACCOUNTS, MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS]
        )
        jetons = await connexion(admin.email)
        id_compte = await compte_d_envoi(client, jetons)
        standards = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )
        id_modele = standards.json()[0]["id_mail_templates"]

        with patch(
            "app.modules.email_accounts.smtp_client.send_messages",
            new=AsyncMock(return_value=[ACCEPTE, REFUSE, ACCEPTE]),
        ):
            envoi = await client.post(
                "/api/v1/newsletter/sends",
                headers=entete(jetons),
                json={
                    "id_mail_templates": id_modele,
                    "id_email_accounts": id_compte,
                    "event_title": "Webinaire de décembre",
                    "recipients": [
                        {"email": "Alice@iagora.example.com", "display_name": "Alice Rakoto"},
                        {"email": "bob@iagora.example.com"},
                        {"email": "carla@iagora.example.com", "display_name": "Carla"},
                    ],
                    "variables": {"titre_webinaire": "Piloter sa donnée"},
                },
            )

        assert envoi.status_code == 201, envoi.text
        corps = envoi.json()
        assert corps["status_code"] == "partial"
        assert corps["recipient_count"] == 3
        assert corps["delivered_count"] == 2
        assert corps["bounce_count"] == 1
        assert corps["delivery_rate"] == 67
        assert corps["failure_note"] == REFUSE.message
        assert corps["template_version"] == "v1"
        assert corps["account_label"] == "Datum Academy — contact"

        adresses = {ligne["email"]: ligne for ligne in corps["recipients"]}
        # Les adresses sont rangées en minuscules, comme partout ailleurs.
        assert "alice@iagora.example.com" in adresses
        assert adresses["bob@iagora.example.com"]["is_delivered"] is False
        assert adresses["bob@iagora.example.com"]["error_message"] == REFUSE.message

        total = (
            await session.execute(text("SELECT count(*) FROM newsletter_send_recipients"))
        ).scalar_one()
        assert total == 3

    async def test_le_prenom_est_celui_de_chaque_destinataire(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Un envoi en copie cachée dirait le même « Bonjour » à tout le monde."""
        admin = await fabrique_utilisateur(
            droits=[MANAGE_EMAIL_ACCOUNTS, MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS]
        )
        jetons = await connexion(admin.email)
        id_compte = await compte_d_envoi(client, jetons)
        standards = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )
        id_modele = standards.json()[0]["id_mail_templates"]

        envoye = AsyncMock(return_value=[ACCEPTE, ACCEPTE])
        with patch("app.modules.email_accounts.smtp_client.send_messages", new=envoye):
            await client.post(
                "/api/v1/newsletter/sends",
                headers=entete(jetons),
                json={
                    "id_mail_templates": id_modele,
                    "id_email_accounts": id_compte,
                    "recipients": [
                        {"email": "alice@iagora.example.com", "display_name": "Alice Rakoto"},
                        {"email": "bob@iagora.example.com", "display_name": "Bob Andria"},
                    ],
                },
            )

        messages = envoye.await_args.args[1]
        assert len(messages) == 2
        premier = messages[0].get_body(preferencelist=("html",)).get_content()
        second = messages[1].get_body(preferencelist=("html",)).get_content()
        # Le prénom est le PREMIER mot du nom saisi.
        assert "Bienvenue Alice," in premier
        assert "Bienvenue Bob," in second
        # Chaque message ne porte qu'un destinataire.
        assert messages[0]["To"].addresses[0].addr_spec == "alice@iagora.example.com"
        assert len(messages[0]["To"].addresses) == 1
        # Le repli texte vient en premier, le HTML en second.
        assert messages[0].get_body(preferencelist=("plain",)) is not None

    async def test_un_brouillon_ne_part_pas(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(
            droits=[MANAGE_EMAIL_ACCOUNTS, MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS]
        )
        jetons = await connexion(admin.email)
        id_compte = await compte_d_envoi(client, jetons)
        creation = await client.post(
            "/api/v1/newsletter/mail-templates",
            headers=entete(jetons),
            json={
                "category_code": "reminder",
                "name": "Brouillon maison",
                "subject": "Objet",
                "body_html": "<tr><td>x</td></tr>",
                "status": "draft",
            },
        )
        refus = await client.post(
            "/api/v1/newsletter/sends",
            headers=entete(jetons),
            json={
                "id_mail_templates": creation.json()["id_mail_templates"],
                "id_email_accounts": id_compte,
                "recipients": [{"email": "alice@iagora.example.com"}],
            },
        )
        assert refus.status_code == 409
        assert refus.json()["error"]["code"] == "mail_template_not_published"

    async def test_les_statistiques_ignorent_les_envois_non_tentes(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        """Le taux de remise ne porte que sur ce qui est réellement parti."""
        admin = await fabrique_utilisateur(
            droits=[MANAGE_EMAIL_ACCOUNTS, MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS]
        )
        jetons = await connexion(admin.email)
        id_compte = await compte_d_envoi(client, jetons)
        standards = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )
        id_modele = standards.json()[0]["id_mail_templates"]

        with patch(
            "app.modules.email_accounts.smtp_client.send_messages",
            new=AsyncMock(return_value=[ACCEPTE, REFUSE]),
        ):
            await client.post(
                "/api/v1/newsletter/sends",
                headers=entete(jetons),
                json={
                    "id_mail_templates": id_modele,
                    "id_email_accounts": id_compte,
                    "recipients": [
                        {"email": "alice@iagora.example.com"},
                        {"email": "bob@iagora.example.com"},
                    ],
                },
            )

        stats = await client.get("/api/v1/newsletter/sends/stats", headers=entete(jetons))
        assert stats.status_code == 200, stats.text
        corps = stats.json()
        assert corps["sends"] == 1
        assert corps["targeted"] == 2
        assert corps["delivered"] == 1
        assert corps["bounced"] == 1
        assert corps["delivery_rate"] == 50
        assert corps["needing_attention"] == 1
        assert {compte["code"] for compte in corps["by_status"]} == {"partial"}

        # Le même compte, filtré : mêmes chiffres. Un autre compte : rien.
        cible = await client.get(
            f"/api/v1/newsletter/sends/stats?id_email_accounts={id_compte}",
            headers=entete(jetons),
        )
        assert cible.json()["delivered"] == 1
        autre = await client.get(
            "/api/v1/newsletter/sends/stats?id_email_accounts=999999", headers=entete(jetons)
        )
        assert autre.json()["sends"] == 0

    async def test_la_liste_des_envois_est_paginee_et_filtrable(
        self,
        client: AsyncClient,
        fabrique_utilisateur,  # type: ignore[no-untyped-def]
        connexion,  # type: ignore[no-untyped-def]
    ) -> None:
        admin = await fabrique_utilisateur(
            droits=[MANAGE_EMAIL_ACCOUNTS, MANAGE_MAIL_TEMPLATES, SEND_NEWSLETTERS]
        )
        jetons = await connexion(admin.email)
        id_compte = await compte_d_envoi(client, jetons)
        standards = await client.post(
            "/api/v1/newsletter/mail-templates/install-standards", headers=entete(jetons)
        )

        with patch(
            "app.modules.email_accounts.smtp_client.send_messages",
            new=AsyncMock(return_value=[ACCEPTE]),
        ):
            for standard in standards.json()[:3]:
                await client.post(
                    "/api/v1/newsletter/sends",
                    headers=entete(jetons),
                    json={
                        "id_mail_templates": standard["id_mail_templates"],
                        "id_email_accounts": id_compte,
                        "recipients": [{"email": "alice@iagora.example.com"}],
                    },
                )

        page = await client.get("/api/v1/newsletter/sends?page=1&size=2", headers=entete(jetons))
        assert page.status_code == 200, page.text
        corps = page.json()
        assert corps["total"] == 3
        assert corps["pages"] == 2
        assert len(corps["items"]) == 2

        rappels = await client.get(
            "/api/v1/newsletter/sends?category_code=reminder", headers=entete(jetons)
        )
        assert rappels.json()["total"] == 1
        assert rappels.json()["items"][0]["category_code"] == "reminder"
