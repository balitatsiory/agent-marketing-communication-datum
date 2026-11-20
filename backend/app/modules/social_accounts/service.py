"""Règles métier du module Comptes réseaux sociaux."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.security import decrypt_token, encrypt_token
from app.modules.platforms.models import SocialPlatform
from app.modules.social_accounts.constants import STATUT_ACTIF, STATUT_DEBRANCHE
from app.modules.social_accounts.models import (
    SocialAccount,
    SocialAccountErrorCause,
    SocialAccountStatistic,
    SocialAccountStatisticType,
    SocialAccountStatisticValue,
    SocialAccountStatus,
    SocialAccountSync,
    SocialAccountToken,
    SocialPlatformStatisticType,
    SocialPost,
)
from app.modules.social_accounts.schemas import (
    PlatformMetricRead,
    SocialAccountCreate,
    SocialAccountErrorCauseRead,
    SocialAccountMetricsSummary,
    SocialAccountRead,
    SocialAccountReconnect,
    SocialAccountStatisticsRead,
    SocialAccountSyncPostsRead,
    SocialAccountSyncRead,
    SocialAccountSyncStatsRead,
    SocialAccountTokenRead,
    SocialAccountVerifyRead,
    SocialPlatformRead,
    SocialPostRead,
    SocialStatisticTypeRead,
    StatisticPointRead,
)
from app.modules.social_accounts.stats_collector import (
    collecter_statistiques_meta,
    importer_posts_meta,
)
from app.modules.social_accounts.verifier import verifier_compte_meta
from app.modules.users.models import User


async def lister_plateformes(session: AsyncSession) -> list[SocialPlatformRead]:
    """Renvoie les plateformes connues et les mesures que chacune expose."""
    plateformes = list(
        (await session.execute(select(SocialPlatform).order_by(SocialPlatform.sort_order)))
        .scalars()
        .all()
    )

    lignes_mesures = (
        await session.execute(
            select(
                SocialPlatformStatisticType.id_social_platforms,
                SocialPlatformStatisticType.platform_metric_name,
                SocialAccountStatisticType.code,
                SocialAccountStatisticType.label,
                SocialAccountStatisticType.nature,
                SocialAccountStatisticType.is_summable,
            )
            .join(
                SocialAccountStatisticType,
                SocialAccountStatisticType.id_social_account_statistic_types
                == SocialPlatformStatisticType.id_social_account_statistic_types,
            )
            .order_by(SocialAccountStatisticType.sort_order)
        )
    ).all()

    par_plateforme: dict[int, list[PlatformMetricRead]] = {}
    for row in lignes_mesures:
        par_plateforme.setdefault(row.id_social_platforms, []).append(
            PlatformMetricRead(
                code=row.code,
                label=row.label,
                nature=row.nature,
                is_summable=row.is_summable,
                platform_metric_name=row.platform_metric_name,
            )
        )

    return [
        SocialPlatformRead.model_validate(p).model_copy(
            update={"supported_metrics": par_plateforme.get(p.id_social_platforms, [])}
        )
        for p in plateformes
    ]


async def lister_statuts(session: AsyncSession) -> list[SocialAccountStatus]:
    """Renvoie les états possibles d'un compte, dans l'ordre d'affichage."""
    return list(
        (
            await session.execute(
                select(SocialAccountStatus).order_by(SocialAccountStatus.sort_order)
            )
        )
        .scalars()
        .all()
    )


async def _statut_par_code(session: AsyncSession, code: str) -> SocialAccountStatus:
    statut = (
        await session.execute(
            select(SocialAccountStatus).where(SocialAccountStatus.code == code)
        )
    ).scalar_one_or_none()
    if statut is None:
        raise ApiError("unknown_status", f"État de compte introuvable : {code}.", 500)
    return statut


