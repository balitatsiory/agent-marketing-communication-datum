"""Reconnaissance et compression, éprouvées sur des octets.

Ces tests ne montent ni base ni stockage : `images.py` ne dépend de rien, et
c'est précisément ce qui permet de le vérifier finement.

Le plafond utilisé ici vaut quelques milliers d'octets et non 8 Mo. La logique
est la même, et fabriquer une image de 8 Mo à chaque test rendrait la suite
inutilement lente.
"""

import io

import pytest
from PIL import Image

from app.modules.media.images import (
    ImageTropGrandeError,
    TypeDeFichierRefuseError,
    compresser,
    detecter_type,
    dimensions,
    est_une_image,
)


def image_bruitee(largeur: int, hauteur: int, format_pillow: str) -> bytes:
    """Image à l'allure photographique : dégradé doux et grain léger.

    Ni aplat uni, qui se réduirait à quelques centaines d'octets et ne mettrait
    jamais la compression à l'épreuve, ni bruit pur, qui est le pire cas de
    toutes les compressions et ne ressemble à aucun fichier réellement déposé.
    """
    image = Image.new("RGB", (largeur, hauteur))
    image.putdata(
        [
            (
                (x * 255) // max(1, largeur - 1),
                (y * 255) // max(1, hauteur - 1),
                128 + ((x * 3 + y * 5) % 24),
            )
            for y in range(hauteur)
            for x in range(largeur)
        ]
    )
    tampon = io.BytesIO()
    image.save(tampon, format=format_pillow)
    return tampon.getvalue()


class TestDetectionDuType:
    @pytest.mark.parametrize(
        ("format_pillow", "attendu"),
        [
            ("PNG", "image/png"),
            ("JPEG", "image/jpeg"),
            ("WEBP", "image/webp"),
            ("GIF", "image/gif"),
        ],
    )
    def test_les_formats_d_image_sont_reconnus(self, format_pillow: str, attendu: str) -> None:
        octets = image_bruitee(8, 8, format_pillow)
        assert detecter_type(octets[:16]) == attendu

    def test_le_mp4_est_reconnu_a_sa_boite_ftyp(self) -> None:
        assert detecter_type(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 8) == "video/mp4"

    def test_le_webm_est_reconnu(self) -> None:
        assert detecter_type(b"\x1a\x45\xdf\xa3" + b"\x00" * 12) == "video/webm"

    def test_le_type_vient_des_octets_et_non_du_nom(self) -> None:
        """Un fichier nommé .png mais contenant du JPEG est du JPEG.

        C'est la raison d'être de cette fonction : les contraintes CHECK de la
        table — durée réservée aux vidéos, variantes limitées aux images —
        reposeraient sinon sur une affirmation du navigateur.
        """
        octets = image_bruitee(8, 8, "JPEG")
        assert detecter_type(octets[:16]) == "image/jpeg"

    def test_un_format_inconnu_est_refuse(self) -> None:
        with pytest.raises(TypeDeFichierRefuseError) as capture:
            detecter_type(b"ceci n'est pas un fichier connu")
        assert capture.value.status_code == 415

    def test_un_fichier_vide_est_refuse(self) -> None:
        with pytest.raises(TypeDeFichierRefuseError):
            detecter_type(b"")

    def test_les_videos_ne_sont_pas_des_images(self) -> None:
        assert est_une_image("image/png")
        assert not est_une_image("video/mp4")


class TestDimensions:
    def test_les_dimensions_sont_lues(self) -> None:
        assert dimensions(image_bruitee(40, 25, "PNG"), pixels_max=1_000_000) == (40, 25)

    # Pillow avertit lui aussi au-delà de la limite qu'on lui a fixée : c'est
    # exactement ce que ce test provoque, et l'avertissement n'a pas à encombrer
    # la sortie de la suite.
    @pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
    def test_au_dela_de_la_limite_de_pixels_l_image_est_refusee(self) -> None:
        with pytest.raises(ImageTropGrandeError) as capture:
            dimensions(image_bruitee(40, 25, "PNG"), pixels_max=500)
        assert capture.value.status_code == 413

    def test_un_fichier_qui_n_est_pas_une_image_est_refuse(self) -> None:
        with pytest.raises(TypeDeFichierRefuseError):
            dimensions(b"\x1a\x45\xdf\xa3 pas une image", pixels_max=1_000_000)


class TestCompression:
    def test_une_image_sous_le_plafond_n_est_pas_reencodee(self) -> None:
        """Réencoder une image légère lui ferait perdre de la qualité pour rien :
        les octets rendus doivent être exactement ceux reçus."""
        octets = image_bruitee(20, 20, "JPEG")
        rendus, largeur, hauteur = compresser(octets, octets_max=len(octets) + 1)
        assert rendus == octets
        assert (largeur, hauteur) == (20, 20)

    def test_un_jpeg_trop_lourd_perd_de_la_qualite_avant_ses_dimensions(self) -> None:
        """Le document d'architecture impose cet ordre : qualité d'abord,
        redimensionnement en dernier recours."""
        octets = image_bruitee(400, 400, "JPEG")
        # Un plafond que la seule baisse de qualité peut atteindre : c'est
        # précisément ce que la règle du 21 octobre demande de vérifier.
        plafond = int(len(octets) * 0.8)
        rendus, largeur, hauteur = compresser(octets, octets_max=plafond)

        assert len(rendus) <= plafond
        assert (largeur, hauteur) == (400, 400)

    def test_un_png_trop_lourd_est_redimensionne(self) -> None:
        """La qualité n'est pas un levier sur un PNG : seule la taille l'est.
        La conversion de format relève de media_variants, pas du dépôt."""
        octets = image_bruitee(400, 400, "PNG")
        plafond = len(octets) // 2
        rendus, largeur, hauteur = compresser(octets, octets_max=plafond)

        assert len(rendus) <= plafond
        assert largeur < 400 and hauteur < 400

    def test_le_format_est_conserve(self) -> None:
        octets = image_bruitee(400, 400, "PNG")
        rendus, _, _ = compresser(octets, octets_max=len(octets) // 2)
        assert detecter_type(rendus[:16]) == "image/png"

    def test_les_dimensions_rendues_sont_celles_du_fichier_rendu(self) -> None:
        """Elles partent en base : une divergence ferait afficher de travers
        chaque vignette de la bibliothèque."""
        octets = image_bruitee(400, 400, "PNG")
        rendus, largeur, hauteur = compresser(octets, octets_max=len(octets) // 2)
        with Image.open(io.BytesIO(rendus)) as image:
            assert image.size == (largeur, hauteur)
