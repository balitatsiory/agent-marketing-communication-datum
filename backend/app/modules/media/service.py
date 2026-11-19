"""Règles métier du module Média."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import BinaryIO

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.core.storage import FichierTropLourdError, Stockage
from app.modules.media.images import compresser, detecter_type, dimensions, est_une_image
from app.modules.media.models import (
    Media,
    MediaReference,
    MediaReferenceNature,
    MediaVariant,
)
from app.modules.media.schemas import MediaReferenceCreate, MediaReferenceUpdate
from app.modules.users.models import User

# Extension donnée à la clé de stockage. Elle ne sert pas à déterminer le type
# — celui-ci est détecté aux octets — mais à ce qu'un objet reste identifiable
# dans le tableau de bord Cloudflare et qu'un téléchargement direct s'ouvre
# avec la bonne application.
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}

# Taille lue pour reconnaître le type. Douze octets suffisent à toutes les
# signatures connues ; on en lit un peu plus par prudence.
OCTETS_DE_RECONNAISSANCE = 32


def fabriquer_cle(type_mime: str, quand: datetime | None = None) -> str:
    """Clé de l'objet dans le stockage.

    Trois propriétés voulues : elle ne se devine pas, elle ne révèle pas le nom
    donné par l'utilisateur, et elle se range par mois, ce qui rend un inventaire
    ou une purge par période praticables côté Cloudflare.
    """
    date = quand or datetime.now(UTC)
    return f"{date:%Y/%m}/{uuid.uuid4().hex}{EXTENSIONS.get(type_mime, '')}"


async def _lire_avec_plafond(flux: BinaryIO, octets_max: int) -> bytes:
    """Lit tout le flux, en refusant dès le plafond franchi.

    Utilisé pour les images seulement : elles doivent être entièrement en
    mémoire pour être mesurées et compressées. Une vidéo, elle, n'est jamais
    chargée : elle part vers le stockage morceau par morceau.
    """
    morceaux: list[bytes] = []
    total = 0
    while morceau := flux.read(1024 * 1024):
        total += len(morceau)
        if total > octets_max:
            raise FichierTropLourdError(octets_max)
        morceaux.append(morceau)
    return b"".join(morceaux)


async def deposer(
    session: AsyncSession,
    stockage: Stockage,
    flux: BinaryIO,
    display_name: str,
    par: User,
) -> Media:
    """Range un fichier et écrit sa ligne.

    L'ordre compte : l'objet part d'abord, la ligne ensuite. Si l'écriture en
    base échoue, l'objet est retiré — un objet sans ligne est invisible et
    coûte du stockage, tandis qu'une ligne sans objet casserait chaque
    affichage de la bibliothèque.
    """
    reglages = get_settings()

    debut = flux.read(OCTETS_DE_RECONNAISSANCE)
    type_mime = detecter_type(debut)

    largeur: int | None = None
    hauteur: int | None = None

    if est_une_image(type_mime):
        donnees = debut + await _lire_avec_plafond(flux, reglages.MEDIA_MAX_UPLOAD_BYTES)
        dimensions(donnees, reglages.MEDIA_MAX_PIXELS)
        donnees, largeur, hauteur = compresser(donnees, reglages.MEDIA_MAX_STORED_BYTES)
        a_envoyer: BinaryIO = _Tampon(donnees)
    else:
        # La vidéo n'est ni mesurée ni transformée : le document du 21 octobre
        # exclut toute transformation, et la durée demanderait un décodeur que
        # le projet n'embarque pas. video_duration_seconds reste nul.
        a_envoyer = _Enchaine(debut, flux)

    cle = fabriquer_cle(type_mime)
    octets = await stockage.deposer(cle, a_envoyer, type_mime)

    media = Media(
        storage_key=cle,
        file_type=type_mime,
        source="upload",
        display_name=display_name,
        size_bytes=octets,
        width=largeur,
        height=hauteur,
        id_users_created_by=par.id_users,
    )
    session.add(media)
    try:
        await session.flush()
    except Exception:
        await stockage.supprimer(cle)
        raise
    return media


class _Tampon:
    """Flux en mémoire, exposant le seul `read` qu'attend le stockage."""

    def __init__(self, donnees: bytes) -> None:
        self._donnees = donnees
        self._position = 0

    def read(self, taille: int = -1) -> bytes:
        if taille < 0:
            morceau = self._donnees[self._position :]
        else:
            morceau = self._donnees[self._position : self._position + taille]
        self._position += len(morceau)
        return morceau


