"""Dépôt, bibliothèque et médias de référence, de bout en bout.

Le stockage est un dossier jetable, substitué par `stockage_de_test` : la
suite ne touche ni au réseau ni à Cloudflare, et n'écrit rien dans le dépôt.
"""

import io

from httpx import AsyncClient
from PIL import Image

from app.core.storage import StockageLocal
from tests.conftest import entete


def image(largeur: int = 40, hauteur: int = 30, format_pillow: str = "PNG") -> bytes:
    img = Image.new("RGB", (largeur, hauteur))
    img.putdata(
        [
            ((x * 255) // max(1, largeur - 1), (y * 255) // max(1, hauteur - 1), 120)
            for y in range(hauteur)
            for x in range(largeur)
        ]
    )
    tampon = io.BytesIO()
    img.save(tampon, format=format_pillow)
    return tampon.getvalue()


def fichier(octets: bytes, nom: str = "visuel.png", type_mime: str = "image/png"):  # type: ignore[no-untyped-def]
    return {"fichier": (nom, io.BytesIO(octets), type_mime)}


async def deposer(client: AsyncClient, jetons, octets: bytes | None = None, **kw):  # type: ignore[no-untyped-def]
    reponse = await client.post(
        "/api/v1/media", headers=entete(jetons), files=fichier(octets or image(), **kw)
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


class TestDroitsRequis:
    async def test_deposer_demande_manage_media(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        simple = await fabrique_utilisateur()
        jetons = await connexion(simple.email)
        reponse = await client.post("/api/v1/media", headers=entete(jetons), files=fichier(image()))
        assert reponse.status_code == 403

    async def test_purger_demande_son_propre_droit(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """manage_media archive ; détruire demande purge_media, qui est à part."""
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)

        archivage = await client.delete(
            f"/api/v1/media/{depose['id_media']}", headers=entete(jetons)
        )
        assert archivage.status_code == 204

        purge = await client.delete(
            f"/api/v1/media/{depose['id_media']}/purge", headers=entete(jetons)
        )
        assert purge.status_code == 403


class TestDepot:
    async def test_un_fichier_depose_part_dans_le_stockage(
        self,
        client: AsyncClient,
        fabrique_utilisateur,
        connexion,
        stockage_de_test: StockageLocal,
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        octets = image()
        depose = await deposer(client, jetons, octets)

        assert depose["file_type"] == "image/png"
        assert depose["size_bytes"] == len(octets)
        assert (depose["width"], depose["height"]) == (40, 30)
        assert depose["source"] == "upload"
        assert depose["url"].startswith("https://medias.test/")

    async def test_le_type_vient_des_octets_et_non_du_nom(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """Un JPEG nommé .png reste un JPEG : les contraintes CHECK de la base
        en dépendent."""
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons, image(format_pillow="JPEG"), nom="menteur.png")
        assert depose["file_type"] == "image/jpeg"

    async def test_le_nom_affiche_vient_du_fichier_a_defaut(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons, nom="affiche-janvier.png")
        assert depose["display_name"] == "affiche-janvier.png"

    async def test_un_format_inconnu_est_refuse(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        reponse = await client.post(
            "/api/v1/media",
            headers=entete(jetons),
            files=fichier(b"ceci n'est pas un fichier connu", nom="x.png"),
        )
        assert reponse.status_code == 415
        assert reponse.json()["error"]["code"] == "unsupported_file_type"

    async def test_la_cle_de_stockage_ne_sort_jamais_de_l_api(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """L'API expose une URL recomposée, pas la clé : celle-ci est un détail
        d'implémentation du stockage."""
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        assert "storage_key" not in depose


class TestBibliotheque:
    async def test_la_liste_exclut_les_archives_par_defaut(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        garde = await deposer(client, jetons)
        archive = await deposer(client, jetons)
        await client.delete(f"/api/v1/media/{archive['id_media']}", headers=entete(jetons))

        liste = await client.get("/api/v1/media", headers=entete(jetons))
        identifiants = [m["id_media"] for m in liste.json()["items"]]
        assert garde["id_media"] in identifiants
        assert archive["id_media"] not in identifiants

        avec = await client.get(
            "/api/v1/media", headers=entete(jetons), params={"include_archived": "true"}
        )
        assert archive["id_media"] in [m["id_media"] for m in avec.json()["items"]]

    async def test_renommer_un_media_archive_est_refuse(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))

        reponse = await client.patch(
            f"/api/v1/media/{depose['id_media']}",
            headers=entete(jetons),
            json={"display_name": "autre"},
        )
        assert reponse.status_code == 409

    async def test_archiver_deux_fois_renvoie_409(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))
        seconde = await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))
        assert seconde.status_code == 409


class TestPurge:
    async def test_purger_exige_un_archivage_prealable(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """La purge est sans retour : elle ne doit pas pouvoir être déclenchée
        d'un seul geste sur un média en service."""
        purgeur = await fabrique_utilisateur(droits=["manage_media", "purge_media"])
        jetons = await connexion(purgeur.email)
        depose = await deposer(client, jetons)

        reponse = await client.delete(
            f"/api/v1/media/{depose['id_media']}/purge", headers=entete(jetons)
        )
        assert reponse.status_code == 409

    async def test_la_purge_retire_la_ligne_et_le_fichier(
        self,
        client: AsyncClient,
        fabrique_utilisateur,
        connexion,
        stockage_de_test: StockageLocal,
    ) -> None:
        purgeur = await fabrique_utilisateur(droits=["manage_media", "purge_media"])
        jetons = await connexion(purgeur.email)
        depose = await deposer(client, jetons)

        await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))
        purge = await client.delete(
            f"/api/v1/media/{depose['id_media']}/purge", headers=entete(jetons)
        )
        assert purge.status_code == 204

        relecture = await client.get(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))
        assert relecture.status_code == 404

    async def test_la_purge_emporte_les_references_du_media(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """Sans cela, la clé étrangère refuserait la suppression, et le geste
        échouerait précisément sur les médias qui ont servi."""
        purgeur = await fabrique_utilisateur(
            droits=["manage_media", "manage_media_reference", "purge_media"]
        )
        jetons = await connexion(purgeur.email)
        depose = await deposer(client, jetons)
        await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={"id_media": depose["id_media"], "nature_code": "logo", "label": "Logo"},
        )

        await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))
        purge = await client.delete(
            f"/api/v1/media/{depose['id_media']}/purge", headers=entete(jetons)
        )
        assert purge.status_code == 204


