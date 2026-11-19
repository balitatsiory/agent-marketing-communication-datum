"""Reconnaissance et compression des fichiers déposés.

Deux responsabilités, volontairement séparées du service : elles ne touchent
ni à la base ni au stockage, et se testent donc sur des octets, sans rien
monter autour.

**Le type est détecté aux octets, jamais déduit de l'extension.** C'est ce que
dit le commentaire de `media.file_type` en base, et ce n'est pas une
coquetterie : un fichier nommé `photo.png` peut être n'importe quoi, et les
contraintes CHECK de la table — durée réservée aux vidéos, variantes limitées
aux images — reposeraient alors sur une affirmation du navigateur.

**La compression suit la règle du document d'architecture v1.4 du 21 octobre
2026** : au-delà de 8 Mo, baisser d'abord la qualité à format et dimensions
constants, et ne redimensionner qu'en dernier recours.
"""

from __future__ import annotations

import io

from PIL import Image

from app.core.errors import ApiError

# Signatures reconnues. La valeur est le type MIME inscrit en base.
# Un format absent de cette table est refusé : mieux vaut refuser un format
# legitime que ranger un fichier dont on ignore la nature.
SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (4, b"ftyp", "video/mp4"),
    (0, b"\x1a\x45\xdf\xa3", "video/webm"),
)

# Octets nécessaires pour trancher. WebP demande les douze premiers : RIFF,
# puis quatre octets de taille, puis WEBP.
OCTETS_DE_RECONNAISSANCE = 16

# Qualités essayées successivement, de la moins destructrice à la plus. En
# dessous de 45, l'image devient visiblement dégradée : mieux vaut alors
# redimensionner, ce que fait l'étape suivante.
QUALITES = (85, 75, 65, 55, 45)

# Facteur appliqué à chaque réduction. 0,8 divise la surface par 1,5 environ :
# assez pour progresser, assez peu pour ne pas sur-réduire d'un coup.
FACTEUR_REDUCTION = 0.8
# Douze réductions ramènent une image à 7 % de sa largeur d'origine. Huit, soit
# 17 %, se sont révélées insuffisantes à l'essai sur un PNG : la bosse décrite
# plus bas consomme les premières étapes sans rien gagner.
REDUCTIONS_MAX = 12

TYPES_IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp"}

# Formats Pillow acceptant un paramètre de qualité. Pour les autres, PNG en
# tête, la qualité n'est pas un levier : on redimensionne directement.
FORMATS_AVEC_QUALITE = {"JPEG", "WEBP"}


class TypeDeFichierRefuseError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported_file_type",
            "Ce format de fichier n'est pas accepté. Formats reconnus : "
            "PNG, JPEG, GIF, WebP, MP4, WebM.",
            415,
        )


class ImageTropGrandeError(ApiError):
    def __init__(self, pixels: int, pixels_max: int) -> None:
        super().__init__(
            "image_too_large",
            f"L'image compte {pixels // 1_000_000} millions de pixels, au-delà "
            f"de la limite de {pixels_max // 1_000_000} millions.",
            413,
        )


class ImageIncompressibleError(ApiError):
    def __init__(self, octets_max: int) -> None:
        super().__init__(
            "image_not_compressible",
            f"L'image n'a pas pu être ramenée sous {octets_max // (1024 * 1024)} Mo.",
            422,
        )


def detecter_type(debut: bytes) -> str:
    """Type MIME lu dans les premiers octets du fichier.

    Lève `TypeDeFichierRefuseError` si aucune signature ne correspond.
    """
    # WebP se reconnaît en deux morceaux disjoints, d'où ce cas à part.
    if debut[:4] == b"RIFF" and debut[8:12] == b"WEBP":
        return "image/webp"

    for position, signature, type_mime in SIGNATURES:
        if debut[position : position + len(signature)] == signature:
            return type_mime

    raise TypeDeFichierRefuseError()


def est_une_image(type_mime: str) -> bool:
    return type_mime in TYPES_IMAGE


def dimensions(donnees: bytes, pixels_max: int) -> tuple[int, int]:
    """Largeur et hauteur, sans décoder l'image entière.

    Pillow ne lit que l'en-tête tant que les pixels ne sont pas demandés : la
    limite est donc vérifiée AVANT qu'une image piégée n'occupe la mémoire.
    """
    # Garde-fou de Pillow contre les images volontairement énormes. Réglé sur
    # notre propre limite plutôt que sur sa valeur par défaut.
    Image.MAX_IMAGE_PIXELS = pixels_max

    try:
        with Image.open(io.BytesIO(donnees)) as image:
            largeur, hauteur = image.size
    except Image.DecompressionBombError as erreur:
        raise ImageTropGrandeError(pixels_max, pixels_max) from erreur
    except OSError as erreur:
        raise TypeDeFichierRefuseError() from erreur

    if largeur * hauteur > pixels_max:
        raise ImageTropGrandeError(largeur * hauteur, pixels_max)
    return largeur, hauteur


def _encoder(image: Image.Image, format_pillow: str, qualite: int | None) -> bytes:
    tampon = io.BytesIO()
    options: dict[str, object] = {"optimize": True}
    if qualite is not None:
        options["quality"] = qualite
    image.save(tampon, format=format_pillow, **options)
    return tampon.getvalue()


def compresser(donnees: bytes, octets_max: int) -> tuple[bytes, int, int]:
    """Ramène une image sous le plafond. Renvoie (octets, largeur, hauteur).

    Le fichier est rendu tel quel s'il tient déjà : une image légère ne doit
    jamais être réencodée, ce qui lui ferait perdre de la qualité pour rien.

    La méthode suit le document d'architecture : la qualité baisse d'abord, à
    format et dimensions constants ; le redimensionnement n'intervient
    qu'ensuite. Conséquence assumée et notée dans ce document : au-delà du
    plafond, la qualité d'origine est perdue définitivement.
    """
    if len(donnees) <= octets_max:
        with Image.open(io.BytesIO(donnees)) as image:
            return donnees, image.width, image.height

    with Image.open(io.BytesIO(donnees)) as ouverte:
        image = ouverte.copy()
        format_pillow = ouverte.format or "PNG"

    if format_pillow in FORMATS_AVEC_QUALITE:
        for qualite in QUALITES:
            compressee = _encoder(image, format_pillow, qualite)
            if len(compressee) <= octets_max:
                return compressee, image.width, image.height

    # Dernier recours : réduire les dimensions, en gardant le format.
    #
    # Attention, contre l'intuition : réduire un PNG ne le rend pas forcément
    # plus léger. Le rééchantillonnage détruit les régularités de l'image, que
    # la compression sans perte du PNG exploitait ; une image très régulière
    # peut ainsi GROSSIR aux premières réductions avant de diminuer. Mesuré le
    # 19 novembre 2026 : un PNG de 2 660 octets passe à 4 059 puis 11 655 avant
    # de redescendre. D'où une boucle qui va jusqu'au bout au lieu de s'arrêter
    # à la première étape sans gain, et un refus franc si le plafond reste hors
    # d'atteinte.
    qualite_basse = QUALITES[-1] if format_pillow in FORMATS_AVEC_QUALITE else None
    for _ in range(REDUCTIONS_MAX):
        largeur = max(1, int(image.width * FACTEUR_REDUCTION))
        hauteur = max(1, int(image.height * FACTEUR_REDUCTION))
        image = image.resize((largeur, hauteur), Image.Resampling.LANCZOS)
        compressee = _encoder(image, format_pillow, qualite_basse)
        if len(compressee) <= octets_max:
            return compressee, largeur, hauteur

    raise ImageIncompressibleError(octets_max)
