"""Recette du stockage Cloudflare R2.

À lancer une fois les cinq réglages R2_* renseignés dans backend/.env et
STORAGE_BACKEND passé à « r2 » :

    .venv\\Scripts\\python -m scripts.verifier_r2

Le script dépose un objet d'essai, le relit, contrôle sa taille et son type,
teste la lecture publique, puis le supprime. Il n'affiche AUCUN secret :
seulement la présence ou l'absence de chaque réglage.

Pourquoi un script plutôt qu'un test : la suite pytest ne doit dépendre ni du
réseau ni d'identifiants Cloudflare. La recette du vrai seau est une
vérification manuelle, faite une fois à la mise en service.
"""

from __future__ import annotations

import asyncio
import io
import urllib.error
import urllib.request
import uuid
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.storage import get_stockage

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

CONTENU = b"IAGORA - recette du stockage R2\n"
TYPE_MIME = "text/plain"


def _ligne(renseigne: bool, texte: str) -> str:
    return f"  [{'x' if renseigne else ' '}] {texte}"


def _client_lecture() -> S3Client:
    """Client de relecture, construit à part du stockage testé."""
    import boto3
    from botocore.config import Config

    reglages = get_settings()
    assert reglages.R2_ACCESS_KEY_ID is not None
    assert reglages.R2_SECRET_ACCESS_KEY is not None
    return boto3.client(
        "s3",
        endpoint_url=reglages.r2_endpoint_url,
        aws_access_key_id=reglages.R2_ACCESS_KEY_ID.get_secret_value(),
        aws_secret_access_key=reglages.R2_SECRET_ACCESS_KEY.get_secret_value(),
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


async def principal() -> int:
    reglages = get_settings()

    print("1. Configuration lue dans backend/.env")
    print(_ligne(reglages.STORAGE_BACKEND == "r2", f"STORAGE_BACKEND = {reglages.STORAGE_BACKEND}"))
    print(_ligne(bool(reglages.R2_ACCOUNT_ID), "R2_ACCOUNT_ID"))
    print(_ligne(reglages.R2_ACCESS_KEY_ID is not None, "R2_ACCESS_KEY_ID"))
    print(_ligne(reglages.R2_SECRET_ACCESS_KEY is not None, "R2_SECRET_ACCESS_KEY"))
    print(_ligne(bool(reglages.R2_BUCKET), f"R2_BUCKET = {reglages.R2_BUCKET or '?'}"))
    print(_ligne(bool(reglages.R2_PUBLIC_BASE_URL), "R2_PUBLIC_BASE_URL"))
    print(f"      adresse S3 : {reglages.r2_endpoint_url}")

    if reglages.STORAGE_BACKEND != "r2":
        print("\nSTORAGE_BACKEND ne vaut pas « r2 » : rien n'est envoyé.")
        print("Mettre STORAGE_BACKEND=r2 dans backend/.env, puis relancer.")
        return 1

    stockage = get_stockage()
    client = _client_lecture()
    cle = f"recette/{uuid.uuid4().hex}.txt"

    print(f"\n2. Dépôt de {len(CONTENU)} octets sous « {cle} »")
    octets = await stockage.deposer(cle, io.BytesIO(CONTENU), TYPE_MIME)
    print(_ligne(octets == len(CONTENU), f"dépôt accepté, {octets} octets comptés"))

    print("\n3. Relecture par l'API S3")
    tete = client.head_object(Bucket=reglages.R2_BUCKET, Key=cle)
    taille = int(tete["ContentLength"])
    type_rendu = str(tete.get("ContentType", ""))
    print(_ligne(taille == len(CONTENU), f"taille rendue : {taille} octets"))
    print(_ligne(type_rendu == TYPE_MIME, f"type rendu : {type_rendu or 'aucun'}"))
    corps = client.get_object(Bucket=reglages.R2_BUCKET, Key=cle)["Body"].read()
    print(_ligne(corps == CONTENU, "contenu identique à l'octet près"))

    print("\n4. Lecture publique (celle dont se sert l'application)")
    url = stockage.url_publique(cle)
    print(f"      {url}")
    if not reglages.R2_PUBLIC_BASE_URL:
        print(_ligne(False, "R2_PUBLIC_BASE_URL vide : l'URL rendue est inutilisable"))
    else:
        try:
            with urllib.request.urlopen(url, timeout=15) as reponse:
                public = reponse.read()
            print(_ligne(public == CONTENU, f"lecture anonyme : {len(public)} octets"))
        except urllib.error.HTTPError as erreur:
            print(_ligne(False, f"lecture anonyme refusée : HTTP {erreur.code}"))
            print("      Le seau n'est pas en accès public ou le domaine n'est")
            print("      pas rattaché. À régler dans R2 > Settings > Public access.")
        except urllib.error.URLError as erreur:
            print(_ligne(False, f"domaine injoignable : {erreur.reason}"))

    print("\n5. Suppression")
    await stockage.supprimer(cle)
    from botocore.exceptions import ClientError

    try:
        client.head_object(Bucket=reglages.R2_BUCKET, Key=cle)
    except ClientError as erreur:
        code = str(erreur.response.get("Error", {}).get("Code", ""))
        print(_ligne(code in {"404", "NoSuchKey"}, f"objet absent après suppression ({code})"))
    else:
        print(_ligne(False, "l'objet est TOUJOURS là : la suppression a échoué"))

    print("\nRecette terminée. Toute ligne [ ] est un point à régler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(principal()))
