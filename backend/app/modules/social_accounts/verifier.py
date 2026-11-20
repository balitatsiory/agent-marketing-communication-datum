"""Vérification en direct des comptes et jetons auprès des plateformes (Meta Graph API)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.core.config import get_settings
from app.modules.platforms.models import SocialPlatform

TIMEOUT_SECONDES = 10.0

PERMISSIONS_META_FACEBOOK = frozenset(
    {"pages_show_list", "pages_read_engagement", "pages_manage_posts"}
)
PERMISSIONS_META_INSTAGRAM = frozenset(
    {"instagram_basic", "instagram_content_publish", "instagram_manage_insights"}
)


@dataclass
class ResultatVerification:
    """Résultat normalisé d'un contrôle auprès d'une plateforme."""

    valide: bool
    cause_code: str | None = None
    message_utilisateur: str = ""
    message_brut: str | None = None
    est_panne_passage: bool = False
    nom_plateforme: str | None = None
    handle_plateforme: str | None = None
    url_plateforme: str | None = None
    permissions_accordees: list[str] | None = None
    expiration_jeton: datetime | None = None
    permissions_manquantes: list[str] = field(default_factory=list)


def _traduire_erreur_meta(code_meta: int | None, subcode: int | None) -> tuple[str, bool]:
    """Traduit un code d'erreur Meta vers (cause_code, est_panne_passage)."""
    if code_meta == 190:
        if subcode in (458, 460):
            return ("token_revoked", False)
        return ("token_expired", False)
    if code_meta in (10, 200, 294):
        return ("permission_missing", False)
    if code_meta in (4, 17, 32, 613):
        return ("rate_limited", True)
    if code_meta in (1, 2):
        return ("platform_unavailable", True)
    return ("unknown", False)


async def verifier_compte_meta(
    plateforme: SocialPlatform,
    account_external_id: str,
    access_token: str,
) -> ResultatVerification:
    """Interroge Meta Graph API pour vérifier l'existence du compte et la validité du jeton.

    Effectue d'abord `GET /{account_external_id}` pour confirmer que le jeton a bien
    accès à cette page/ce compte, puis `GET /debug_token` si META_APP_ID et
    META_APP_SECRET sont configurés afin de relever les scopes et l'expiration.
    """
    base = (plateforme.api_base_url or "https://graph.facebook.com").rstrip("/")
    version = (plateforme.api_version or "v26.0").strip("/")
    champs = "id,name,username,link" if plateforme.code == "facebook" else "id,name,username"
    url_compte = f"{base}/{version}/{account_external_id}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDES) as client:
            rep = await client.get(
                url_compte,
                params={"fields": champs, "access_token": access_token},
            )
    except httpx.TimeoutException:
        return ResultatVerification(
            valide=False,
            cause_code="platform_unavailable",
            message_utilisateur="Meta n'a pas répondu dans le délai imparti.",
            message_brut="Timeout HTTP lors de l'appel à Meta Graph API.",
            est_panne_passage=True,
        )
    except httpx.HTTPError as err:
        return ResultatVerification(
            valide=False,
            cause_code="platform_unavailable",
            message_utilisateur="Impossible de joindre l'API Meta pour le moment.",
            message_brut=str(err),
            est_panne_passage=True,
        )

    try:
        corps = rep.json()
    except ValueError:
        corps = {}

    if rep.status_code >= 500:
        return ResultatVerification(
            valide=False,
            cause_code="platform_unavailable",
            message_utilisateur="Erreur temporaire côté Meta. Réessayez plus tard.",
            message_brut=f"HTTP {rep.status_code} : {rep.text[:400]}",
            est_panne_passage=True,
        )

    if rep.status_code >= 400 or "error" in corps:
        err_meta = corps.get("error", {}) if isinstance(corps, dict) else {}
        code_meta = err_meta.get("code")
        subcode = err_meta.get("error_subcode")
        msg_meta = err_meta.get("message") or rep.text[:400]
        cause_code, panne_passage = _traduire_erreur_meta(code_meta, subcode)
        brut = (
            f"Meta error {code_meta}"
            + (f" (subcode {subcode})" if subcode else "")
            + f" : {msg_meta}"
        )
        return ResultatVerification(
            valide=False,
            cause_code=cause_code,
            message_utilisateur=f"Vérification refusée par Meta : {msg_meta}",
            message_brut=brut,
            est_panne_passage=panne_passage,
        )

    nom = corps.get("name")
    handle = corps.get("username")
    url_publique = corps.get("link")

    reglages = get_settings()
    scopes: list[str] | None = None
    expiration: datetime | None = None
    manquantes: list[str] = []

    if reglages.META_APP_ID and reglages.META_APP_SECRET and reglages.META_APP_SECRET.get_secret_value():
        debug_access_token = f"{reglages.META_APP_ID}|{reglages.META_APP_SECRET.get_secret_value()}"
    else:
        # En l'absence de META_APP_SECRET, Meta accepte aussi le jeton lui-même sur /debug_token.
        debug_access_token = access_token

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDES) as client:
            rep_dbg = await client.get(
                f"{base}/{version}/debug_token",
                params={"input_token": access_token, "access_token": debug_access_token},
            )
        if rep_dbg.status_code == 200:
            data_dbg = rep_dbg.json().get("data", {})
            if isinstance(data_dbg, dict):
                if data_dbg.get("is_valid") is False:
                    return ResultatVerification(
                        valide=False,
                        cause_code="token_expired",
                        message_utilisateur="Meta indique que ce jeton n'est plus valide.",
                        message_brut=str(data_dbg.get("error", "is_valid=false")),
                        est_panne_passage=False,
                    )
                raw_scopes = data_dbg.get("scopes")
                if isinstance(raw_scopes, list):
                    scopes = [str(s) for s in raw_scopes]
                    attendues = (
                        PERMISSIONS_META_FACEBOOK
                        if plateforme.code == "facebook"
                        else PERMISSIONS_META_INSTAGRAM
                    )
                    manquantes = sorted(attendues - set(scopes))
                exp_ts = data_dbg.get("expires_at")
                if isinstance(exp_ts, int) and exp_ts > 0:
                    expiration = datetime.fromtimestamp(exp_ts, tz=UTC)
    except httpx.HTTPError:
        pass

    if manquantes:
        return ResultatVerification(
            valide=False,
            cause_code="permission_missing",
            message_utilisateur=(
                "Jeton valide, mais des permissions manquent : " + ", ".join(manquantes) + "."
            ),
            message_brut="Permissions manquantes : " + ", ".join(manquantes),
            est_panne_passage=False,
            nom_plateforme=nom,
            handle_plateforme=handle,
            url_plateforme=url_publique,
            permissions_accordees=scopes,
            expiration_jeton=expiration,
            permissions_manquantes=manquantes,
        )

    cible_texte = nom or handle or account_external_id
    return ResultatVerification(
        valide=True,
        message_utilisateur=f"Connexion vérifiée auprès de {plateforme.label} ({cible_texte}).",
        nom_plateforme=nom,
        handle_plateforme=handle,
        url_plateforme=url_publique,
        permissions_accordees=scopes,
        expiration_jeton=expiration,
    )
