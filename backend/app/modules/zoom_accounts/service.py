"""Règles métier du module Comptes Zoom.

Sécurité :
- le Client Secret et le jeton d'accès sont chiffrés par `encrypt_token`
  (Fernet) avant toute écriture et déchiffrés au seul moment d'appeler Zoom ;
- aucune réponse de l'API ne les porte ;
- les journaux ne portent que des identifiants de lignes.

Les autres modules n'appellent jamais Zoom eux-mêmes : ils passent par
`call_api`, qui gère le jeton, son renouvellement et la traduction des refus.
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.security import decrypt_token, encrypt_token
from app.modules.users.models import User
from app.modules.zoom_accounts.constants import (
    CHECK_CONNECTION,
    CHECK_TOKEN_REFRESH,
    REQUIRED_SCOPES,
    TOKEN_EXPIRY_MARGIN_SECONDS,
)
from app.modules.zoom_accounts.models import (
    ZoomAccount,
    ZoomAccountCheck,
    ZoomAccountCredential,
)
from app.modules.zoom_accounts.schemas import (
    ZoomAccountCheckRead,
    ZoomAccountCreate,
    ZoomAccountRead,
    ZoomAccountUpdate,
    ZoomAccountVerifyRead,
    ZoomClientSecretSave,
    ZoomScopeRead,
)
from app.modules.zoom_accounts.zoom_client import (
    ZOOM_CODE_MISSING_SCOPE,
    ZoomClient,
    ZoomError,
)

logger = logging.getLogger(__name__)

APERCU_MASQUE = "••••••••"
VERIFICATIONS_PAR_DEFAUT = 20


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def _jeton_valide(compte: ZoomAccount) -> bool:
    if compte.access_token_encrypted is None or compte.access_token_expires_at is None:
        return False
    marge = timedelta(seconds=TOKEN_EXPIRY_MARGIN_SECONDS)
    return compte.access_token_expires_at - marge > datetime.now(UTC)


def _to_read(
    compte: ZoomAccount,
    secret: ZoomAccountCredential | None,
    auteur: User | None = None,
) -> ZoomAccountRead:
    accordes = compte.granted_scopes_json or []
    return ZoomAccountRead(
        id_zoom_accounts=compte.id_zoom_accounts,
        label=compte.label,
        host_email=compte.host_email,
        external_zoom_account_id=compte.external_zoom_account_id,
        client_id=compte.client_id,
        has_client_secret=secret is not None,
        client_secret_masked=secret.client_secret_masked if secret is not None else None,
        client_secret_obtained_at=secret.obtained_at if secret is not None else None,
        token_obtained_at=compte.access_token_obtained_at,
        token_expires_at=compte.access_token_expires_at,
        has_valid_token=_jeton_valide(compte),
        scopes=[
            ZoomScopeRead(scope=code, label=libelle, is_granted=code in accordes)
            for code, libelle in REQUIRED_SCOPES.items()
        ],
        granted_scopes=accordes,
        last_verified_at=compte.last_verified_at,
        last_verify_ok=compte.last_verify_ok,
        last_verify_message=compte.last_verify_message,
        created_by_name=auteur.nom_affiche if auteur is not None else None,
        created_at=compte.created_at,
        updated_at=compte.updated_at,
    )


async def _secret_actif(
    session: AsyncSession, id_zoom_accounts: int
) -> ZoomAccountCredential | None:
    return (
        await session.execute(
            select(ZoomAccountCredential).where(
                ZoomAccountCredential.id_zoom_accounts == id_zoom_accounts,
                ZoomAccountCredential.superseded_at.is_(None),
                ZoomAccountCredential.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _charger(session: AsyncSession, id_zoom_accounts: int) -> ZoomAccount:
    compte = await session.get(ZoomAccount, id_zoom_accounts)
    if compte is None or compte.deleted_at is not None:
        raise NotFoundError("Compte Zoom introuvable.")
    return compte


async def _fiche(session: AsyncSession, compte: ZoomAccount) -> ZoomAccountRead:
    # Recharge la ligne : `updated_at` est posé par un déclencheur.
    await session.refresh(compte)
    auteur = (
        await session.get(User, compte.id_users_created_by)
        if compte.id_users_created_by is not None
        else None
    )
    return _to_read(compte, await _secret_actif(session, compte.id_zoom_accounts), auteur)


async def list_accounts(session: AsyncSession) -> list[ZoomAccountRead]:
    """Comptes Zoom non archivés, par ordre alphabétique."""
    comptes = (
        (
            await session.execute(
                select(ZoomAccount)
                .where(ZoomAccount.deleted_at.is_(None))
                .order_by(ZoomAccount.label)
            )
        )
        .scalars()
        .all()
    )
    return [await _fiche(session, compte) for compte in comptes]


async def get_account(session: AsyncSession, id_zoom_accounts: int) -> ZoomAccountRead:
    """Fiche d'un compte.

    Raises:
        NotFoundError: compte inconnu ou archivé.
    """
    return await _fiche(session, await _charger(session, id_zoom_accounts))


async def list_labels(session: AsyncSession) -> dict[int, str]:
    """Libellé de chaque compte, archivés compris : leurs webinaires restent affichés."""
    lignes = await session.execute(select(ZoomAccount.id_zoom_accounts, ZoomAccount.label))
    return dict(lignes.all())


async def get_host_email(session: AsyncSession, id_zoom_accounts: int) -> str:
    """Adresse de l'hôte : celle que visent `/users/{userId}/meetings`."""
    return (await _charger(session, id_zoom_accounts)).host_email


