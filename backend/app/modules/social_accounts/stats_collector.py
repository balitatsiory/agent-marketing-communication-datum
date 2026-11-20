"""Collecte en direct des statistiques de compte auprès de Meta Graph API."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.modules.platforms.models import SocialPlatform
from app.modules.social_accounts.verifier import _traduire_erreur_meta

TIMEOUT_SECONDES = 15.0


@dataclass
class ResultatCollecteStats:
    """Résultat normalisé d'un passage de collecte `statistics`."""

    ok: bool
    cause_code: str | None = None
    message_utilisateur: str = ""
    message_brut: str | None = None
    est_panne_passage: bool = False
    # Mapping : metric_date -> { code_mesure_iagora: valeur_entiere }
    valeurs_par_jour: dict[date, dict[str, int]] = field(default_factory=dict)
    raw_response: dict[str, Any] | None = None


def _date_meta(end_time: str | None) -> date:
    if not end_time:
        return date.today()
    try:
        return datetime.fromisoformat(end_time.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


async def collecter_statistiques_meta(
    plateforme: SocialPlatform,
    account_external_id: str,
    access_token: str,
    jours: int = 30,
) -> ResultatCollecteStats:
    """Interroge Meta Graph API pour relever les mesures du compte (Facebook / Instagram).

    Conserve la réponse brute pour `social_account_statistics.raw_response_json`.
    """
    base = (plateforme.api_base_url or "https://graph.facebook.com").rstrip("/")
    version = (plateforme.api_version or "v26.0").strip("/")
    maintenant = datetime.now(UTC)
    debut = int((maintenant - timedelta(days=jours)).timestamp())
    fin = int(maintenant.timestamp())

    valeurs: dict[date, dict[str, int]] = {}
    brut_combine: dict[str, Any] = {}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDES) as client:
            # 1. Stock d'abonnés instantané sur le nœud Page / IG User
            rep_node = await client.get(
                f"{base}/{version}/{account_external_id}",
                params={"fields": "id,followers_count", "access_token": access_token},
            )
            corps_node = rep_node.json() if rep_node.content else {}
            brut_combine["node"] = corps_node

            if rep_node.status_code >= 500:
                return ResultatCollecteStats(
                    ok=False,
                    cause_code="platform_unavailable",
                    message_utilisateur="Erreur temporaire côté Meta. Réessayez plus tard.",
                    message_brut=f"HTTP {rep_node.status_code} : {rep_node.text[:300]}",
                    est_panne_passage=True,
                )

            if rep_node.status_code >= 400 or "error" in corps_node:
                err = corps_node.get("error", {}) if isinstance(corps_node, dict) else {}
                cause_code, panne = _traduire_erreur_meta(err.get("code"), err.get("error_subcode"))
                msg = err.get("message") or rep_node.text[:300]
                return ResultatCollecteStats(
                    ok=False,
                    cause_code=cause_code,
                    message_utilisateur=f"Collecte refusée par Meta : {msg}",
                    message_brut=f"Meta error {err.get('code')} : {msg}",
                    est_panne_passage=panne,
                )

            if isinstance(corps_node, dict) and isinstance(corps_node.get("followers_count"), int):
                valeurs.setdefault(date.today(), {})["followers"] = int(
                    corps_node["followers_count"]
                )

            # 2. Séries quotidiennes via /{id}/insights (noms d'API vérifiés 2025-2026)
            if plateforme.code == "facebook":
                metriques = "page_follows,page_media_view,page_total_media_view_unique,page_post_engagements"
                mapping = {
                    "page_follows": "followers",
                    "page_media_view": "views",
                    "page_total_media_view_unique": "reach",
                    "page_post_engagements": "interactions",
                }
            else:
                metriques = "reach,views,total_interactions"
                mapping = {
                    "reach": "reach",
                    "views": "views",
                    "total_interactions": "interactions",
                }

            rep_ins = await client.get(
                f"{base}/{version}/{account_external_id}/insights",
                params={
                    "metric": metriques,
                    "period": "day",
                    "since": debut,
                    "until": fin,
                    "access_token": access_token,
                },
            )
            corps_ins = rep_ins.json() if rep_ins.content else {}
            brut_combine["insights"] = corps_ins

            if rep_ins.status_code == 200 and isinstance(corps_ins, dict):
                for item in corps_ins.get("data", []):
                    nom_api = item.get("name")
                    code_iagora = mapping.get(nom_api)
                    if not code_iagora:
                        continue
                    for pt in item.get("values", []):
                        v = pt.get("value")
                        if isinstance(v, (int, float)):
                            jour = _date_meta(pt.get("end_time"))
                            valeurs.setdefault(jour, {})[code_iagora] = int(v)

    except httpx.TimeoutException:
        return ResultatCollecteStats(
            ok=False,
            cause_code="platform_unavailable",
            message_utilisateur="Meta n'a pas répondu dans le délai imparti.",
            message_brut="Timeout HTTP lors de la collecte des statistiques Meta.",
            est_panne_passage=True,
        )
    except httpx.HTTPError as err:
        return ResultatCollecteStats(
            ok=False,
            cause_code="platform_unavailable",
            message_utilisateur="Impossible de joindre l'API Meta pour relever les statistiques.",
            message_brut=str(err),
            est_panne_passage=True,
        )

    nb_jours = len(valeurs)
    if nb_jours == 0:
        return ResultatCollecteStats(
            ok=True,
            message_utilisateur="Collecte terminée : aucune nouvelle donnée renvoyée par Meta.",
            valeurs_par_jour={},
            raw_response=brut_combine,
        )

    return ResultatCollecteStats(
        ok=True,
        message_utilisateur=f"Statistiques relevées auprès de {plateforme.label} ({nb_jours} jour(s) couvert(s)).",
        valeurs_par_jour=valeurs,
        raw_response=brut_combine,
    )