class _Enchaine:
    """Recolle les octets déjà lus devant le reste du flux.

    La reconnaissance du type consomme les premiers octets ; sans cette
    enveloppe, le fichier arriverait tronqué dans le stockage.
    """

    def __init__(self, debut: bytes, suite: BinaryIO) -> None:
        self._debut = debut
        self._suite = suite

    def read(self, taille: int = -1) -> bytes:
        if not self._debut:
            return self._suite.read(taille)
        if taille < 0:
            morceau, self._debut = self._debut, b""
            return morceau + self._suite.read()
        morceau, self._debut = self._debut[:taille], self._debut[taille:]
        if len(morceau) < taille:
            morceau += self._suite.read(taille - len(morceau))
        return morceau


async def lister(
    session: AsyncSession, params: PageParams, inclure_archives: bool = False
) -> tuple[list[Media], int]:
    conditions = [] if inclure_archives else [Media.deleted_at.is_(None)]

    total = (
        await session.execute(select(func.count()).select_from(Media).where(*conditions))
    ).scalar_one()

    requete = (
        select(Media)
        .where(*conditions)
        .order_by(Media.created_at.desc(), Media.id_media.desc())
        .offset(params.offset)
        .limit(params.size)
    )
    return list((await session.execute(requete)).scalars().all()), int(total)


async def obtenir(session: AsyncSession, id_media: int) -> Media:
    media = await session.get(Media, id_media)
    if media is None:
        raise NotFoundError("Ce média n'existe pas.")
    return media


async def renommer(session: AsyncSession, id_media: int, display_name: str) -> Media:
    media = await obtenir(session, id_media)
    if media.deleted_at is not None:
        raise ConflictError("Ce média est archivé : son nom n'est plus modifiable.")
    media.display_name = display_name
    await session.flush()
    return media