async def _assembler_comptes(
    session: AsyncSession, comptes: list[SocialAccount]
) -> list[SocialAccountRead]:
    """Compose la vue de liste avec plateforme, statut, parent, jeton actif et synthèse stats."""
    if not comptes:
        return []

    ids = [c.id_social_accounts for c in comptes]

    plateformes = {
        p.id_social_platforms: p
        for p in (await session.execute(select(SocialPlatform))).scalars().all()
    }
    statuts = {
        s.id_social_account_statuses: s
        for s in (await session.execute(select(SocialAccountStatus))).scalars().all()
    }
    causes = {
        e.id_social_account_error_causes: e
        for e in (await session.execute(select(SocialAccountErrorCause))).scalars().all()
    }

    parent_ids = {c.id_social_accounts_parent for c in comptes if c.id_social_accounts_parent}
    parents: dict[int, SocialAccount] = {}
    if parent_ids:
        parents = {
            p.id_social_accounts: p
            for p in (
                await session.execute(
                    select(SocialAccount).where(SocialAccount.id_social_accounts.in_(parent_ids))
                )
            )
            .scalars()
            .all()
        }

    jetons_actifs = {
        t.id_social_accounts: t
        for t in (
            await session.execute(
                select(SocialAccountToken).where(
                    SocialAccountToken.id_social_accounts.in_(ids),
                    SocialAccountToken.superseded_at.is_(None),
                    SocialAccountToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    # Nombre de publications parues sur les 30 derniers jours.
    depuis_dt = datetime.now(UTC) - timedelta(days=30)
    posts_rows = (
        await session.execute(
            select(SocialPost.id_social_accounts, func.count(SocialPost.id_social_posts))
            .where(
                SocialPost.id_social_accounts.in_(ids),
                SocialPost.published_at >= depuis_dt,
                SocialPost.deleted_on_platform_at.is_(None),
            )
            .group_by(SocialPost.id_social_accounts)
        )
    ).all()
    posts_par_compte = {int(r[0]): int(r[1]) for r in posts_rows}

    # Dernier relevé par (compte, jour) sur les 30 derniers jours :
    # actualiser en cours de journée n'écrase rien, on garde le relevé le plus récent du jour.
    depuis_date = date.today() - timedelta(days=30)
    dernier_par_jour = (
        select(
            SocialAccountStatistic.id_social_account_statistics,
            SocialAccountStatistic.id_social_accounts,
            SocialAccountStatistic.metric_date,
            SocialAccountStatistic.collected_at,
        )
        .distinct(SocialAccountStatistic.id_social_accounts, SocialAccountStatistic.metric_date)
        .where(
            SocialAccountStatistic.id_social_accounts.in_(ids),
            SocialAccountStatistic.metric_date >= depuis_date,
        )
        .order_by(
            SocialAccountStatistic.id_social_accounts,
            SocialAccountStatistic.metric_date,
            SocialAccountStatistic.collected_at.desc(),
        )
        .subquery()
    )

    stats_rows = (
        await session.execute(
            select(
                dernier_par_jour.c.id_social_accounts,
                dernier_par_jour.c.metric_date,
                dernier_par_jour.c.collected_at,
                SocialAccountStatisticType.code,
                SocialAccountStatisticValue.value,
            )
            .join(
                SocialAccountStatisticValue,
                SocialAccountStatisticValue.id_social_account_statistics
                == dernier_par_jour.c.id_social_account_statistics,
            )
            .join(
                SocialAccountStatisticType,
                SocialAccountStatisticType.id_social_account_statistic_types
                == SocialAccountStatisticValue.id_social_account_statistic_types,
            )
        )
    ).all()

    # Agrégation par compte : stock/non-sommable = valeur du jour le plus récent ;
    # flux sommable (views, interactions) = cumul sur la fenêtre de 30 jours.
    stats_par_compte: dict[int, SocialAccountMetricsSummary] = {
        cid: SocialAccountMetricsSummary(posts_30d=posts_par_compte.get(cid, 0)) for cid in ids
    }
    derniere_date_stock: dict[tuple[int, str], date] = {}
    for row in stats_rows:
        cid = int(row.id_social_accounts)
        summary = stats_par_compte[cid]
        mdate: date = row.metric_date
        cat: datetime = row.collected_at
        code: str = row.code
        val = int(row.value)

        if summary.last_metric_date is None or mdate > summary.last_metric_date:
            summary.last_metric_date = mdate
        if summary.last_collected_at is None or cat > summary.last_collected_at:
            summary.last_collected_at = cat

        if code in ("followers", "reach"):
            cle = (cid, code)
            if cle not in derniere_date_stock or mdate >= derniere_date_stock[cle]:
                derniere_date_stock[cle] = mdate
                setattr(summary, code, val)
        elif code == "views":
            summary.views_30d = (summary.views_30d or 0) + val
        elif code == "interactions":
            summary.interactions_30d = (summary.interactions_30d or 0) + val

    resultats: list[SocialAccountRead] = []
    for c in comptes:
        plat = plateformes[c.id_social_platforms]
        statut = statuts[c.id_social_account_statuses_current]
        cause_obj = (
            causes.get(c.id_social_account_error_causes_current)
            if c.id_social_account_error_causes_current
            else None
        )
        parent = parents.get(c.id_social_accounts_parent) if c.id_social_accounts_parent else None
        jeton = jetons_actifs.get(c.id_social_accounts)

        resultats.append(
            SocialAccountRead(
                id_social_accounts=c.id_social_accounts,
                platform_code=plat.code,
                platform_label=plat.label,
                status_code=statut.code,
                status_label=statut.label,
                id_social_accounts_parent=c.id_social_accounts_parent,
                parent_display_name=parent.account_display_name if parent else None,
                parent_platform_code=(
                    plateformes[parent.id_social_platforms].code if parent else None
                ),
                account_external_id=c.account_external_id,
                account_display_name=c.account_display_name,
                account_username=c.account_username,
                profile_url=c.profile_url,
                credential_mode=c.credential_mode,
                error_cause=(
                    SocialAccountErrorCauseRead.model_validate(cause_obj) if cause_obj else None
                ),
                current_error_message=c.current_error_message,
                has_active_token=jeton is not None,
                token_kind=jeton.token_kind if jeton else None,
                token_expires_at=jeton.access_expires_at if jeton else None,
                metrics=stats_par_compte[c.id_social_accounts],
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return resultats


async def lister_comptes(
    session: AsyncSession,
    status_code: str | None = None,
    platform_code: str | None = None,
) -> list[SocialAccountRead]:
    """Liste les comptes non archivés, triés par plateforme puis nom."""
    requete = (
        select(SocialAccount)
        .join(SocialPlatform, SocialPlatform.id_social_platforms == SocialAccount.id_social_platforms)
        .join(
            SocialAccountStatus,
            SocialAccountStatus.id_social_account_statuses
            == SocialAccount.id_social_account_statuses_current,
        )
        .where(SocialAccount.deleted_at.is_(None))
        .order_by(SocialPlatform.sort_order, SocialAccount.account_display_name)
    )
    if status_code:
        requete = requete.where(SocialAccountStatus.code == status_code)
    if platform_code:
        requete = requete.where(SocialPlatform.code == platform_code)

    comptes = list((await session.execute(requete)).scalars().all())
    return await _assembler_comptes(session, comptes)


async def creer_compte(
    session: AsyncSession, donnees: SocialAccountCreate, par: User
) -> SocialAccountRead:
    """Raccorde un nouveau compte réseau social (saisie manuelle)."""
    plateforme = (
        await session.execute(
            select(SocialPlatform).where(SocialPlatform.code == donnees.platform_code.strip())
        )
    ).scalar_one_or_none()
    if plateforme is None:
        raise NotFoundError(f"Plateforme inconnue : « {donnees.platform_code} ».")

    parent_id: int | None = None
    if donnees.credential_mode == "inherited":
        parent = (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.id_social_accounts == donnees.id_social_accounts_parent,
                    SocialAccount.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise NotFoundError("Le compte parent sélectionné est introuvable.")
        if parent.credential_mode != "own":
            raise ApiError(
                "invalid_parent_account",
                "Le compte parent doit détenir ses propres clés (mode « own »).",
            )
        parent_id = parent.id_social_accounts

    statut_connecte = await _statut_par_code(session, STATUT_ACTIF)

    compte = SocialAccount(
        id_social_platforms=plateforme.id_social_platforms,
        id_social_account_statuses_current=statut_connecte.id_social_account_statuses,
        id_social_accounts_parent=parent_id,
        account_external_id=donnees.account_external_id.strip(),
        account_display_name=donnees.account_display_name.strip(),
        account_username=donnees.account_username.strip() if donnees.account_username else None,
        profile_url=donnees.profile_url.strip() if donnees.profile_url else None,
        credential_mode=donnees.credential_mode,
        id_users_created_by=par.id_users,
        id_users_changed_by=par.id_users,
    )
    session.add(compte)

    try:
        await session.flush()
    except IntegrityError as erreur:
        await session.rollback()
        raise ConflictError(
            "Un compte portant cet identifiant externe est déjà raccordé sur cette plateforme."
        ) from erreur

    if donnees.credential_mode == "own":
        assert donnees.access_token is not None
        jeton = SocialAccountToken(
            id_social_accounts=compte.id_social_accounts,
            access_token_encrypted=encrypt_token(donnees.access_token.strip()),
            refresh_token_encrypted=(
                encrypt_token(donnees.refresh_token.strip()) if donnees.refresh_token else None
            ),
            access_expires_at=donnees.access_expires_at,
            refresh_expires_at=donnees.refresh_expires_at,
            token_kind=donnees.token_kind.strip() if donnees.token_kind else None,
            obtained_at=donnees.obtained_at or datetime.now(UTC),
            id_users_created_by=par.id_users,
        )
        session.add(jeton)

    await session.commit()
    await session.refresh(compte)
    return (await _assembler_comptes(session, [compte]))[0]


async def reconnecter_compte(
    session: AsyncSession, id_compte: int, donnees: SocialAccountReconnect, par: User
) -> SocialAccountRead:
    """Enregistre une nouvelle délivrance de clés et remet le compte à l'état connecté."""
    compte = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.id_social_accounts == id_compte,
                SocialAccount.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if compte is None:
        raise NotFoundError("Compte réseau social introuvable.")

    if compte.credential_mode == "inherited":
        raise ApiError(
            "inherited_account_reconnect",
            "Ce compte hérite des clés de son compte parent : reconnectez le compte parent.",
        )

    maintenant = datetime.now(UTC)

    # Marquer l'ancienne délivrance active comme remplacée dans la même transaction
    # pour respecter l'index partiel unique `uq_social_account_tokens_actif`.
    anciens = list(
        (
            await session.execute(
                select(SocialAccountToken).where(
                    SocialAccountToken.id_social_accounts == id_compte,
                    SocialAccountToken.superseded_at.is_(None),
                    SocialAccountToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for ancien in anciens:
        ancien.superseded_at = maintenant
    await session.flush()

    session.add(
        SocialAccountToken(
            id_social_accounts=id_compte,
            access_token_encrypted=encrypt_token(donnees.access_token.strip()),
            refresh_token_encrypted=(
                encrypt_token(donnees.refresh_token.strip()) if donnees.refresh_token else None
            ),
            access_expires_at=donnees.access_expires_at,
            refresh_expires_at=donnees.refresh_expires_at,
            token_kind=donnees.token_kind.strip() if donnees.token_kind else None,
            obtained_at=donnees.obtained_at or maintenant,
            id_users_created_by=par.id_users,
        )
    )

    statut_connecte = await _statut_par_code(session, STATUT_ACTIF)
    compte.id_social_account_statuses_current = statut_connecte.id_social_account_statuses
    compte.id_social_account_error_causes_current = None
    compte.current_error_message = None
    compte.id_users_changed_by = par.id_users

    await session.commit()
    await session.refresh(compte)
    return (await _assembler_comptes(session, [compte]))[0]


async def debrancher_compte(
    session: AsyncSession, id_compte: int, par: User
) -> SocialAccountRead:
    """Débranche volontairement un compte : révoque ses clés et conserve son historique."""
    compte = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.id_social_accounts == id_compte,
                SocialAccount.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if compte is None:
        raise NotFoundError("Compte réseau social introuvable.")

    maintenant = datetime.now(UTC)
    actifs = list(
        (
            await session.execute(
                select(SocialAccountToken).where(
                    SocialAccountToken.id_social_accounts == id_compte,
                    SocialAccountToken.superseded_at.is_(None),
                    SocialAccountToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for jeton in actifs:
        jeton.revoked_at = maintenant
        jeton.access_token_encrypted = ""
        jeton.refresh_token_encrypted = None

    statut_deconnecte = await _statut_par_code(session, STATUT_DEBRANCHE)
    compte.id_social_account_statuses_current = statut_deconnecte.id_social_account_statuses
    compte.id_social_account_error_causes_current = None
    compte.current_error_message = None
    compte.id_users_changed_by = par.id_users

    await session.commit()
    await session.refresh(compte)
    return (await _assembler_comptes(session, [compte]))[0]


async def _cause_par_code(
    session: AsyncSession, code: str
) -> SocialAccountErrorCause | None:
    cause = (
        await session.execute(
            select(SocialAccountErrorCause).where(SocialAccountErrorCause.code == code)
        )
    ).scalar_one_or_none()
    if cause is not None:
        return cause
    if code == "token_revoked":
        return (
            await session.execute(
                select(SocialAccountErrorCause).where(
                    SocialAccountErrorCause.code == "authorization_removed"
                )
            )
        ).scalar_one_or_none()
    return (
        await session.execute(
            select(SocialAccountErrorCause).where(SocialAccountErrorCause.code == "unknown")
        )
    ).scalar_one_or_none()


async def verifier_compte(
    session: AsyncSession, id_compte: int, par: User
) -> SocialAccountVerifyRead:
    """Vérifie en direct le jeton et l'identifiant du compte auprès de Meta Graph API.

    Journalise le passage dans `social_account_syncs` (`sync_kind='token_check'`) et
    met à jour l'état du compte selon les règles portées par `social_account_error_causes`.
    """
    compte = await _charger_compte(session, id_compte)

    plateforme = await session.get(SocialPlatform, compte.id_social_platforms)
    if plateforme is None:
        raise NotFoundError("Plateforme introuvable.")

    if plateforme.code not in ("facebook", "instagram"):
        raise ApiError(
            "verification_not_supported",
            f"La vérification en direct n'est pas encore branchée pour {plateforme.label}. "
            "Seuls Facebook et Instagram (Meta Graph API) sont vérifiables aujourd'hui.",
            400,
        )

    id_detenteur = (
        compte.id_social_accounts_parent
        if compte.credential_mode == "inherited" and compte.id_social_accounts_parent
        else compte.id_social_accounts
    )
    jeton = (
        await session.execute(
            select(SocialAccountToken).where(
                SocialAccountToken.id_social_accounts == id_detenteur,
                SocialAccountToken.superseded_at.is_(None),
                SocialAccountToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if jeton is None or not jeton.access_token_encrypted:
        raise ApiError(
            "no_active_token",
            "Aucun jeton actif trouvé pour ce compte (ou son compte parent).",
            400,
        )

    clair = decrypt_token(jeton.access_token_encrypted)

    # Fermer d'éventuels passages token_check abandonnés avant d'ouvrir le nouveau.
    maintenant = datetime.now(UTC)
    abandonnes = list(
        (
            await session.execute(
                select(SocialAccountSync).where(
                    SocialAccountSync.id_social_accounts == id_compte,
                    SocialAccountSync.sync_kind == "token_check",
                    SocialAccountSync.finished_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for anc in abandonnes:
        anc.finished_at = maintenant
        anc.sync_outcome = "failed"
    await session.flush()

    passage = SocialAccountSync(
        id_social_accounts=id_compte,
        sync_kind="token_check",
        started_at=maintenant,
        id_users_triggered_by=par.id_users,
    )
    session.add(passage)
    await session.flush()

    resultat = await verifier_compte_meta(plateforme, compte.account_external_id, clair)
    fin = datetime.now(UTC)

    if resultat.permissions_accordees is not None:
        jeton.granted_api_permissions_json = {"scopes": resultat.permissions_accordees}
    if resultat.expiration_jeton is not None:
        jeton.access_expires_at = resultat.expiration_jeton

    if resultat.valide:
        statut_actif = await _statut_par_code(session, STATUT_ACTIF)
        # Poser finished_at et sync_outcome ensemble pour respecter la contrainte
        # `(finished_at IS NULL) = (sync_outcome IS NULL)` avant tout autoflush.
        passage.finished_at = fin
        passage.sync_outcome = "succeeded"
        compte.id_social_account_statuses_current = statut_actif.id_social_account_statuses
        compte.id_social_account_error_causes_current = None
        compte.current_error_message = None
        if not compte.profile_url and resultat.url_plateforme:
            compte.profile_url = resultat.url_plateforme
        compte.id_users_changed_by = par.id_users
    else:
        cause = await _cause_par_code(session, resultat.cause_code or "unknown")
        passage.finished_at = fin
        if resultat.est_panne_passage:
            passage.sync_outcome = "failed"
            passage.id_social_account_error_causes = (
                cause.id_social_account_error_causes if cause else None
            )
        else:
            # Une vérification qui constate proprement un jeton invalide vaut succeeded.
            passage.sync_outcome = "succeeded"

        if cause is not None and cause.writes_on_account:
            compte.id_social_account_error_causes_current = cause.id_social_account_error_causes
            compte.current_error_message = resultat.message_brut
            if cause.id_social_account_statuses_target is not None:
                compte.id_social_account_statuses_current = cause.id_social_account_statuses_target
            compte.id_users_changed_by = par.id_users
        elif resultat.message_brut and not resultat.est_panne_passage:
            compte.current_error_message = resultat.message_brut

    await session.commit()
    await session.refresh(compte)
    compte_lu = (await _assembler_comptes(session, [compte]))[0]

    return SocialAccountVerifyRead(
        verified=resultat.valide,
        message=resultat.message_utilisateur,
        platform_name=resultat.nom_plateforme,
        platform_username=resultat.handle_plateforme,
        platform_url=resultat.url_plateforme,
        granted_permissions=resultat.permissions_accordees,
        missing_permissions=resultat.permissions_manquantes,
        raw_error=resultat.message_brut,
        account=compte_lu,
    )


async def _charger_compte(session: AsyncSession, id_compte: int) -> SocialAccount:
    if id_compte < 1 or id_compte > 2_147_483_647:
        raise NotFoundError("Compte réseau social introuvable.")
    compte = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.id_social_accounts == id_compte,
                SocialAccount.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if compte is None:
        raise NotFoundError("Compte réseau social introuvable.")
    return compte


async def _noms_utilisateurs(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(User.id_users, User.first_name, User.last_name).where(User.id_users.in_(ids))
        )
    ).all()
    return {int(r[0]): f"{r[1]} {r[2]}".strip() for r in rows}


async def obtenir_compte(session: AsyncSession, id_compte: int) -> SocialAccountRead:
    """Lit la fiche détaillée d'un compte réseau social."""
    compte = await _charger_compte(session, id_compte)
    return (await _assembler_comptes(session, [compte]))[0]


async def lister_statistiques_compte(
    session: AsyncSession, id_compte: int, jours: int = 30
) -> SocialAccountStatisticsRead:
    """Renvoie les séries quotidiennes (dernier relevé par jour) sur `jours` jours."""
    compte = await _charger_compte(session, id_compte)
    plateforme = await session.get(SocialPlatform, compte.id_social_platforms)

    types_mesures = list(
        (
            await session.execute(
                select(SocialAccountStatisticType).order_by(SocialAccountStatisticType.sort_order)
            )
        )
        .scalars()
        .all()
    )
    supportes = {
        row.id_social_account_statistic_types: row.platform_metric_name
        for row in (
            await session.execute(
                select(SocialPlatformStatisticType).where(
                    SocialPlatformStatisticType.id_social_platforms == compte.id_social_platforms
                )
            )
        )
        .scalars()
        .all()
    }

    metric_types = [
        SocialStatisticTypeRead(
            code=t.code,
            label=t.label,
            description=t.description,
            nature=t.nature,
            is_summable=t.is_summable,
            supported_by_platform=bool(
                plateforme
                and plateforme.supports_account_metrics
                and t.id_social_account_statistic_types in supportes
            ),
            platform_metric_name=supportes.get(t.id_social_account_statistic_types),
        )
        for t in types_mesures
    ]

    depuis = date.today() - timedelta(days=jours)
    dernier_par_jour = (
        select(
            SocialAccountStatistic.id_social_account_statistics,
            SocialAccountStatistic.metric_date,
            SocialAccountStatistic.collected_at,
        )
        .distinct(SocialAccountStatistic.metric_date)
        .where(
            SocialAccountStatistic.id_social_accounts == id_compte,
            SocialAccountStatistic.metric_date >= depuis,
        )
        .order_by(
            SocialAccountStatistic.metric_date,
            SocialAccountStatistic.collected_at.desc(),
        )
        .subquery()
    )

    lignes = (
        await session.execute(
            select(
                dernier_par_jour.c.metric_date,
                dernier_par_jour.c.collected_at,
                SocialAccountStatisticType.code,
                SocialAccountStatisticValue.value,
            )
            .join(
                SocialAccountStatisticValue,
                SocialAccountStatisticValue.id_social_account_statistics
                == dernier_par_jour.c.id_social_account_statistics,
            )
            .join(
                SocialAccountStatisticType,
                SocialAccountStatisticType.id_social_account_statistic_types
                == SocialAccountStatisticValue.id_social_account_statistic_types,
            )
            .order_by(dernier_par_jour.c.metric_date.asc())
        )
    ).all()

    series: dict[str, list[StatisticPointRead]] = {t.code: [] for t in types_mesures}
    for row in lignes:
        series.setdefault(row.code, []).append(
            StatisticPointRead(
                metric_date=row.metric_date,
                collected_at=row.collected_at,
                value=int(row.value),
            )
        )

    return SocialAccountStatisticsRead(days=jours, metric_types=metric_types, series=series)


async def synchroniser_statistiques_compte(
    session: AsyncSession, id_compte: int, par: User
) -> SocialAccountSyncStatsRead:
    """Lance une collecte manuelle des statistiques de compte auprès de Meta Graph API."""
    compte = await _charger_compte(session, id_compte)
    plateforme = await session.get(SocialPlatform, compte.id_social_platforms)
    if plateforme is None:
        raise NotFoundError("Plateforme introuvable.")

    if not plateforme.supports_account_metrics:
        raise ApiError(
            "metrics_not_supported",
            f"{plateforme.label} n'expose pas de statistiques de compte.",
            400,
        )
    if plateforme.code not in ("facebook", "instagram"):
        raise ApiError(
            "stats_sync_not_supported",
            f"La collecte en direct des statistiques n'est pas encore branchée pour {plateforme.label}. "
            "Seuls Facebook et Instagram (Meta Graph API) sont collectables aujourd'hui.",
            400,
        )

    id_detenteur = (
        compte.id_social_accounts_parent
        if compte.credential_mode == "inherited" and compte.id_social_accounts_parent
        else compte.id_social_accounts
    )
    jeton = (
        await session.execute(
            select(SocialAccountToken).where(
                SocialAccountToken.id_social_accounts == id_detenteur,
                SocialAccountToken.superseded_at.is_(None),
                SocialAccountToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if jeton is None or not jeton.access_token_encrypted:
        raise ApiError(
            "no_active_token",
            "Aucun jeton actif trouvé pour ce compte (ou son compte parent).",
            400,
        )

    clair = decrypt_token(jeton.access_token_encrypted)

    maintenant = datetime.now(UTC)
    abandonnes = list(
        (
            await session.execute(
                select(SocialAccountSync).where(
                    SocialAccountSync.id_social_accounts == id_compte,
                    SocialAccountSync.sync_kind == "statistics",
                    SocialAccountSync.finished_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for anc in abandonnes:
        anc.finished_at = maintenant
        anc.sync_outcome = "failed"
    await session.flush()

    passage = SocialAccountSync(
        id_social_accounts=id_compte,
        sync_kind="statistics",
        started_at=maintenant,
        id_users_triggered_by=par.id_users,
    )
    session.add(passage)
    await session.flush()

    res = await collecter_statistiques_meta(plateforme, compte.account_external_id, clair)
    fin = datetime.now(UTC)

    if res.ok:
        types_par_code = {
            t.code: t.id_social_account_statistic_types
            for t in (await session.execute(select(SocialAccountStatisticType))).scalars().all()
        }
        dates_tri = sorted(res.valeurs_par_jour.keys())
        for jour in dates_tri:
            mesures = res.valeurs_par_jour[jour]
            if not mesures:
                continue
            releve = SocialAccountStatistic(
                id_social_accounts=id_compte,
                metric_date=jour,
                collected_at=fin,
                raw_response_json=res.raw_response if jour == dates_tri[-1] else None,
            )
            session.add(releve)
            await session.flush()
            for code_m, val in mesures.items():
                id_type = types_par_code.get(code_m)
                if id_type is not None:
                    session.add(
                        SocialAccountStatisticValue(
                            id_social_account_statistics=releve.id_social_account_statistics,
                            id_social_account_statistic_types=id_type,
                            value=val,
                        )
                    )
        passage.finished_at = fin
        passage.sync_outcome = "succeeded" if dates_tri else "empty"
        passage.covered_until_date = dates_tri[-1] if dates_tri else None
    else:
        cause = await _cause_par_code(session, res.cause_code or "unknown")
        passage.finished_at = fin
        passage.sync_outcome = "failed"
        passage.id_social_account_error_causes = (
            cause.id_social_account_error_causes if cause else None
        )
        if cause is not None and cause.writes_on_account:
            compte.id_social_account_error_causes_current = cause.id_social_account_error_causes
            compte.current_error_message = res.message_brut
            if cause.id_social_account_statuses_target is not None:
                compte.id_social_account_statuses_current = cause.id_social_account_statuses_target
            compte.id_users_changed_by = par.id_users

    await session.commit()
    await session.refresh(compte)
    compte_lu = (await _assembler_comptes(session, [compte]))[0]
    return SocialAccountSyncStatsRead(
        ok=res.ok,
        synced_days=len(res.valeurs_par_jour),
        message=res.message_utilisateur,
        raw_error=res.message_brut,
        account=compte_lu,
    )


async def lister_jetons_compte(
    session: AsyncSession, id_compte: int
) -> list[SocialAccountTokenRead]:
    """Renvoie l'historique des délivrances de clés d'un compte (sans les secrets)."""
    await _charger_compte(session, id_compte)
    jetons = list(
        (
            await session.execute(
                select(SocialAccountToken)
                .where(SocialAccountToken.id_social_accounts == id_compte)
                .order_by(SocialAccountToken.obtained_at.desc(), SocialAccountToken.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    user_ids = {t.id_users_created_by for t in jetons if t.id_users_created_by}
    noms = await _noms_utilisateurs(session, user_ids)

    resultats: list[SocialAccountTokenRead] = []
    for t in jetons:
        perms: list[str] = []
        raw = t.granted_api_permissions_json
        if isinstance(raw, list):
            perms = [str(p) for p in raw]
        elif isinstance(raw, dict) and isinstance(raw.get("scopes"), list):
            perms = [str(p) for p in raw["scopes"]]

        resultats.append(
            SocialAccountTokenRead(
                id_social_account_tokens=t.id_social_account_tokens,
                token_kind=t.token_kind,
                obtained_at=t.obtained_at,
                access_expires_at=t.access_expires_at,
                superseded_at=t.superseded_at,
                revoked_at=t.revoked_at,
                granted_permissions=perms,
                created_by_name=noms.get(t.id_users_created_by) if t.id_users_created_by else None,
                is_active=t.superseded_at is None and t.revoked_at is None,
            )
        )
    return resultats


async def lister_passages_compte(
    session: AsyncSession, id_compte: int
) -> list[SocialAccountSyncRead]:
    """Renvoie le journal des passages (`social_account_syncs`) d'un compte."""
    await _charger_compte(session, id_compte)
    passages = list(
        (
            await session.execute(
                select(SocialAccountSync)
                .where(SocialAccountSync.id_social_accounts == id_compte)
                .order_by(SocialAccountSync.started_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    causes = {
        c.id_social_account_error_causes: c
        for c in (await session.execute(select(SocialAccountErrorCause))).scalars().all()
    }
    user_ids = {p.id_users_triggered_by for p in passages if p.id_users_triggered_by}
    noms = await _noms_utilisateurs(session, user_ids)

    return [
        SocialAccountSyncRead(
            id_social_account_syncs=p.id_social_account_syncs,
            sync_kind=p.sync_kind,
            started_at=p.started_at,
            finished_at=p.finished_at,
            sync_outcome=p.sync_outcome,
            covered_until_date=p.covered_until_date,
            error_cause_code=(
                causes[p.id_social_account_error_causes].code
                if p.id_social_account_error_causes in causes
                else None
            ),
            error_cause_label=(
                causes[p.id_social_account_error_causes].label
                if p.id_social_account_error_causes in causes
                else None
            ),
            retry_after=p.retry_after,
            triggered_by_name=(
                noms.get(p.id_users_triggered_by) if p.id_users_triggered_by else None
            ),
        )
        for p in passages
    ]


async def lister_posts_compte(session: AsyncSession, id_compte: int) -> list[SocialPostRead]:
    """Renvoie les publications parues (`social_posts`) sur ce compte."""
    await _charger_compte(session, id_compte)
    posts = list(
        (
            await session.execute(
                select(SocialPost)
                .where(SocialPost.id_social_accounts == id_compte)
                .order_by(SocialPost.published_at.desc().nullslast(), SocialPost.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    user_ids = {p.id_users_archived_by for p in posts if p.id_users_archived_by}
    noms = await _noms_utilisateurs(session, user_ids)

    return [
        SocialPostRead(
            id_social_posts=p.id_social_posts,
            post_external_id=p.post_external_id,
            permalink=p.permalink,
            published_at=p.published_at,
            archived_on_platform_at=p.archived_on_platform_at,
            archived_by_name=noms.get(p.id_users_archived_by) if p.id_users_archived_by else None,
            deleted_on_platform_at=p.deleted_on_platform_at,
            created_at=p.created_at,
        )
        for p in posts
    ]


async def declarer_post_archive(
    session: AsyncSession, id_compte: int, id_post: int, par: User
) -> SocialPostRead:
    """Déclare une publication comme archivée sur le réseau (geste humain)."""
    await _charger_compte(session, id_compte)
    post = (
        await session.execute(
            select(SocialPost).where(
                SocialPost.id_social_posts == id_post,
                SocialPost.id_social_accounts == id_compte,
            )
        )
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("Publication parue introuvable sur ce compte.")

    post.archived_on_platform_at = datetime.now(UTC)
    post.id_users_archived_by = par.id_users
    await session.commit()
    await session.refresh(post)

    return SocialPostRead(
        id_social_posts=post.id_social_posts,
        post_external_id=post.post_external_id,
        permalink=post.permalink,
        published_at=post.published_at,
        archived_on_platform_at=post.archived_on_platform_at,
        archived_by_name=f"{par.first_name} {par.last_name}".strip(),
        deleted_on_platform_at=post.deleted_on_platform_at,
        created_at=post.created_at,
    )


async def synchroniser_posts_compte(
    session: AsyncSession, id_compte: int, par: User
) -> SocialAccountSyncPostsRead:
    """Importe depuis Meta Graph API les publications déjà parues sur ce compte."""
    compte = await _charger_compte(session, id_compte)
    plateforme = await session.get(SocialPlatform, compte.id_social_platforms)
    if plateforme is None:
        raise NotFoundError("Plateforme introuvable.")

    if plateforme.code not in ("facebook", "instagram"):
        raise ApiError(
            "posts_sync_not_supported",
            f"L'import des publications n'est pas encore branché pour {plateforme.label}. "
            "Seuls Facebook et Instagram (Meta Graph API) sont supportés aujourd'hui.",
            400,
        )

    id_detenteur = (
        compte.id_social_accounts_parent
        if compte.credential_mode == "inherited" and compte.id_social_accounts_parent
        else compte.id_social_accounts
    )
    jeton = (
        await session.execute(
            select(SocialAccountToken).where(
                SocialAccountToken.id_social_accounts == id_detenteur,
                SocialAccountToken.superseded_at.is_(None),
                SocialAccountToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if jeton is None or not jeton.access_token_encrypted:
        raise ApiError(
            "no_active_token",
            "Aucun jeton actif trouvé pour ce compte (ou son compte parent).",
            400,
        )

    clair = decrypt_token(jeton.access_token_encrypted)
    res = await importer_posts_meta(plateforme, compte.account_external_id, clair)

    if not res.ok:
        posts_actuels = await lister_posts_compte(session, id_compte)
        return SocialAccountSyncPostsRead(
            ok=False,
            imported_count=0,
            total_fetched=0,
            message=res.message_utilisateur,
            raw_error=res.message_brut,
            posts=posts_actuels,
        )

    existants = {
        p.post_external_id: p
        for p in (
            await session.execute(
                select(SocialPost).where(SocialPost.id_social_accounts == id_compte)
            )
        )
        .scalars()
        .all()
    }

    importes = 0
    for ext in res.posts:
        deja = existants.get(ext.post_external_id)
        if deja is not None:
            if not deja.permalink and ext.permalink:
                deja.permalink = ext.permalink
            if not deja.published_at and ext.published_at:
                deja.published_at = ext.published_at
        else:
            session.add(
                SocialPost(
                    id_social_accounts=id_compte,
                    post_external_id=ext.post_external_id,
                    permalink=ext.permalink,
                    published_at=ext.published_at,
                )
            )
            importes += 1

    await session.commit()
    posts_maj = await lister_posts_compte(session, id_compte)
    msg = (
        f"{importes} nouvelle(s) publication(s) importée(s) sur {len(res.posts)} lue(s) depuis {plateforme.label}."
        if res.posts
        else f"Aucune publication trouvée sur {plateforme.label}."
    )
    return SocialAccountSyncPostsRead(
        ok=True,
        imported_count=importes,
        total_fetched=len(res.posts),
        message=msg,
        posts=posts_maj,
    )