async def list_checks(
    session: AsyncSession, id_zoom_accounts: int, limite: int = VERIFICATIONS_PAR_DEFAUT
) -> list[ZoomAccountCheckRead]:
    """Historique des vérifications, la plus récente en tête."""
    await _charger(session, id_zoom_accounts)
    lignes = (
        await session.execute(
            select(ZoomAccountCheck, User)
            .outerjoin(User, User.id_users == ZoomAccountCheck.id_users_checked_by)
            .where(ZoomAccountCheck.id_zoom_accounts == id_zoom_accounts)
            .order_by(
                ZoomAccountCheck.checked_at.desc(),
                ZoomAccountCheck.id_zoom_account_checks.desc(),
            )
            .limit(limite)
        )
    ).all()
    return [
        ZoomAccountCheckRead(
            id_zoom_account_checks=ligne.id_zoom_account_checks,
            kind=ligne.kind,  # type: ignore[arg-type]
            is_ok=ligne.is_ok,
            message=ligne.message,
            latency_ms=ligne.latency_ms,
            checked_at=ligne.checked_at,
            checked_by_name=auteur.nom_affiche if auteur is not None else None,
        )
        for ligne, auteur in lignes
    ]


# ---------------------------------------------------------------------------
# Jeton et appels à Zoom
# ---------------------------------------------------------------------------


async def _obtenir_jeton(session: AsyncSession, client: ZoomClient, compte: ZoomAccount) -> str:
    """Demande un jeton neuf à Zoom et le conserve, chiffré.

    Raises:
        ApiError: aucun secret enregistré.
        ZoomError: Zoom refuse ou ne répond pas.
    """
    secret = await _secret_actif(session, compte.id_zoom_accounts)
    if secret is None:
        raise ApiError("zoom_secret_missing", "Aucun Client Secret enregistré.", 409)
    jeton = await client.fetch_token(
        compte.external_zoom_account_id,
        compte.client_id,
        decrypt_token(secret.client_secret_encrypted),
    )
    maintenant = datetime.now(UTC)
    compte.access_token_encrypted = encrypt_token(jeton.access_token)
    compte.access_token_obtained_at = maintenant
    compte.access_token_expires_at = maintenant + timedelta(seconds=jeton.expires_in)
    compte.granted_scopes_json = list(jeton.scopes)
    await session.flush()
    return jeton.access_token