@dataclass
class PostMetaExterne:
    """Publication lue chez Meta avant insertion dans `social_posts`."""

    post_external_id: str
    permalink: str | None
    published_at: datetime | None


@dataclass
class ResultatImportPosts:
    """Résultat de la lecture des publications parues sur Meta."""

    ok: bool
    cause_code: str | None = None
    message_utilisateur: str = ""
    message_brut: str | None = None
    posts: list[PostMetaExterne] = field(default_factory=list)


def _horodatage_meta(valeur: str | None) -> datetime | None:
    if not valeur:
        return None
    try:
        # Meta renvoie parfois `+0000` sans deux-points (ex. 2026-11-18T09:30:00+0000).
        normalise = valeur.replace("Z", "+00:00")
        if len(normalise) >= 5 and normalise[-5] in ("+", "-") and normalise[-3] != ":":
            normalise = normalise[:-2] + ":" + normalise[-2:]
        return datetime.fromisoformat(normalise).astimezone(UTC)
    except ValueError:
        return None


async def importer_posts_meta(
    plateforme: SocialPlatform,
    account_external_id: str,
    access_token: str,
    limite: int = 50,
) -> ResultatImportPosts:
    """Lit les publications déjà parues sur une page Facebook ou un compte Instagram."""
    base = (plateforme.api_base_url or "https://graph.facebook.com").rstrip("/")
    version = (plateforme.api_version or "v26.0").strip("/")

    if plateforme.code == "facebook":
        endpoints = [
            (f"{base}/{version}/{account_external_id}/published_posts", "id,permalink_url,created_time"),
            (f"{base}/{version}/{account_external_id}/posts", "id,permalink_url,created_time"),
        ]
    else:
        endpoints = [
            (f"{base}/{version}/{account_external_id}/media", "id,permalink,timestamp"),
        ]

    derniere_erreur: ResultatImportPosts | None = None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDES) as client:
            for url, fields in endpoints:
                rep = await client.get(
                    url,
                    params={"fields": fields, "limit": limite, "access_token": access_token},
                )
                corps = rep.json() if rep.content else {}

                if rep.status_code >= 500:
                    return ResultatImportPosts(
                        ok=False,
                        cause_code="platform_unavailable",
                        message_utilisateur="Erreur temporaire côté Meta. Réessayez plus tard.",
                        message_brut=f"HTTP {rep.status_code} : {rep.text[:300]}",
                    )

                if rep.status_code >= 400 or "error" in corps:
                    err = corps.get("error", {}) if isinstance(corps, dict) else {}
                    cause_code, _ = _traduire_erreur_meta(err.get("code"), err.get("error_subcode"))
                    msg = err.get("message") or rep.text[:300]
                    derniere_erreur = ResultatImportPosts(
                        ok=False,
                        cause_code=cause_code,
                        message_utilisateur=f"Import refusé par Meta : {msg}",
                        message_brut=f"Meta error {err.get('code')} : {msg}",
                    )
                    continue

                donnees = corps.get("data", []) if isinstance(corps, dict) else []
                posts: list[PostMetaExterne] = []
                for item in donnees:
                    ext_id = item.get("id")
                    if not ext_id:
                        continue
                    posts.append(
                        PostMetaExterne(
                            post_external_id=str(ext_id),
                            permalink=item.get("permalink_url") or item.get("permalink"),
                            published_at=_horodatage_meta(
                                item.get("created_time") or item.get("timestamp")
                            ),
                        )
                    )
                if posts or url == endpoints[-1][0]:
                    return ResultatImportPosts(
                        ok=True,
                        message_utilisateur=f"{len(posts)} publication(s) lue(s) depuis {plateforme.label}.",
                        posts=posts,
                    )
    except httpx.TimeoutException:
        return ResultatImportPosts(
            ok=False,
            cause_code="platform_unavailable",
            message_utilisateur="Meta n'a pas répondu dans le délai imparti.",
            message_brut="Timeout HTTP lors de l'import des publications Meta.",
        )
    except httpx.HTTPError as err:
        return ResultatImportPosts(
            ok=False,
            cause_code="platform_unavailable",
            message_utilisateur="Impossible de joindre l'API Meta pour importer les publications.",
            message_brut=str(err),
        )

    return derniere_erreur or ResultatImportPosts(
        ok=True,
        message_utilisateur=f"Aucune publication trouvée sur {plateforme.label}.",
        posts=[],
    )
