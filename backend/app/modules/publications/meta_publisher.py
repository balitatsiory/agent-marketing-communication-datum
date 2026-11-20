"""Diffusion réelle d'une cible sur Facebook via Meta Graph API.

Supporte :
- `text`     : POST /{page_id}/feed (message)
- `image`    : POST /{page_id}/photos (multipart si stockage local, sinon url)
- `carousel` : upload de chaque image avec published=false puis POST /{page_id}/feed
- `video` / `reel` : POST /{page_id}/videos

Dérive automatiquement le Page Access Token si le compte porte un User / System User Token.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.storage import get_stockage
from app.modules.media.models import Media
from app.modules.platforms.models import SocialPlatform
from app.modules.social_accounts.stats_collector import _resoudre_jeton_page_facebook

TIMEOUT_SECONDES = 60.0


@dataclass
class ResultatDiffusion:
    ok: bool
    post_external_id: str | None = None
    permalink: str | None = None
    error_detail: dict[str, Any] | None = None
    message: str = ""


def _lire_octets_locaux(media: Media) -> bytes | None:
    reglages = get_settings()
    if reglages.STORAGE_BACKEND != "local":
        return None
    racine = Path(reglages.STORAGE_LOCAL_DIR).resolve()
    chemin = (racine / media.storage_key).resolve()
    if not chemin.is_relative_to(racine) or not chemin.is_file():
        return None
    return chemin.read_bytes()


async def _lire_permalink(
    client: httpx.AsyncClient,
    base: str,
    version: str,
    post_id: str,
    page_token: str,
) -> str:
    try:
        rep = await client.get(
            f"{base}/{version}/{post_id}",
            params={"fields": "permalink_url", "access_token": page_token},
        )
        if rep.status_code == 200:
            url = rep.json().get("permalink_url")
            if isinstance(url, str) and url:
                return url
    except (httpx.HTTPError, ValueError):
        pass
    return f"https://www.facebook.com/{post_id}"


def _extraire_erreur_meta(rep: httpx.Response) -> tuple[str, dict[str, Any]]:
    try:
        corps = rep.json()
    except ValueError:
        corps = {"raw": rep.text[:400]}
    err = corps.get("error", {}) if isinstance(corps, dict) else {}
    msg = err.get("message") if isinstance(err, dict) else None
    texte = str(msg or rep.text[:300])
    return texte, {"status_code": rep.status_code, "meta_error": err or corps}


async def publier_sur_facebook(
    plateforme: SocialPlatform,
    page_id: str,
    access_token: str,
    format_code: str,
    legende: str,
    medias: list[Media],
) -> ResultatDiffusion:
    """Publie une cible sur une Page Facebook via Meta Graph API."""
    base = (plateforme.api_base_url or "https://graph.facebook.com").rstrip("/")
    version = (plateforme.api_version or "v26.0").strip("/")
    stockage = get_stockage()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDES) as client:
            page_token = await _resoudre_jeton_page_facebook(
                client, base, version, page_id, access_token
            )

            # 1. Texte seul
            if format_code == "text" or len(medias) == 0:
                rep = await client.post(
                    f"{base}/{version}/{page_id}/feed",
                    data={"message": legende, "access_token": page_token},
                )
                if rep.status_code >= 400:
                    msg, detail = _extraire_erreur_meta(rep)
                    return ResultatDiffusion(ok=False, error_detail=detail, message=msg)
                post_id = str(rep.json().get("id", ""))
                lien = await _lire_permalink(client, base, version, post_id, page_token)
                return ResultatDiffusion(
                    ok=True, post_external_id=post_id, permalink=lien, message="Publié sur Facebook."
                )

            # 2. Image unique
            if format_code in ("image", "story") and len(medias) == 1:
                m = medias[0]
                octets = _lire_octets_locaux(m)
                if octets is not None:
                    rep = await client.post(
                        f"{base}/{version}/{page_id}/photos",
                        data={"caption": legende, "published": "true", "access_token": page_token},
                        files={"source": (m.display_name, octets, m.file_type)},
                    )
                else:
                    rep = await client.post(
                        f"{base}/{version}/{page_id}/photos",
                        data={
                            "caption": legende,
                            "url": stockage.url_publique(m.storage_key),
                            "published": "true",
                            "access_token": page_token,
                        },
                    )
                if rep.status_code >= 400:
                    msg, detail = _extraire_erreur_meta(rep)
                    return ResultatDiffusion(ok=False, error_detail=detail, message=msg)
                corps = rep.json()
                post_id = str(corps.get("post_id") or corps.get("id") or "")
                lien = await _lire_permalink(client, base, version, post_id, page_token)
                return ResultatDiffusion(
                    ok=True, post_external_id=post_id, permalink=lien, message="Image publiée sur Facebook."
                )

            # 3. Carrousel (plusieurs images)
            if format_code == "carousel" or len(medias) > 1:
                media_fbids: list[str] = []
                for m in medias:
                    octets = _lire_octets_locaux(m)
                    if octets is not None:
                        rep_ph = await client.post(
                            f"{base}/{version}/{page_id}/photos",
                            data={"published": "false", "access_token": page_token},
                            files={"source": (m.display_name, octets, m.file_type)},
                        )
                    else:
                        rep_ph = await client.post(
                            f"{base}/{version}/{page_id}/photos",
                            data={
                                "url": stockage.url_publique(m.storage_key),
                                "published": "false",
                                "access_token": page_token,
                            },
                        )
                    if rep_ph.status_code >= 400:
                        msg, detail = _extraire_erreur_meta(rep_ph)
                        return ResultatDiffusion(ok=False, error_detail=detail, message=msg)
                    media_fbids.append(str(rep_ph.json()["id"]))

                charge: dict[str, str] = {"message": legende, "access_token": page_token}
                for idx, fbid in enumerate(media_fbids):
                    charge[f"attached_media[{idx}]"] = f'{{"media_fbid":"{fbid}"}}'

                rep = await client.post(f"{base}/{version}/{page_id}/feed", data=charge)
                if rep.status_code >= 400:
                    msg, detail = _extraire_erreur_meta(rep)
                    return ResultatDiffusion(ok=False, error_detail=detail, message=msg)
                post_id = str(rep.json().get("id", ""))
                lien = await _lire_permalink(client, base, version, post_id, page_token)
                return ResultatDiffusion(
                    ok=True,
                    post_external_id=post_id,
                    permalink=lien,
                    message=f"Carrousel ({len(media_fbids)} images) publié sur Facebook.",
                )

            # 4. Vidéo / Reel
            m = medias[0]
            octets = _lire_octets_locaux(m)
            if octets is not None:
                rep = await client.post(
                    f"{base}/{version}/{page_id}/videos",
                    data={"description": legende, "access_token": page_token},
                    files={"source": (m.display_name, octets, m.file_type)},
                )
            else:
                rep = await client.post(
                    f"{base}/{version}/{page_id}/videos",
                    data={
                        "description": legende,
                        "file_url": stockage.url_publique(m.storage_key),
                        "access_token": page_token,
                    },
                )
            if rep.status_code >= 400:
                msg, detail = _extraire_erreur_meta(rep)
                return ResultatDiffusion(ok=False, error_detail=detail, message=msg)
            post_id = str(rep.json().get("id", ""))
            lien = await _lire_permalink(client, base, version, post_id, page_token)
            return ResultatDiffusion(
                ok=True, post_external_id=post_id, permalink=lien, message="Vidéo publiée sur Facebook."
            )

    except httpx.TimeoutException:
        return ResultatDiffusion(
            ok=False,
            error_detail={"error": "timeout"},
            message="Meta n'a pas répondu dans le délai imparti lors de la publication.",
        )
    except httpx.HTTPError as err:
        return ResultatDiffusion(
            ok=False,
            error_detail={"error": str(err)},
            message=f"Erreur réseau lors de la publication sur Facebook : {err}",
        )
