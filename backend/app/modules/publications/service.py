"""Règles métier du module 08 Publications."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, NotFoundError, PermissionDeniedError
from app.core.security import decrypt_token
from app.core.storage import get_stockage
from app.modules.media.models import Media
from app.modules.platforms.models import SocialPlatform
from app.modules.publications.constants import (
    CIBLE_ATTENTE_PROG,
    CIBLE_ECHEC,
    CIBLE_PUBLIEE,
    EVT_CIBLE_CREEE,
    EVT_CIBLE_ENVOI,
    EVT_CIBLE_ECHEC,
    EVT_CIBLE_PUBLIEE,
    EVT_PUB_APPROUVEE,
    EVT_PUB_CORRECTION,
    EVT_PUB_CREEE,
    EVT_PUB_ECHEC,
    EVT_PUB_ENVOI,
    EVT_PUB_PARTIELLE,
    EVT_PUB_PUBLIEE,
    PUB_A_CORRIGER,
    PUB_APPROUVEE,
    PUB_ECHEC,
    PUB_EN_ATTENTE,
    PUB_EN_COURS,
    PUB_PARTIELLE,
    PUB_PROGRAMMEE,
    PUB_PUBLIEE,
    VALIDATE_OWN_PUBLICATIONS,
)
from app.modules.publications.meta_publisher import publier_sur_facebook
from app.modules.publications.models import (
    DeliveryEventType,
    DeliveryStatus,
    Format,
    HistoryPublication,
    HistoryPublicationTarget,
    PlatformFormat,
    Publication,
    PublicationEventType,
    PublicationMedia,
    PublicationStatus,
    PublicationTarget,
)
from app.modules.publications.schemas import (
    PublicationCreate,
    PublicationFormatRead,
    PublicationHistoryRead,
    PublicationMediaRead,
    PublicationPublishResultRead,
    PublicationRead,
    PublicationTargetRead,
)
from app.modules.social_accounts.constants import STATUT_ACTIF
from app.modules.social_accounts.models import (
    SocialAccount,
    SocialAccountStatus,
    SocialAccountToken,
    SocialPost,
)
from app.modules.users.deps import codes_de
from app.modules.users.models import User


async def lister_formats(session: AsyncSession) -> list[PublicationFormatRead]:
    """Renvoie les formats actifs et les plateformes qui acceptent chacun."""
    formats = list(
        (await session.execute(select(Format).where(Format.is_enabled.is_(True)).order_by(Format.sort_order)))
        .scalars()
        .all()
    )
    liens = (
        await session.execute(
            select(PlatformFormat.id_formats, SocialPlatform.code)
            .join(SocialPlatform, SocialPlatform.id_social_platforms == PlatformFormat.id_social_platforms)
            .order_by(SocialPlatform.sort_order)
        )
    ).all()

    par_format: dict[int, list[str]] = {}
    for id_fmt, plat_code in liens:
        par_format.setdefault(int(id_fmt), []).append(str(plat_code))

    return [
        PublicationFormatRead(
            code=f.code,
            label=f.label,
            min_media_count=f.min_media_count,
            max_media_count=f.max_media_count,
            is_enabled=f.is_enabled,
            sort_order=f.sort_order,
            platforms=par_format.get(f.id_formats, []),
        )
        for f in formats
    ]


async def _pub_status(session: AsyncSession, code: str) -> PublicationStatus:
    st = (
        await session.execute(select(PublicationStatus).where(PublicationStatus.code == code))
    ).scalar_one_or_none()
    if st is None:
        raise ApiError("unknown_publication_status", f"Statut publication introuvable : {code}.", 500)
    return st


async def _deliv_status(session: AsyncSession, code: str) -> DeliveryStatus:
    st = (
        await session.execute(select(DeliveryStatus).where(DeliveryStatus.code == code))
    ).scalar_one_or_none()
    if st is None:
        raise ApiError("unknown_delivery_status", f"Statut cible introuvable : {code}.", 500)
    return st


async def _pub_event(session: AsyncSession, code: str) -> PublicationEventType:
    ev = (
        await session.execute(select(PublicationEventType).where(PublicationEventType.code == code))
    ).scalar_one_or_none()
    if ev is None:
        raise ApiError("unknown_publication_event", f"Événement publication introuvable : {code}.", 500)
    return ev


async def _deliv_event(session: AsyncSession, code: str) -> DeliveryEventType:
    ev = (
        await session.execute(select(DeliveryEventType).where(DeliveryEventType.code == code))
    ).scalar_one_or_none()
    if ev is None:
        raise ApiError("unknown_delivery_event", f"Événement cible introuvable : {code}.", 500)
    return ev


async def _assembler_publications(
    session: AsyncSession, publications: list[Publication]
) -> list[PublicationRead]:
    if not publications:
        return []

    ids = [p.id_publications for p in publications]
    stockage = get_stockage()

    formats = {f.id_formats: f for f in (await session.execute(select(Format))).scalars().all()}
    pub_statuses = {
        s.id_publication_statuses: s
        for s in (await session.execute(select(PublicationStatus))).scalars().all()
    }
    deliv_statuses = {
        s.id_delivery_statuses: s
        for s in (await session.execute(select(DeliveryStatus))).scalars().all()
    }
    pub_events = {
        e.id_publication_event_types: e
        for e in (await session.execute(select(PublicationEventType))).scalars().all()
    }
    plateformes = {
        p.id_social_platforms: p
        for p in (await session.execute(select(SocialPlatform))).scalars().all()
    }

    # Médias ordonnés
    pm_rows = (
        await session.execute(
            select(PublicationMedia, Media)
            .join(Media, Media.id_media == PublicationMedia.id_media)
            .where(PublicationMedia.id_publications.in_(ids))
            .order_by(PublicationMedia.carousel_position.asc())
        )
    ).all()
    medias_par_pub: dict[int, list[PublicationMediaRead]] = {}
    for pm, m in pm_rows:
        medias_par_pub.setdefault(pm.id_publications, []).append(
            PublicationMediaRead(
                id_media=m.id_media,
                carousel_position=pm.carousel_position,
                display_name=m.display_name,
                file_type=m.file_type,
                url=stockage.url_publique(m.storage_key),
            )
        )

    # Cibles
    cibles = list(
        (
            await session.execute(
                select(PublicationTarget)
                .where(PublicationTarget.id_publications.in_(ids))
                .order_by(PublicationTarget.id_publication_targets.asc())
            )
        )
        .scalars()
        .all()
    )
    compte_ids = {c.id_social_accounts for c in cibles}
    comptes = (
        {
            a.id_social_accounts: a
            for a in (
                await session.execute(
                    select(SocialAccount).where(SocialAccount.id_social_accounts.in_(compte_ids))
                )
            )
            .scalars()
            .all()
        }
        if compte_ids
        else {}
    )
    post_ids = {c.id_social_posts for c in cibles if c.id_social_posts}
    posts = (
        {
            p.id_social_posts: p
            for p in (
                await session.execute(select(SocialPost).where(SocialPost.id_social_posts.in_(post_ids)))
            )
            .scalars()
            .all()
        }
        if post_ids
        else {}
    )

    # Dernière erreur par cible depuis history_publication_targets
    cible_ids = [c.id_publication_targets for c in cibles]
    erreurs_par_cible: dict[int, str] = {}
    if cible_ids:
        hist_cibles = list(
            (
                await session.execute(
                    select(HistoryPublicationTarget)
                    .where(
                        HistoryPublicationTarget.id_publication_targets.in_(cible_ids),
                        HistoryPublicationTarget.error_message_json.is_not(None),
                    )
                    .order_by(HistoryPublicationTarget.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        for hc in hist_cibles:
            if hc.id_publication_targets not in erreurs_par_cible:
                err_json = hc.error_message_json or {}
                meta_err = err_json.get("meta_error") if isinstance(err_json, dict) else None
                if isinstance(meta_err, dict) and meta_err.get("message"):
                    erreurs_par_cible[hc.id_publication_targets] = str(meta_err["message"])
                else:
                    erreurs_par_cible[hc.id_publication_targets] = str(
                        hc.commentaires_users or err_json.get("error") or "Échec d'envoi."
                    )

    cibles_par_pub: dict[int, list[PublicationTargetRead]] = {}
    for c in cibles:
        acc = comptes[c.id_social_accounts]
        plat = plateformes[acc.id_social_platforms]
        dst = deliv_statuses[c.id_delivery_statuses]
        sp = posts.get(c.id_social_posts) if c.id_social_posts else None
        cibles_par_pub.setdefault(c.id_publications, []).append(
            PublicationTargetRead(
                id_publication_targets=c.id_publication_targets,
                id_social_accounts=c.id_social_accounts,
                account_display_name=acc.account_display_name,
                platform_code=plat.code,
                platform_label=plat.label,
                description=c.description_publication_targets,
                scheduled_at=c.current_scheduled_at_denormalized,
                delivery_status_code=dst.code,
                delivery_status_label=dst.label,
                id_social_posts=c.id_social_posts,
                post_external_id=sp.post_external_id if sp else None,
                permalink=sp.permalink if sp else None,
                last_error=erreurs_par_cible.get(c.id_publication_targets),
            )
        )

    # Historique publication
    hists = list(
        (
            await session.execute(
                select(HistoryPublication)
                .where(HistoryPublication.id_publications.in_(ids))
                .order_by(HistoryPublication.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    user_ids = {h.id_users_changed_by for h in hists if h.id_users_changed_by}
    noms: dict[int, str] = {}
    if user_ids:
        urows = (
            await session.execute(
                select(User.id_users, User.first_name, User.last_name).where(User.id_users.in_(user_ids))
            )
        ).all()
        noms = {int(r[0]): f"{r[1]} {r[2]}".strip() for r in urows}

    hist_par_pub: dict[int, list[PublicationHistoryRead]] = {}
    auteur_par_pub: dict[int, str | None] = {}
    for h in hists:
        ev = pub_events[h.id_publication_event_types]
        st = pub_statuses[h.id_publication_statuses]
        nom = noms.get(h.id_users_changed_by) if h.id_users_changed_by else None
        if ev.code == EVT_PUB_CREEE and h.id_publications not in auteur_par_pub:
            auteur_par_pub[h.id_publications] = nom
        hist_par_pub.setdefault(h.id_publications, []).append(
            PublicationHistoryRead(
                event_code=ev.code,
                event_label=ev.label,
                status_code=st.code,
                status_label=st.label,
                changed_by_name=nom,
                comment=h.commentaires_users,
                created_at=h.created_at,
            )
        )

    resultats: list[PublicationRead] = []
    for p in publications:
        fmt = formats[p.id_formats]
        st = pub_statuses[p.id_publication_statuses]
        resultats.append(
            PublicationRead(
                id_publications=p.id_publications,
                format_code=fmt.code,
                format_label=fmt.label,
                status_code=st.code,
                status_label=st.label,
                created_by_name=auteur_par_pub.get(p.id_publications),
                media=medias_par_pub.get(p.id_publications, []),
                targets=cibles_par_pub.get(p.id_publications, []),
                history=hist_par_pub.get(p.id_publications, []),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )
    return resultats


async def lister_publications(session: AsyncSession) -> list[PublicationRead]:
    pubs = list(
        (await session.execute(select(Publication).order_by(Publication.created_at.desc()).limit(100)))
        .scalars()
        .all()
    )
    return await _assembler_publications(session, pubs)


async def obtenir_publication(session: AsyncSession, id_pub: int) -> PublicationRead:
    if id_pub < 1 or id_pub > 2_147_483_647:
        raise NotFoundError("Publication introuvable.")
    pub = await session.get(Publication, id_pub)
    if pub is None:
        raise NotFoundError("Publication introuvable.")
    return (await _assembler_publications(session, [pub]))[0]


async def creer_publication(
    session: AsyncSession, donnees: PublicationCreate, par: User
) -> PublicationRead:
    """Crée une publication en statut `pending_review`, ses médias, ses cibles et ses journaux."""
    fmt = (
        await session.execute(
            select(Format).where(Format.code == donnees.format_code.strip(), Format.is_enabled.is_(True))
        )
    ).scalar_one_or_none()
    if fmt is None:
        raise NotFoundError(f"Format inconnu ou désactivé : « {donnees.format_code} ».")

    # Contrôle du nombre de médias et absence de doublon
    nb_medias = len(donnees.media_ids)
    if nb_medias < fmt.min_media_count or nb_medias > fmt.max_media_count:
        raise ApiError(
            "invalid_media_count",
            f"Le format « {fmt.label} » attend entre {fmt.min_media_count} et {fmt.max_media_count} média(s).",
        )
    if len(set(donnees.media_ids)) != nb_medias:
        raise ApiError("duplicate_media", "Un même média ne peut figurer qu'une seule fois.")

    if donnees.media_ids:
        trouves = set(
            (
                await session.execute(
                    select(Media.id_media).where(
                        Media.id_media.in_(donnees.media_ids), Media.deleted_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        manquants = [mid for mid in donnees.media_ids if mid not in trouves]
        if manquants:
            raise NotFoundError(f"Média(s) introuvable(s) ou archivé(s) : {manquants}.")

    # Contrôle des cibles : comptes actifs uniques + compatibilité format/plateforme + longueur légende
    ids_comptes = [t.id_social_accounts for t in donnees.targets]
    if len(set(ids_comptes)) != len(ids_comptes):
        raise ApiError("duplicate_target_account", "Un même compte ne peut être ciblé qu'une fois.")

    comptes = {
        a.id_social_accounts: a
        for a in (
            await session.execute(
                select(SocialAccount).where(
                    SocialAccount.id_social_accounts.in_(ids_comptes),
                    SocialAccount.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    statuts_comptes = {
        s.id_social_account_statuses: s.code
        for s in (await session.execute(select(SocialAccountStatus))).scalars().all()
    }
    plateformes = {
        p.id_social_platforms: p
        for p in (await session.execute(select(SocialPlatform))).scalars().all()
    }
    plateformes_format = set(
        (
            await session.execute(
                select(PlatformFormat.id_social_platforms).where(
                    PlatformFormat.id_formats == fmt.id_formats
                )
            )
        )
        .scalars()
        .all()
    )

    for t in donnees.targets:
        acc = comptes.get(t.id_social_accounts)
        if acc is None:
            raise NotFoundError(f"Compte réseau social #{t.id_social_accounts} introuvable.")
        if statuts_comptes.get(acc.id_social_account_statuses_current) != STATUT_ACTIF:
            raise ApiError(
                "account_not_active",
                f"Le compte « {acc.account_display_name} » n'est pas actif et ne peut pas recevoir de cible.",
            )
        plat = plateformes[acc.id_social_platforms]
        if acc.id_social_platforms not in plateformes_format:
            raise ApiError(
                "format_not_supported_by_platform",
                f"{plat.label} n'accepte pas le format « {fmt.label} ».",
            )
        if plat.max_description_length and len(t.description) > plat.max_description_length:
            raise ApiError(
                "caption_too_long",
                f"La légende dépasse la limite de {plat.max_description_length} caractères pour {plat.label}.",
            )

    st_pending = await _pub_status(session, PUB_EN_ATTENTE)
    ev_pub_creee = await _pub_event(session, EVT_PUB_CREEE)
    st_cible_att = await _deliv_status(session, CIBLE_ATTENTE_PROG)
    ev_cible_creee = await _deliv_event(session, EVT_CIBLE_CREEE)

    pub = Publication(
        id_publication_statuses=st_pending.id_publication_statuses,
        id_formats=fmt.id_formats,
    )
    session.add(pub)
    await session.flush()

    for pos, id_media in enumerate(donnees.media_ids, start=1):
        session.add(
            PublicationMedia(
                id_publications=pub.id_publications,
                id_media=id_media,
                carousel_position=pos,
            )
        )

    session.add(
        HistoryPublication(
            id_publications=pub.id_publications,
            id_publication_event_types=ev_pub_creee.id_publication_event_types,
            id_publication_statuses=st_pending.id_publication_statuses,
            id_users_changed_by=par.id_users,
        )
    )

    for t in donnees.targets:
        cible = PublicationTarget(
            id_publications=pub.id_publications,
            id_social_accounts=t.id_social_accounts,
            description_publication_targets=t.description.strip(),
            current_scheduled_at_denormalized=t.scheduled_at,
            id_delivery_statuses=st_cible_att.id_delivery_statuses,
        )
        session.add(cible)
        await session.flush()
        session.add(
            HistoryPublicationTarget(
                id_publication_targets=cible.id_publication_targets,
                id_delivery_event_types=ev_cible_creee.id_delivery_event_types,
                id_delivery_statuses=st_cible_att.id_delivery_statuses,
                new_scheduled_at=t.scheduled_at,
                new_description_publication_targets=t.description.strip(),
                id_users_changed_by=par.id_users,
            )
        )

    await session.commit()
    await session.refresh(pub)
    return (await _assembler_publications(session, [pub]))[0]


async def approuver_publication(
    session: AsyncSession, id_pub: int, par: User, commentaire: str | None = None
) -> PublicationRead:
    """Validation humaine obligatoire avant toute diffusion (F-07, OB-04)."""
    pub = await session.get(Publication, id_pub)
    if pub is None:
        raise NotFoundError("Publication introuvable.")

    st_actuel = await session.get(PublicationStatus, pub.id_publication_statuses)
    if st_actuel is None or st_actuel.code != PUB_EN_ATTENTE:
        raise ApiError(
            "invalid_publication_transition",
            "Seule une publication en attente de validation peut être approuvée.",
        )

    # Si le relecteur est aussi l'auteur, le droit `validate_own_publications` est exigé.
    creation = (
        await session.execute(
            select(HistoryPublication)
            .join(
                PublicationEventType,
                PublicationEventType.id_publication_event_types
                == HistoryPublication.id_publication_event_types,
            )
            .where(
                HistoryPublication.id_publications == id_pub,
                PublicationEventType.code == EVT_PUB_CREEE,
            )
            .order_by(HistoryPublication.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if creation is not None and creation.id_users_changed_by == par.id_users:
        if VALIDATE_OWN_PUBLICATIONS not in await codes_de(session, par.id_users):
            raise PermissionDeniedError(
                "Valider sa propre publication demande le droit « validate_own_publications »."
            )

    st_app = await _pub_status(session, PUB_APPROUVEE)
    ev_app = await _pub_event(session, EVT_PUB_APPROUVEE)

    pub.id_publication_statuses = st_app.id_publication_statuses
    session.add(
        HistoryPublication(
            id_publications=pub.id_publications,
            id_publication_event_types=ev_app.id_publication_event_types,
            id_publication_statuses=st_app.id_publication_statuses,
            id_users_changed_by=par.id_users,
            commentaires_users=commentaire,
        )
    )
    await session.commit()
    await session.refresh(pub)
    return (await _assembler_publications(session, [pub]))[0]


async def demander_correction(
    session: AsyncSession, id_pub: int, par: User, commentaire: str | None = None
) -> PublicationRead:
    pub = await session.get(Publication, id_pub)
    if pub is None:
        raise NotFoundError("Publication introuvable.")

    st_actuel = await session.get(PublicationStatus, pub.id_publication_statuses)
    if st_actuel is None or st_actuel.code != PUB_EN_ATTENTE:
        raise ApiError(
            "invalid_publication_transition",
            "Seule une publication en attente de validation peut être renvoyée en correction.",
        )

    st_corr = await _pub_status(session, PUB_A_CORRIGER)
    ev_corr = await _pub_event(session, EVT_PUB_CORRECTION)
    pub.id_publication_statuses = st_corr.id_publication_statuses
    session.add(
        HistoryPublication(
            id_publications=pub.id_publications,
            id_publication_event_types=ev_corr.id_publication_event_types,
            id_publication_statuses=st_corr.id_publication_statuses,
            id_users_changed_by=par.id_users,
            commentaires_users=commentaire,
        )
    )
    await session.commit()
    await session.refresh(pub)
    return (await _assembler_publications(session, [pub]))[0]


async def publier_maintenant(
    session: AsyncSession, id_pub: int, par: User
) -> PublicationPublishResultRead:
    """Diffuse immédiatement les cibles d'une publication VALIDÉE vers les plateformes (Facebook)."""
    pub = await session.get(Publication, id_pub)
    if pub is None:
        raise NotFoundError("Publication introuvable.")

    st_actuel = await session.get(PublicationStatus, pub.id_publication_statuses)
    if st_actuel is None or st_actuel.code not in (PUB_APPROUVEE, PUB_PROGRAMMEE, PUB_ECHEC, PUB_PARTIELLE):
        raise ApiError(
            "validation_required",
            "Aucune diffusion n'est permise avant validation humaine (statut « Validée » requis).",
        )

    fmt = await session.get(Format, pub.id_formats)
    assert fmt is not None

    medias = [
        m
        for _, m in (
            await session.execute(
                select(PublicationMedia, Media)
                .join(Media, Media.id_media == PublicationMedia.id_media)
                .where(PublicationMedia.id_publications == id_pub)
                .order_by(PublicationMedia.carousel_position.asc())
            )
        ).all()
    ]

    cibles = list(
        (
            await session.execute(
                select(PublicationTarget)
                .where(PublicationTarget.id_publications == id_pub)
                .order_by(PublicationTarget.id_publication_targets.asc())
            )
        )
        .scalars()
        .all()
    )

    st_pub_encours = await _pub_status(session, PUB_EN_COURS)
    ev_pub_envoi = await _pub_event(session, EVT_PUB_ENVOI)
    st_cible_pub = await _deliv_status(session, CIBLE_PUBLIEE)
    st_cible_echec = await _deliv_status(session, CIBLE_ECHEC)
    ev_cible_envoi = await _deliv_event(session, EVT_CIBLE_ENVOI)
    ev_cible_pub = await _deliv_event(session, EVT_CIBLE_PUBLIEE)
    ev_cible_echec = await _deliv_event(session, EVT_CIBLE_ECHEC)

    pub.id_publication_statuses = st_pub_encours.id_publication_statuses
    session.add(
        HistoryPublication(
            id_publications=pub.id_publications,
            id_publication_event_types=ev_pub_envoi.id_publication_event_types,
            id_publication_statuses=st_pub_encours.id_publication_statuses,
            id_users_changed_by=par.id_users,
        )
    )
    await session.flush()

    nb_publiees = 0
    nb_echecs = 0
    messages: list[str] = []

    for cible in cibles:
        if cible.id_delivery_statuses == st_cible_pub.id_delivery_statuses:
            nb_publiees += 1
            continue

        acc = await session.get(SocialAccount, cible.id_social_accounts)
        assert acc is not None
        plat = await session.get(SocialPlatform, acc.id_social_platforms)
        assert plat is not None

        session.add(
            HistoryPublicationTarget(
                id_publication_targets=cible.id_publication_targets,
                id_delivery_event_types=ev_cible_envoi.id_delivery_event_types,
                id_delivery_statuses=cible.id_delivery_statuses,
                id_users_changed_by=par.id_users,
            )
        )

        if plat.code != "facebook":
            nb_echecs += 1
            msg = f"Le connecteur d'envoi en direct n'est pas encore branché pour {plat.label}."
            messages.append(msg)
            cible.id_delivery_statuses = st_cible_echec.id_delivery_statuses
            session.add(
                HistoryPublicationTarget(
                    id_publication_targets=cible.id_publication_targets,
                    id_delivery_event_types=ev_cible_echec.id_delivery_event_types,
                    id_delivery_statuses=st_cible_echec.id_delivery_statuses,
                    id_users_changed_by=par.id_users,
                    commentaires_users=msg,
                    error_message_json={"error": "connector_not_implemented", "platform": plat.code},
                )
            )
            continue

        id_detenteur = (
            acc.id_social_accounts_parent
            if acc.credential_mode == "inherited" and acc.id_social_accounts_parent
            else acc.id_social_accounts
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
            nb_echecs += 1
            msg = f"Aucun jeton actif pour « {acc.account_display_name} »."
            messages.append(msg)
            cible.id_delivery_statuses = st_cible_echec.id_delivery_statuses
            session.add(
                HistoryPublicationTarget(
                    id_publication_targets=cible.id_publication_targets,
                    id_delivery_event_types=ev_cible_echec.id_delivery_event_types,
                    id_delivery_statuses=st_cible_echec.id_delivery_statuses,
                    id_users_changed_by=par.id_users,
                    commentaires_users=msg,
                    error_message_json={"error": "no_active_token"},
                )
            )
            continue

        clair = decrypt_token(jeton.access_token_encrypted)
        res = await publier_sur_facebook(
            plateforme=plat,
            page_id=acc.account_external_id,
            access_token=clair,
            format_code=fmt.code,
            legende=cible.description_publication_targets or "",
            medias=medias,
        )

        if res.ok and res.post_external_id:
            nb_publiees += 1
            sp = SocialPost(
                id_social_accounts=acc.id_social_accounts,
                post_external_id=res.post_external_id,
                permalink=res.permalink,
                published_at=datetime.now(UTC),
            )
            session.add(sp)
            await session.flush()

            cible.id_social_posts = sp.id_social_posts
            cible.id_delivery_statuses = st_cible_pub.id_delivery_statuses
            session.add(
                HistoryPublicationTarget(
                    id_publication_targets=cible.id_publication_targets,
                    id_delivery_event_types=ev_cible_pub.id_delivery_event_types,
                    id_delivery_statuses=st_cible_pub.id_delivery_statuses,
                    id_users_changed_by=par.id_users,
                    commentaires_users=res.message,
                )
            )
            messages.append(f"{acc.account_display_name} : {res.message}")
        else:
            nb_echecs += 1
            cible.id_delivery_statuses = st_cible_echec.id_delivery_statuses
            session.add(
                HistoryPublicationTarget(
                    id_publication_targets=cible.id_publication_targets,
                    id_delivery_event_types=ev_cible_echec.id_delivery_event_types,
                    id_delivery_statuses=st_cible_echec.id_delivery_statuses,
                    id_users_changed_by=par.id_users,
                    commentaires_users=res.message,
                    error_message_json=res.error_detail,
                )
            )
            messages.append(f"{acc.account_display_name} : {res.message}")

    # Statut final de la publication résumé depuis ses cibles
    if nb_publiees == len(cibles) and nb_publiees > 0:
        st_final = await _pub_status(session, PUB_PUBLIEE)
        ev_final = await _pub_event(session, EVT_PUB_PUBLIEE)
    elif nb_publiees > 0:
        st_final = await _pub_status(session, PUB_PARTIELLE)
        ev_final = await _pub_event(session, EVT_PUB_PARTIELLE)
    else:
        st_final = await _pub_status(session, PUB_ECHEC)
        ev_final = await _pub_event(session, EVT_PUB_ECHEC)

    pub.id_publication_statuses = st_final.id_publication_statuses
    session.add(
        HistoryPublication(
            id_publications=pub.id_publications,
            id_publication_event_types=ev_final.id_publication_event_types,
            id_publication_statuses=st_final.id_publication_statuses,
            id_users_changed_by=par.id_users,
            commentaires_users=" ; ".join(messages)[:2000],
        )
    )

    await session.commit()
    await session.refresh(pub)
    pub_lue = (await _assembler_publications(session, [pub]))[0]
    return PublicationPublishResultRead(
        ok=nb_echecs == 0 and nb_publiees > 0,
        message=" · ".join(messages),
        published_count=nb_publiees,
        failed_count=nb_echecs,
        publication=pub_lue,
    )