async def archiver(session: AsyncSession, id_media: int, par: User) -> None:
    """Retire le média des listes sans détruire le fichier.

    Un média porté par une publication déjà diffusée ne peut pas disparaître
    sans emporter l'historique avec lui. Ses références éventuelles sont
    archivées dans la même transaction : une référence qui pointerait vers un
    média archivé enverrait un fichier absent au modèle d'image.
    """
    media = await obtenir(session, id_media)
    if media.deleted_at is not None:
        raise ConflictError("Ce média est déjà archivé.")

    maintenant = datetime.now(UTC)
    media.deleted_at = maintenant
    media.id_users_deleted_by = par.id_users

    references = (
        (
            await session.execute(
                select(MediaReference).where(
                    MediaReference.id_media == id_media,
                    MediaReference.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for reference in references:
        reference.deleted_at = maintenant
        reference.id_users_deleted_by = par.id_users

    await session.flush()


async def purger(session: AsyncSession, stockage: Stockage, id_media: int, par: User) -> None:
    """Détruit le fichier ET sa ligne, sans retour possible.

    Geste distinct de l'archivage et protégé par son propre droit. Il n'existe
    que pour ce qui n'aurait jamais dû être déposé ; la base ne peut pas le
    rattraper, d'où le refus tant que le média n'a pas d'abord été archivé.
    """
    media = await obtenir(session, id_media)
    if media.deleted_at is None:
        raise ConflictError("Un média doit être archivé avant d'être supprimé définitivement.")

    # Les lignes qui pointent vers ce média partent d'abord : sans cela, la
    # clé étrangère refuserait la suppression, et le geste échouerait sur les
    # médias qui ont justement servi — c'est-à-dire ceux qu'on purge.
    await session.execute(delete(MediaVariant).where(MediaVariant.id_media == id_media))
    await session.execute(delete(MediaReference).where(MediaReference.id_media == id_media))

    cle = media.storage_key
    await session.delete(media)
    await session.flush()
    # Le fichier part APRÈS la ligne : si la suppression de la ligne échoue,
    # rien n'est perdu ; l'inverse laisserait une ligne pointant dans le vide.
    await stockage.supprimer(cle)


# --------------------------------------------------------------- références


async def lister_natures(session: AsyncSession) -> list[MediaReferenceNature]:
    requete = (
        select(MediaReferenceNature)
        .where(MediaReferenceNature.is_enabled.is_(True))
        .order_by(MediaReferenceNature.sort_order)
    )
    return list((await session.execute(requete)).scalars().all())


async def _nature_par_code(session: AsyncSession, code: str) -> MediaReferenceNature:
    nature = (
        await session.execute(select(MediaReferenceNature).where(MediaReferenceNature.code == code))
    ).scalar_one_or_none()
    if nature is None:
        raise ApiError("unknown_nature", f"Nature de référence inconnue : {code}.", 400)
    return nature


async def declarer_reference(
    session: AsyncSession, donnees: MediaReferenceCreate, par: User
) -> MediaReference:
    media = await obtenir(session, donnees.id_media)
    if media.deleted_at is not None:
        raise ConflictError("Ce média est archivé : il ne peut pas servir de référence.")
    if not est_une_image(media.file_type):
        raise ConflictError("Seule une image peut servir de référence à la génération.")

    deja = (
        await session.execute(
            select(MediaReference).where(
                MediaReference.id_media == donnees.id_media,
                MediaReference.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if deja is not None:
        raise ConflictError("Ce média est déjà déclaré comme référence.")

    nature = await _nature_par_code(session, donnees.nature_code)
    reference = MediaReference(
        id_media=donnees.id_media,
        id_media_reference_natures=nature.id_media_reference_natures,
        label=donnees.label,
        description=donnees.description,
        id_users_created_by=par.id_users,
    )
    session.add(reference)
    await session.flush()
    return reference


async def lister_references(
    session: AsyncSession, params: PageParams, inclure_archivees: bool = False
) -> tuple[list[MediaReference], int]:
    conditions = [] if inclure_archivees else [MediaReference.deleted_at.is_(None)]

    total = (
        await session.execute(select(func.count()).select_from(MediaReference).where(*conditions))
    ).scalar_one()

    requete = (
        select(MediaReference)
        .where(*conditions)
        .order_by(MediaReference.label)
        .offset(params.offset)
        .limit(params.size)
    )
    return list((await session.execute(requete)).scalars().all()), int(total)


async def obtenir_reference(session: AsyncSession, id_reference: int) -> MediaReference:
    reference = await session.get(MediaReference, id_reference)
    if reference is None:
        raise NotFoundError("Cette référence n'existe pas.")
    return reference


async def modifier_reference(
    session: AsyncSession, id_reference: int, donnees: MediaReferenceUpdate, par: User
) -> MediaReference:
    reference = await obtenir_reference(session, id_reference)
    if reference.deleted_at is not None:
        raise ConflictError("Cette référence est archivée.")

    if donnees.nature_code is not None:
        nature = await _nature_par_code(session, donnees.nature_code)
        reference.id_media_reference_natures = nature.id_media_reference_natures
    if donnees.label is not None:
        reference.label = donnees.label
    if donnees.description is not None:
        reference.description = donnees.description
    if donnees.is_active is not None:
        reference.is_active = donnees.is_active

    await session.flush()
    return reference


async def archiver_reference(session: AsyncSession, id_reference: int, par: User) -> None:
    """Le média, lui, reste : seule sa qualité de référence est retirée."""
    reference = await obtenir_reference(session, id_reference)
    if reference.deleted_at is not None:
        raise ConflictError("Cette référence est déjà archivée.")

    reference.deleted_at = datetime.now(UTC)
    reference.id_users_deleted_by = par.id_users
    await session.flush()


async def code_de_nature(session: AsyncSession, id_nature: int) -> str:
    nature = await session.get(MediaReferenceNature, id_nature)
    return nature.code if nature is not None else ""
