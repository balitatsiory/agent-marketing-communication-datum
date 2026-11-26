"""Logique métier du module Publications et workflow de validation avec notifications."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.modules.notifications import service as notification_service
from app.modules.notifications.constants import (
    SOURCE_INTERNAL,
    SOURCE_PLATFORM,
    TYPE_CORRECTION_SUGGESTED,
    TYPE_PUBLICATION_APPROVED,
    TYPE_PUBLICATION_PUBLISHED,
    TYPE_TEAM_ACTIVITY,
    TYPE_VALIDATION_REQUEST,
)
from app.modules.publications.constants import (
    EVENT_APPROVED,
    EVENT_CHANGES_REQUESTED,
    EVENT_COMMENT,
    EVENT_CREATED,
    EVENT_MODIFIED,
    EVENT_PUBLISHED,
    EVENT_SUBMITTED,
    FORMATS_VALIDES,
    STATUT_CHANGES_REQUESTED,
    STATUT_DRAFT,
    STATUT_PUBLISHED,
    STATUT_REVIEW,
    STATUT_SCHEDULED,
    STATUT_WITHDRAWN,
)
from app.modules.publications.models import Publication, PublicationEvent
from app.modules.publications.schemas import (
    ApprovePublicationInput,
    PublicationCreate,
    PublicationDetailRead,
    PublicationEventRead,
    PublicationSummaryRead,
    PublicationUpdate,
    ValidatorOptionRead,
)
from app.modules.users.models import User

HASHTAG_RE = re.compile(r"#[\wÀ-ÿ-]+")


def _initiales(u: User | None) -> str:
    if u is None:
        return "IA"
    return f"{u.first_name[:1]}{u.last_name[:1]}".upper() or u.email[:2].upper()


def _extraire_hashtags(caption: str, explicites: list[str] | None) -> list[str]:
    if explicites is not None:
        return list(dict.fromkeys(h.strip() for h in explicites if h.strip()))
    return list(dict.fromkeys(HASHTAG_RE.findall(caption)))


async def _charger_utilisateurs(session: AsyncSession, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    rows = (await session.execute(select(User).where(User.id_users.in_(ids)))).scalars().all()
    return {u.id_users: u for u in rows}


async def _destinataires_validation(
    session: AsyncSession,
    *,
    auteur: User,
    id_users_validator: int | None,
) -> list[int]:
    """Détermine qui doit recevoir la demande de validation (utilisateur B)."""
    if id_users_validator is not None:
        cible = await session.get(User, id_users_validator)
        if cible is not None and cible.est_utilisable:
            return [cible.id_users]

    autres = (
        await session.execute(
            select(User.id_users).where(
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                User.id_users != auteur.id_users,
            )
        )
    ).scalars().all()
    if autres:
        return list(autres)
    # Fallback en environnement mono-utilisateur pour permettre de tester le cycle.
    return [auteur.id_users]


async def lister_validateurs(
    session: AsyncSession, courant: User
) -> list[ValidatorOptionRead]:
    """Liste les membres actifs pouvant être sélectionnés comme validateur."""
    rows = (
        await session.execute(
            select(User)
            .where(User.deleted_at.is_(None), User.is_active.is_(True))
            .order_by(User.first_name.asc(), User.last_name.asc())
        )
    ).scalars().all()
    options = [
        ValidatorOptionRead(
            id_users=u.id_users,
            full_name=u.nom_affiche,
            initials=_initiales(u),
            email=u.email,
            is_self=u.id_users == courant.id_users,
        )
        for u in rows
    ]
    # Mettre les collègues avant soi-même.
    options.sort(key=lambda o: (o.is_self, o.full_name.lower()))
    return options


async def _hydrater_resume(
    session: AsyncSession, publications: Sequence[Publication]
) -> list[PublicationSummaryRead]:
    if not publications:
        return []
    user_ids: set[int] = set()
    pub_ids: list[int] = []
    for p in publications:
        pub_ids.append(p.id_publications)
        user_ids.add(p.id_users_author)
        if p.id_users_validator is not None:
            user_ids.add(p.id_users_validator)

    utilisateurs = await _charger_utilisateurs(session, user_ids)
    counts_rows = (
        await session.execute(
            select(PublicationEvent.id_publications, func.count())
            .where(
                PublicationEvent.id_publications.in_(pub_ids),
                PublicationEvent.comment.is_not(None),
            )
            .group_by(PublicationEvent.id_publications)
        )
    ).all()
    comment_counts = {int(pid): int(cnt) for pid, cnt in counts_rows}

    resumes: list[PublicationSummaryRead] = []
    for p in publications:
        auteur = utilisateurs.get(p.id_users_author)
        validateur = utilisateurs.get(p.id_users_validator) if p.id_users_validator else None
        resumes.append(
            PublicationSummaryRead(
                id_publications=p.id_publications,
                title=p.title,
                caption=p.caption,
                format_code=p.format_code,
                status_code=p.status_code,
                platform_codes=list(p.platform_codes or []),
                hashtags=list(p.hashtags or []),
                scheduled_at=p.scheduled_at,
                published_at=p.published_at,
                id_users_author=p.id_users_author,
                author_name=auteur.nom_affiche if auteur else "Utilisateur",
                author_initials=_initiales(auteur),
                id_users_validator=p.id_users_validator,
                validator_name=validateur.nom_affiche if validateur else None,
                comment_count=comment_counts.get(p.id_publications, 0),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )
    return resumes


async def _hydrater_detail(
    session: AsyncSession, pub: Publication
) -> PublicationDetailRead:
    events = (
        await session.execute(
            select(PublicationEvent)
            .where(PublicationEvent.id_publications == pub.id_publications)
            .order_by(PublicationEvent.created_at.asc(), PublicationEvent.id_publication_events.asc())
        )
    ).scalars().all()

    user_ids: set[int] = {pub.id_users_author}
    if pub.id_users_validator is not None:
        user_ids.add(pub.id_users_validator)
    for ev in events:
        if ev.id_users_author is not None:
            user_ids.add(ev.id_users_author)
    utilisateurs = await _charger_utilisateurs(session, user_ids)

    resume = (await _hydrater_resume(session, [pub]))[0]
    event_reads = [
        PublicationEventRead(
            id_publication_events=ev.id_publication_events,
            id_publications=ev.id_publications,
            kind=ev.kind,
            label=ev.label,
            comment=ev.comment,
            id_users_author=ev.id_users_author,
            author_name=utilisateurs[ev.id_users_author].nom_affiche
            if ev.id_users_author and ev.id_users_author in utilisateurs
            else "IAGORA",
            author_initials=_initiales(utilisateurs.get(ev.id_users_author))
            if ev.id_users_author
            else "IA",
            created_at=ev.created_at,
        )
        for ev in events
    ]

    return PublicationDetailRead(
        **resume.model_dump(),
        captions_by_platform=pub.captions_by_platform,
        media_items=pub.media_items,
        events=event_reads,
    )


async def _obtenir_entite(session: AsyncSession, id_publications: int) -> Publication:
    pub = await session.get(Publication, id_publications)
    if pub is None or pub.deleted_at is not None:
        raise NotFoundError("Publication introuvable.")
    return pub


async def lister(
    session: AsyncSession,
    params: PageParams,
    *,
    status_code: str | None = None,
) -> tuple[list[PublicationSummaryRead], int]:
    conditions = [Publication.deleted_at.is_(None)]
    if status_code:
        conditions.append(Publication.status_code == status_code)

    total = (
        await session.execute(select(func.count()).select_from(Publication).where(*conditions))
    ).scalar_one()

    rows = (
        await session.execute(
            select(Publication)
            .where(*conditions)
            .order_by(Publication.updated_at.desc(), Publication.id_publications.desc())
            .offset(params.offset)
            .limit(params.size)
        )
    ).scalars().all()
    return await _hydrater_resume(session, rows), int(total)


async def obtenir(session: AsyncSession, id_publications: int) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    return await _hydrater_detail(session, pub)


async def _soumettre_et_notifier(
    session: AsyncSession,
    pub: Publication,
    auteur: User,
    *,
    comment: str | None = None,
    re_soumission: bool = False,
) -> None:
    pub.status_code = STATUT_REVIEW
    label = "Renvoyée à la validation après correction" if re_soumission else "Envoyée à la validation"
    session.add(
        PublicationEvent(
            id_publications=pub.id_publications,
            kind=EVENT_SUBMITTED,
            label=label,
            comment=comment,
            id_users_author=auteur.id_users,
        )
    )
    await notification_service.marquer_lues_par_entite(
        session,
        id_users_recipient=auteur.id_users,
        entity_type="publication",
        entity_id=pub.id_publications,
    )
    destinataires = await _destinataires_validation(
        session, auteur=auteur, id_users_validator=pub.id_users_validator
    )
    reseaux = ", ".join(pub.platform_codes) if pub.platform_codes else "réseaux sociaux"
    verbe = "a renvoyé pour validation" if re_soumission else "a programmé et envoyé à la validation"
    for recipient_id in destinataires:
        await notification_service.creer(
            session,
            id_users_recipient=recipient_id,
            id_users_actor=auteur.id_users,
            notification_type=TYPE_VALIDATION_REQUEST,
            source_scope=SOURCE_INTERNAL,
            platform_code=None,
            title=f"Validation demandée — « {pub.title} »",
            body=f"{auteur.nom_affiche} {verbe} cette publication ({reseaux}).",
            requires_action=True,
            action_label="Voir et valider",
            action_url=f"/publications/{pub.id_publications}",
            entity_type="publication",
            entity_id=pub.id_publications,
        )


async def creer(
    session: AsyncSession, data: PublicationCreate, auteur: User
) -> PublicationDetailRead:
    if data.format_code not in FORMATS_VALIDES:
        raise ApiError("invalid_format", f"Format inconnu : {data.format_code}.")

    caption = data.caption.strip()
    if not caption and data.captions_by_platform:
        first_caption = next((v.strip() for v in data.captions_by_platform.values() if v.strip()), "")
        caption = first_caption

    pub = Publication(
        title=data.title.strip(),
        caption=caption,
        captions_by_platform=data.captions_by_platform,
        format_code=data.format_code,
        status_code=STATUT_DRAFT,
        platform_codes=list(dict.fromkeys(data.platform_codes)),
        hashtags=_extraire_hashtags(caption, data.hashtags),
        media_items=data.media_items,
        scheduled_at=data.scheduled_at,
        id_users_author=auteur.id_users,
        id_users_validator=data.id_users_validator,
    )
    session.add(pub)
    await session.flush()

    session.add(
        PublicationEvent(
            id_publications=pub.id_publications,
            kind=EVENT_CREATED,
            label="Publication créée",
            id_users_author=auteur.id_users,
        )
    )

    if data.submit_for_validation:
        await _soumettre_et_notifier(session, pub, auteur, re_soumission=False)

    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)


async def modifier(
    session: AsyncSession, id_publications: int, data: PublicationUpdate, auteur: User
) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    if pub.status_code in (STATUT_PUBLISHED, STATUT_WITHDRAWN):
        raise ConflictError("Une publication déjà publiée ou retirée ne peut plus être modifiée.")

    if data.title is not None:
        pub.title = data.title.strip()
    if data.caption is not None:
        pub.caption = data.caption.strip()
        if data.hashtags is None:
            pub.hashtags = _extraire_hashtags(pub.caption, None)
    if data.captions_by_platform is not None:
        pub.captions_by_platform = data.captions_by_platform
    if data.platform_codes is not None and len(data.platform_codes) > 0:
        pub.platform_codes = list(dict.fromkeys(data.platform_codes))
    if data.hashtags is not None:
        pub.hashtags = _extraire_hashtags(pub.caption, data.hashtags)
    if data.scheduled_at is not None:
        pub.scheduled_at = data.scheduled_at
    if data.id_users_validator is not None:
        pub.id_users_validator = data.id_users_validator

    session.add(
        PublicationEvent(
            id_publications=pub.id_publications,
            kind=EVENT_MODIFIED,
            label="Publication modifiée",
            id_users_author=auteur.id_users,
        )
    )
    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)


async def soumettre(
    session: AsyncSession,
    id_publications: int,
    auteur: User,
    *,
    id_users_validator: int | None = None,
    comment: str | None = None,
) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    if pub.status_code not in (STATUT_DRAFT, STATUT_CHANGES_REQUESTED):
        raise ConflictError("Seul un brouillon ou une publication en correction peut être soumis.")
    re_soumission = pub.status_code == STATUT_CHANGES_REQUESTED
    if id_users_validator is not None:
        pub.id_users_validator = id_users_validator

    await _soumettre_et_notifier(
        session, pub, auteur, comment=comment, re_soumission=re_soumission
    )
    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)


async def suggerer_correction(
    session: AsyncSession,
    id_publications: int,
    validateur: User,
    comment: str,
) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    if pub.status_code in (STATUT_PUBLISHED, STATUT_WITHDRAWN):
        raise ConflictError("Impossible de suggérer une correction sur une publication déjà publiée.")

    texte = comment.strip()
    if not texte:
        raise ApiError("empty_comment", "Le commentaire de correction ne peut pas être vide.")

    pub.status_code = STATUT_CHANGES_REQUESTED
    pub.id_users_validator = validateur.id_users

    session.add(
        PublicationEvent(
            id_publications=pub.id_publications,
            kind=EVENT_CHANGES_REQUESTED,
            label="Correction suggérée",
            comment=texte,
            id_users_author=validateur.id_users,
        )
    )
    await notification_service.marquer_lues_par_entite(
        session,
        id_users_recipient=validateur.id_users,
        entity_type="publication",
        entity_id=pub.id_publications,
    )
    await notification_service.creer(
        session,
        id_users_recipient=pub.id_users_author,
        id_users_actor=validateur.id_users,
        notification_type=TYPE_CORRECTION_SUGGESTED,
        source_scope=SOURCE_INTERNAL,
        platform_code=None,
        title=f"Correction suggérée — « {pub.title} »",
        body=f"{validateur.nom_affiche} : « {texte} »",
        requires_action=True,
        action_label="Voir et corriger",
        action_url=f"/publications/{pub.id_publications}",
        entity_type="publication",
        entity_id=pub.id_publications,
    )

    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)


async def ajouter_commentaire(
    session: AsyncSession,
    id_publications: int,
    auteur: User,
    comment: str,
) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    texte = comment.strip()
    if not texte:
        raise ApiError("empty_comment", "Le commentaire ne peut pas être vide.")

    session.add(
        PublicationEvent(
            id_publications=pub.id_publications,
            kind=EVENT_COMMENT,
            label="Commentaire",
            comment=texte,
            id_users_author=auteur.id_users,
        )
    )

    # Notifier l'interlocuteur concerné.
    if auteur.id_users != pub.id_users_author:
        destinataires = [pub.id_users_author]
    else:
        destinataires = await _destinataires_validation(
            session, auteur=auteur, id_users_validator=pub.id_users_validator
        )
        destinataires = [uid for uid in destinataires if uid != auteur.id_users]

    for recipient_id in destinataires:
        await notification_service.creer(
            session,
            id_users_recipient=recipient_id,
            id_users_actor=auteur.id_users,
            notification_type=TYPE_TEAM_ACTIVITY,
            source_scope=SOURCE_INTERNAL,
            platform_code=None,
            title=f"Nouveau commentaire — « {pub.title} »",
            body=f"{auteur.nom_affiche} : « {texte} »",
            requires_action=False,
            action_label="Voir la discussion",
            action_url=f"/publications/{pub.id_publications}",
            entity_type="publication",
            entity_id=pub.id_publications,
        )

    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)


async def approuver(
    session: AsyncSession,
    id_publications: int,
    validateur: User,
    data: ApprovePublicationInput,
) -> PublicationDetailRead:
    pub = await _obtenir_entite(session, id_publications)
    if pub.status_code in (STATUT_PUBLISHED, STATUT_WITHDRAWN):
        raise ConflictError("Cette publication est déjà publiée ou retirée.")

    pub.id_users_validator = validateur.id_users
    publier_maintenant = data.publish_now or pub.scheduled_at is None

    await notification_service.marquer_lues_par_entite(
        session,
        id_users_recipient=validateur.id_users,
        entity_type="publication",
        entity_id=pub.id_publications,
    )

    if publier_maintenant:
        pub.status_code = STATUT_PUBLISHED
        pub.published_at = datetime.now(UTC)
        session.add(
            PublicationEvent(
                id_publications=pub.id_publications,
                kind=EVENT_PUBLISHED,
                label="Confirmée et publiée",
                comment=data.comment.strip() if data.comment and data.comment.strip() else None,
                id_users_author=validateur.id_users,
            )
        )
        primary_platform = pub.platform_codes[0] if pub.platform_codes else None
        reseaux = ", ".join(pub.platform_codes) if pub.platform_codes else "réseaux sociaux"
        await notification_service.creer(
            session,
            id_users_recipient=pub.id_users_author,
            id_users_actor=validateur.id_users,
            notification_type=TYPE_PUBLICATION_PUBLISHED,
            source_scope=SOURCE_PLATFORM if primary_platform else SOURCE_INTERNAL,
            platform_code=primary_platform,
            title=f"Publication publiée — « {pub.title} »",
            body=f"{validateur.nom_affiche} a confirmé et publié votre publication sur {reseaux}.",
            requires_action=False,
            action_label="Voir la publication",
            action_url=f"/publications/{pub.id_publications}",
            entity_type="publication",
            entity_id=pub.id_publications,
        )
    else:
        pub.status_code = STATUT_SCHEDULED
        session.add(
            PublicationEvent(
                id_publications=pub.id_publications,
                kind=EVENT_APPROVED,
                label="Approuvée et programmée",
                comment=data.comment.strip() if data.comment and data.comment.strip() else None,
                id_users_author=validateur.id_users,
            )
        )
        await notification_service.creer(
            session,
            id_users_recipient=pub.id_users_author,
            id_users_actor=validateur.id_users,
            notification_type=TYPE_PUBLICATION_APPROVED,
            source_scope=SOURCE_INTERNAL,
            platform_code=None,
            title=f"Publication approuvée — « {pub.title} »",
            body=f"{validateur.nom_affiche} a approuvé et programmé votre publication.",
            requires_action=False,
            action_label="Voir la publication",
            action_url=f"/publications/{pub.id_publications}",
            entity_type="publication",
            entity_id=pub.id_publications,
        )

    await session.commit()
    await session.refresh(pub)
    return await _hydrater_detail(session, pub)