async def _appeler(
    session: AsyncSession,
    client: ZoomClient,
    compte: ZoomAccount,
    method: str,
    path: str,
    params: dict[str, str | int] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Appel porteur du jeton en cache, renouvelé une fois s'il est refusé."""
    if _jeton_valide(compte):
        assert compte.access_token_encrypted is not None  # garanti par _jeton_valide
        jeton = decrypt_token(compte.access_token_encrypted)
        try:
            return await client.request(method, path, jeton, params=params, json=json)
        except ZoomError as erreur:
            # Zoom peut invalider un jeton avant son terme (droits modifiés,
            # nouveau jeton demandé ailleurs) : on en redemande un, une fois.
            if not erreur.is_expired_token:
                raise
    jeton = await _obtenir_jeton(session, client, compte)
    return await client.request(method, path, jeton, params=params, json=json)


def _traduire(erreur: ZoomError) -> ApiError:
    """Refus de Zoom → erreur de l'API IAGORA.

    Jamais de 401 : l'interface l'interpréterait comme la fin de la session
    IAGORA et renverrait l'utilisateur à l'écran de connexion.
    """
    if erreur.zoom_code == ZOOM_CODE_MISSING_SCOPE:
        return ApiError(
            "zoom_scope_missing",
            f"L'application Zoom n'a pas le droit nécessaire : {erreur.message}",
            502,
        )
    if erreur.status_code in (401, 403):
        return ApiError("zoom_auth_failed", f"Zoom refuse l'accès : {erreur.message}", 502)
    if erreur.status_code == 404:
        return ApiError("zoom_not_found", f"Introuvable sur Zoom : {erreur.message}", 404)
    if erreur.status_code == 429:
        return ApiError(
            "zoom_rate_limited", "Quota d'appels Zoom atteint. Réessayer plus tard.", 429
        )
    if 400 <= erreur.status_code < 500:
        return ApiError("zoom_rejected", f"Zoom refuse la demande : {erreur.message}", 422)
    return ApiError("zoom_unavailable", erreur.message, 502)


async def call_api(
    session: AsyncSession,
    client: ZoomClient,
    id_zoom_accounts: int,
    method: str,
    path: str,
    params: dict[str, str | int] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Appelle l'API Zoom au nom d'un compte. Point d'entrée des autres modules.

    Raises:
        NotFoundError: compte inconnu ou archivé.
        ApiError: refus de Zoom, code `zoom_*`.
    """
    compte = await _charger(session, id_zoom_accounts)
    try:
        return await _appeler(session, client, compte, method, path, params=params, json=json)
    except ZoomError as erreur:
        logger.warning(
            "Zoom a refusé %s pour le compte %s : statut %s, code %s",
            method,
            id_zoom_accounts,
            erreur.status_code,
            erreur.zoom_code,
        )
        raise _traduire(erreur) from erreur


# ---------------------------------------------------------------------------
# Vérifications
# ---------------------------------------------------------------------------


async def _consigner(
    session: AsyncSession,
    compte: ZoomAccount,
    kind: str,
    est_ok: bool,
    message: str,
    latence_ms: int,
    par: User,
) -> ZoomAccountVerifyRead:
    """Écrit la ligne d'historique et l'état courant dans la même transaction."""
    session.add(
        ZoomAccountCheck(
            id_zoom_accounts=compte.id_zoom_accounts,
            kind=kind,
            is_ok=est_ok,
            message=message,
            latency_ms=latence_ms,
            id_users_checked_by=par.id_users,
        )
    )
    compte.last_verified_at = datetime.now(UTC)
    compte.last_verify_ok = est_ok
    compte.last_verify_message = message
    await session.flush()
    return ZoomAccountVerifyRead(
        verified=est_ok,
        message=message,
        latency_ms=latence_ms,
        account=await _fiche(session, compte),
    )


def _droits_manquants(compte: ZoomAccount) -> list[str]:
    accordes = set(compte.granted_scopes_json or [])
    return [code for code in REQUIRED_SCOPES if code not in accordes]


async def verify_account(
    session: AsyncSession, client: ZoomClient, id_zoom_accounts: int, par: User
) -> ZoomAccountVerifyRead:
    """Teste la connexion : jeton neuf, puis lecture réelle des réunions de l'hôte."""
    compte = await _charger(session, id_zoom_accounts)
    depart = time.monotonic()
    try:
        jeton = await _obtenir_jeton(session, client, compte)
        await client.request(
            "GET",
            f"/users/{compte.host_email}/meetings",
            jeton,
            params={"type": "scheduled", "page_size": 1},
        )
    except ZoomError as erreur:
        est_ok, message = False, _traduire(erreur).message
    else:
        manquants = _droits_manquants(compte)
        est_ok = True
        message = f"Connexion réussie : les réunions de {compte.host_email} sont accessibles."
        if manquants:
            message += " Droits Zoom absents : " + ", ".join(manquants) + "."
    latence = int((time.monotonic() - depart) * 1000)
    return await _consigner(session, compte, CHECK_CONNECTION, est_ok, message, latence, par)


async def refresh_token(
    session: AsyncSession, client: ZoomClient, id_zoom_accounts: int, par: User
) -> ZoomAccountVerifyRead:
    """Remplace le jeton d'accès par un neuf, sans autre appel."""
    compte = await _charger(session, id_zoom_accounts)
    depart = time.monotonic()
    try:
        await _obtenir_jeton(session, client, compte)
    except ZoomError as erreur:
        est_ok, message = False, _traduire(erreur).message
    else:
        assert compte.access_token_expires_at is not None
        est_ok = True
        message = (
            f"Nouveau jeton obtenu, valable jusqu'à {compte.access_token_expires_at:%H:%M} UTC."
        )
    latence = int((time.monotonic() - depart) * 1000)
    return await _consigner(session, compte, CHECK_TOKEN_REFRESH, est_ok, message, latence, par)


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


async def _refuser_doublon(
    session: AsyncSession, account_id: str, host_email: str, sauf: int | None = None
) -> None:
    requete = select(ZoomAccount.id_zoom_accounts).where(
        ZoomAccount.deleted_at.is_(None),
        ZoomAccount.external_zoom_account_id == account_id,
        ZoomAccount.host_email == host_email,
    )
    if sauf is not None:
        requete = requete.where(ZoomAccount.id_zoom_accounts != sauf)
    if (await session.execute(requete)).first() is not None:
        raise ConflictError(f"Ce compte Zoom est déjà raccordé pour {host_email}.")


def _nouveau_secret(id_zoom_accounts: int, secret: str, par: User) -> ZoomAccountCredential:
    return ZoomAccountCredential(
        id_zoom_accounts=id_zoom_accounts,
        client_secret_encrypted=encrypt_token(secret),
        client_secret_masked=APERCU_MASQUE,
        id_users_created_by=par.id_users,
    )


def _oublier_jeton(compte: ZoomAccount) -> None:
    """Un jeton obtenu avec d'anciens identifiants ne doit plus servir."""
    compte.access_token_encrypted = None
    compte.access_token_obtained_at = None
    compte.access_token_expires_at = None
    compte.granted_scopes_json = None
    compte.last_verified_at = None
    compte.last_verify_ok = None
    compte.last_verify_message = None


async def create_account(
    session: AsyncSession, client: ZoomClient, donnees: ZoomAccountCreate, par: User
) -> ZoomAccountVerifyRead:
    """Raccorde un compte Zoom et, sauf demande contraire, teste la connexion.

    Raises:
        ConflictError: même Account ID et même hôte déjà raccordés.
    """
    host_email = str(donnees.host_email).lower()
    await _refuser_doublon(session, donnees.external_zoom_account_id, host_email)
    compte = ZoomAccount(
        label=donnees.label,
        host_email=host_email,
        external_zoom_account_id=donnees.external_zoom_account_id,
        client_id=donnees.client_id,
        id_users_created_by=par.id_users,
    )
    session.add(compte)
    await session.flush()
    session.add(_nouveau_secret(compte.id_zoom_accounts, donnees.client_secret, par))
    await session.flush()
    logger.info("Compte Zoom %s raccordé", compte.id_zoom_accounts)

    if donnees.verify_immediately:
        return await verify_account(session, client, compte.id_zoom_accounts, par)
    return ZoomAccountVerifyRead(
        verified=False,
        message="Compte enregistré sans test de connexion.",
        latency_ms=0,
        account=await _fiche(session, compte),
    )


async def update_account(
    session: AsyncSession, id_zoom_accounts: int, donnees: ZoomAccountUpdate, par: User
) -> ZoomAccountRead:
    """Modifie les champs non secrets.

    Raises:
        NotFoundError, ConflictError.
    """
    compte = await _charger(session, id_zoom_accounts)
    champs = donnees.model_dump(exclude_unset=True, exclude_none=True)
    if "host_email" in champs:
        champs["host_email"] = str(champs["host_email"]).lower()
    await _refuser_doublon(
        session,
        champs.get("external_zoom_account_id", compte.external_zoom_account_id),
        champs.get("host_email", compte.host_email),
        sauf=id_zoom_accounts,
    )
    identifiants_changes = any(
        champs.get(nom, getattr(compte, nom)) != getattr(compte, nom)
        for nom in ("host_email", "external_zoom_account_id", "client_id")
    )
    for nom, valeur in champs.items():
        setattr(compte, nom, valeur)
    if identifiants_changes:
        _oublier_jeton(compte)
    compte.id_users_changed_by = par.id_users
    await session.flush()
    return await _fiche(session, compte)


async def replace_client_secret(
    session: AsyncSession,
    client: ZoomClient,
    id_zoom_accounts: int,
    donnees: ZoomClientSecretSave,
    par: User,
) -> ZoomAccountVerifyRead:
    """Remplace le Client Secret ; l'ancien est marqué remplacé, jamais effacé."""
    compte = await _charger(session, id_zoom_accounts)
    ancien = await _secret_actif(session, id_zoom_accounts)
    if ancien is not None:
        ancien.superseded_at = datetime.now(UTC)
        # L'index unique n'admet qu'un secret actif : il faut écrire le retrait
        # avant d'ajouter le suivant.
        await session.flush()
    session.add(_nouveau_secret(id_zoom_accounts, donnees.client_secret, par))
    _oublier_jeton(compte)
    compte.id_users_changed_by = par.id_users
    await session.flush()

    if donnees.verify_immediately:
        return await verify_account(session, client, id_zoom_accounts, par)
    return ZoomAccountVerifyRead(
        verified=False,
        message="Secret remplacé sans test de connexion.",
        latency_ms=0,
        account=await _fiche(session, compte),
    )


async def archive_account(session: AsyncSession, id_zoom_accounts: int, par: User) -> None:
    """Archive le compte, révoque son secret et oublie son jeton."""
    compte = await _charger(session, id_zoom_accounts)
    secret = await _secret_actif(session, id_zoom_accounts)
    if secret is not None:
        secret.revoked_at = datetime.now(UTC)
    _oublier_jeton(compte)
    compte.deleted_at = datetime.now(UTC)
    compte.id_users_changed_by = par.id_users
    await session.flush()
    logger.info("Compte Zoom %s archivé", id_zoom_accounts)
