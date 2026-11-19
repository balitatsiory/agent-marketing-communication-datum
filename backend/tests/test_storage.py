"""La couche de stockage, éprouvée sans réseau ni identifiants Cloudflare.

Ces tests portent sur l'implémentation locale et sur le lecteur borné, qui
sont la partie où se joue la sécurité du dépôt. L'implémentation R2 n'est pas
testée ici : elle n'ajoute que la traduction vers l'API S3, et la tester
demanderait un seau réel, ce qui rendrait la suite dépendante du réseau.
"""

import io
from pathlib import Path

import pytest

from app.core.errors import ApiError
from app.core.storage import FichierTropLourdError, LecteurBorne, StockageLocal


class TestLecteurBorne:
    async def test_un_flux_sous_le_plafond_passe_entier(self) -> None:
        lecteur = LecteurBorne(io.BytesIO(b"x" * 100), octets_max=200)
        assert lecteur.read() == b"x" * 100
        assert lecteur.octets_lus == 100

    async def test_le_plafond_interrompt_la_lecture(self) -> None:
        """Le refus tombe PENDANT la lecture : un fichier énorme n'est jamais
        transféré en entier pour être rejeté ensuite."""
        lecteur = LecteurBorne(io.BytesIO(b"x" * 1000), octets_max=100)
        with pytest.raises(FichierTropLourdError):
            lecteur.read(500)

    async def test_le_plafond_porte_sur_le_cumul_et_non_sur_un_morceau(self) -> None:
        lecteur = LecteurBorne(io.BytesIO(b"x" * 300), octets_max=250)
        lecteur.read(100)
        lecteur.read(100)
        with pytest.raises(FichierTropLourdError):
            lecteur.read(100)

    async def test_le_refus_porte_le_statut_413(self) -> None:
        erreur = FichierTropLourdError(8 * 1024 * 1024)
        assert erreur.status_code == 413
        assert erreur.code == "file_too_large"
        assert "8 Mo" in str(erreur)


class TestStockageLocal:
    async def test_un_fichier_depose_se_retrouve_sur_le_disque(self, tmp_path: Path) -> None:
        stockage = StockageLocal(tmp_path)
        octets = await stockage.deposer("2026/11/essai.png", io.BytesIO(b"abc"), "image/png")

        assert octets == 3
        assert (tmp_path / "2026/11/essai.png").read_bytes() == b"abc"

    async def test_les_dossiers_intermediaires_sont_crees(self, tmp_path: Path) -> None:
        stockage = StockageLocal(tmp_path)
        await stockage.deposer("a/b/c/d.png", io.BytesIO(b"x"), "image/png")
        assert (tmp_path / "a/b/c/d.png").exists()

    async def test_une_cle_qui_remonte_l_arborescence_est_refusee(self, tmp_path: Path) -> None:
        """La clé est fabriquée par le service, mais le stockage ne lui fait pas
        confiance pour autant."""
        stockage = StockageLocal(tmp_path)
        with pytest.raises(ApiError) as capture:
            await stockage.deposer("../dehors.png", io.BytesIO(b"x"), "image/png")
        assert capture.value.status_code == 400

    async def test_supprimer_un_objet_absent_ne_proteste_pas(self, tmp_path: Path) -> None:
        """La suppression doit pouvoir être rejouée : un ménage interrompu puis
        relancé ne doit pas échouer sur ce qu'il a déjà retiré."""
        stockage = StockageLocal(tmp_path)
        await stockage.supprimer("jamais/depose.png")

    async def test_un_objet_depose_puis_supprime_disparait(self, tmp_path: Path) -> None:
        stockage = StockageLocal(tmp_path)
        await stockage.deposer("x.png", io.BytesIO(b"x"), "image/png")
        await stockage.supprimer("x.png")
        assert not (tmp_path / "x.png").exists()

    async def test_l_url_publique_se_recompose_a_partir_de_la_cle(self, tmp_path: Path) -> None:
        """La base ne garde qu'une clé : l'adresse se reconstruit à la lecture."""
        stockage = StockageLocal(tmp_path, base_url="https://medias.example.com/")
        assert stockage.url_publique("2026/11/a.png") == "https://medias.example.com/2026/11/a.png"
