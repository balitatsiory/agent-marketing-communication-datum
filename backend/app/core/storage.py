"""Stockage des fichiers déposés.

Deux implémentations derrière une même interface : Cloudflare R2 en réel, et
un dossier du poste pour le développement et les tests. Sans cette seconde
implémentation, la suite de tests dépendrait du réseau et d'identifiants
Cloudflare, et ne pourrait tourner ni hors ligne ni sur une machine
d'intégration.

**La base ne garde jamais d'URL, seulement une clé.** Une URL expire, change de
domaine ou de schéma de signature ; une clé d'objet, non. L'adresse publique se
recompose à la lecture, à partir du domaine configuré.

R2 parle le protocole S3 : le client est celui d'AWS, pointé sur l'adresse R2
du compte, avec une région nommée « auto » que boto3 exige et que R2 ignore.
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Protocol

from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import ApiError

# Taille des morceaux envoyés à R2. Le fichier n'est jamais chargé en entier en
# mémoire : il est relayé morceau par morceau, ce qui borne la consommation
# quelle que soit la taille du dépôt.
TAILLE_MORCEAU = 8 * 1024 * 1024


class FichierTropLourdError(ApiError):
    """Le dépôt dépasse le garde-fou de soumission."""

    def __init__(self, octets_max: int) -> None:
        super().__init__(
            "file_too_large",
            f"Le fichier dépasse la taille maximale autorisée de {octets_max // (1024 * 1024)} Mo.",
            413,
        )


class LecteurBorne:
    """Enveloppe un flux et refuse de lire au-delà d'un plafond.

    Le contrôle se fait PENDANT la lecture et non après : un fichier de
    plusieurs gigaoctets est interrompu dès le plafond franchi, au lieu
    d'être transféré en entier pour être rejeté ensuite.
    """

    def __init__(self, flux: BinaryIO, octets_max: int) -> None:
        self._flux = flux
        self._octets_max = octets_max
        self.octets_lus = 0

    def read(self, taille: int = -1) -> bytes:
        morceau = self._flux.read(taille)
        self.octets_lus += len(morceau)
        if self.octets_lus > self._octets_max:
            raise FichierTropLourdError(self._octets_max)
        return morceau


class Stockage(Protocol):
    """Ce que le reste du code attend d'un stockage, et rien de plus."""

    async def deposer(self, cle: str, flux: BinaryIO, type_mime: str) -> int:
        """Range le flux sous cette clé. Renvoie le nombre d'octets écrits."""
        ...

    async def supprimer(self, cle: str) -> None:
        """Retire l'objet. Ne proteste pas s'il n'existe plus."""
        ...

    def url_publique(self, cle: str) -> str:
        """Adresse de lecture de l'objet."""
        ...


class StockageLocal:
    """Dossier du poste. Mode des tests et du développement."""

    def __init__(self, racine: Path, base_url: str = "/medias") -> None:
        self._racine = racine
        self._base_url = base_url.rstrip("/")

    def _chemin(self, cle: str) -> Path:
        # Une clé ne remonte jamais l'arborescence : elle est fabriquée par le
        # service, mais le stockage ne lui fait pas confiance pour autant.
        chemin = (self._racine / cle).resolve()
        if not chemin.is_relative_to(self._racine.resolve()):
            raise ApiError("invalid_storage_key", "Clé de stockage invalide.", 400)
        return chemin

    async def deposer(self, cle: str, flux: BinaryIO, type_mime: str) -> int:
        chemin = self._chemin(cle)
        chemin.parent.mkdir(parents=True, exist_ok=True)

        def ecrire() -> int:
            with chemin.open("wb") as sortie:
                shutil.copyfileobj(flux, sortie, TAILLE_MORCEAU)
            return chemin.stat().st_size

        return await run_in_threadpool(ecrire)

    async def supprimer(self, cle: str) -> None:
        chemin = self._chemin(cle)
        await run_in_threadpool(chemin.unlink, True)

    def url_publique(self, cle: str) -> str:
        return f"{self._base_url}/{cle}"


class StockageR2:
    """Cloudflare R2, par l'API S3."""

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        base_url_publique: str,
    ) -> None:
        import boto3
        from boto3.s3.transfer import TransferConfig
        from botocore.config import Config

        self._bucket = bucket
        self._base_url = base_url_publique.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        # Au-delà du seuil, boto3 découpe en parties et les envoie l'une après
        # l'autre : la mémoire reste bornée quelle que soit la taille du dépôt.
        self._transfert = TransferConfig(
            multipart_threshold=TAILLE_MORCEAU,
            multipart_chunksize=TAILLE_MORCEAU,
            use_threads=False,
        )

    async def deposer(self, cle: str, flux: BinaryIO, type_mime: str) -> int:
        compteur = LecteurBorne(flux, get_settings().MEDIA_MAX_UPLOAD_BYTES)

        def envoyer() -> None:
            # boto3 est synchrone : l'appel part dans un fil d'exécution séparé
            # pour ne pas immobiliser la boucle événementielle de l'API.
            self._client.upload_fileobj(
                compteur,
                self._bucket,
                cle,
                ExtraArgs={"ContentType": type_mime},
                Config=self._transfert,
            )

        await run_in_threadpool(envoyer)
        return compteur.octets_lus

    async def supprimer(self, cle: str) -> None:
        await run_in_threadpool(self._client.delete_object, Bucket=self._bucket, Key=cle)

    def url_publique(self, cle: str) -> str:
        return f"{self._base_url}/{cle}"


@lru_cache
def get_stockage() -> Stockage:
    """Stockage choisi par la configuration, construit une seule fois."""
    reglages = get_settings()

    if reglages.STORAGE_BACKEND == "local":
        return StockageLocal(Path(reglages.STORAGE_LOCAL_DIR))

    assert reglages.R2_ACCESS_KEY_ID is not None  # garanti par verifier_coherence
    assert reglages.R2_SECRET_ACCESS_KEY is not None
    return StockageR2(
        endpoint_url=reglages.r2_endpoint_url,
        access_key_id=reglages.R2_ACCESS_KEY_ID.get_secret_value(),
        secret_access_key=reglages.R2_SECRET_ACCESS_KEY.get_secret_value(),
        bucket=reglages.R2_BUCKET,
        base_url_publique=reglages.R2_PUBLIC_BASE_URL,
    )