class TestMediasDeReference:
    async def test_les_cinq_natures_sont_exposees(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        reponse = await client.get("/api/v1/media-reference-natures", headers=entete(jetons))
        assert [n["code"] for n in reponse.json()] == [
            "logo",
            "personne",
            "lieu",
            "objet",
            "fond",
        ]

    async def test_declarer_une_reference(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)

        reponse = await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={
                "id_media": depose["id_media"],
                "nature_code": "logo",
                "label": "Logo DATUM Academy",
            },
        )
        assert reponse.status_code == 201
        assert reponse.json()["nature_code"] == "logo"
        assert reponse.json()["is_active"] is True

    async def test_un_media_ne_se_declare_pas_deux_fois(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        corps = {
            "id_media": depose["id_media"],
            "nature_code": "logo",
            "label": "Premiere",
        }
        await client.post("/api/v1/media-references", headers=entete(jetons), json=corps)
        seconde = await client.post("/api/v1/media-references", headers=entete(jetons), json=corps)
        assert seconde.status_code == 409

    async def test_une_nature_inconnue_est_refusee(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        reponse = await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={"id_media": depose["id_media"], "nature_code": "mascotte", "label": "X"},
        )
        assert reponse.status_code == 400
        assert reponse.json()["error"]["code"] == "unknown_nature"

    async def test_archiver_un_media_archive_ses_references(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """Une référence pointant vers un média archivé enverrait un fichier
        absent au modèle d'image."""
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={"id_media": depose["id_media"], "nature_code": "logo", "label": "Logo"},
        )

        await client.delete(f"/api/v1/media/{depose['id_media']}", headers=entete(jetons))

        liste = await client.get("/api/v1/media-references", headers=entete(jetons))
        assert liste.json()["items"] == []

    async def test_une_reference_archivee_laisse_redeclarer_le_media(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        corps = {"id_media": depose["id_media"], "nature_code": "logo", "label": "Premiere"}
        premiere = await client.post("/api/v1/media-references", headers=entete(jetons), json=corps)
        await client.delete(
            f"/api/v1/media-references/{premiere.json()['id_media_references']}",
            headers=entete(jetons),
        )

        seconde = await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={**corps, "label": "Seconde"},
        )
        assert seconde.status_code == 201

    async def test_changer_la_nature_d_une_reference(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        gestionnaire = await fabrique_utilisateur(droits=["manage_media", "manage_media_reference"])
        jetons = await connexion(gestionnaire.email)
        depose = await deposer(client, jetons)
        creee = await client.post(
            "/api/v1/media-references",
            headers=entete(jetons),
            json={"id_media": depose["id_media"], "nature_code": "logo", "label": "Logo"},
        )

        modifiee = await client.patch(
            f"/api/v1/media-references/{creee.json()['id_media_references']}",
            headers=entete(jetons),
            json={"nature_code": "personne"},
        )
        assert modifiee.status_code == 200
        assert modifiee.json()["nature_code"] == "personne"
