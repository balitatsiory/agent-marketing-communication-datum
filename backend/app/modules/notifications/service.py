"""Logique métier du module Notifications."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.pagination import PageParams
from app.modules.notifications.constants import (
    LIBELLES_TYPES_NOTIFICATION,
    SOURCE_INTERNAL,
    SOURCE_PLATFORM,
)
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationRead, NotificationStatsRead
from app.modules.users.models import User


def _initiales(utilisateur: User) -> str:
    return f"{utilisateur.first_name[:1]}{utilisateur.last_name[:1]}".upper() or utilisateur.email[:2].upper()


async def _hydrater(
    session: AsyncSession, notifications: Sequence[Notification]
) -> list[NotificationRead]:
    """Enrichit les notifications avec le nom et les initiales de l'acteur en une requête."""
    actor_ids = {n.id_users_actor for n in notifications if n.id_users_actor is not None}
    acteurs: dict[int, User] = {}
    if actor_ids:
        rows = (await session.execute(select(User).where(User.id_users.in_(actor_ids)))).scalars().all()
        acteurs = {u.id_users: u for u in rows}

    resultat: list[NotificationRead] = []
    for n in notifications:
        acteur = acteurs.get(n.id_users_actor) if n.id_users_actor is not None else None
        resultat.append(
            NotificationRead(
                id_notifications=n.id_notifications,
                id_users_recipient=n.id_users_recipient,
                id_users_actor=n.id_users_actor,
                actor_name=acteur.nom_affiche if acteur else None,
                actor_initials=_initiales(acteur) if acteur else None,
                notification_type=n.notification_type,
                notification_type_label=LIBELLES_TYPES_NOTIFICATION.get(
                    n.notification_type, n.notification_type
                ),
                source_scope=n.source_scope,
                platform_code=n.platform_code,
                title=n.title,
                body=n.body,
                requires_action=n.requires_action,
                action_label=n.action_label,
                action_url=n.action_url,
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                is_read=n.is_read,
                read_at=n.read_at,
                created_at=n.created_at,
            )
        )
    return resultat


async def creer(
    session: AsyncSession,
    *,
    id_users_recipient: int,
    notification_type: str,
    source_scope: str,
    title: str,
    body: str,
    id_users_actor: int | None = None,
    platform_code: str | None = None,
    requires_action: bool = False,
    action_label: str | None = None,
    action_url: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    """Crée une notification persistée en base."""
    notification = Notification(
        id_users_recipient=id_users_recipient,
        id_users_actor=id_users_actor,
        notification_type=notification_type,
        source_scope=source_scope,
        platform_code=platform_code,
        title=title,
        body=body,
        requires_action=requires_action,
        action_label=action_label,
        action_url=action_url,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(notification)
    await session.flush()
    return notification


async def marquer_lues_par_entite(
    session: AsyncSession,
    *,
    id_users_recipient: int,
    entity_type: str,
    entity_id: int,
) -> int:
    """Marque comme lues les notifications d'un utilisateur liées à une entité."""
    now = datetime.now(UTC)
    stmt = (
        update(Notification)
        .where(
            Notification.id_users_recipient == id_users_recipient,
            Notification.entity_type == entity_type,
            Notification.entity_id == entity_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    res = await session.execute(stmt)
    return int(res.rowcount or 0)


async def lister(
    session: AsyncSession,
    id_users: int,
    params: PageParams,
    *,
    q: str | None = None,
    source: str | None = None,
    types: Sequence[str] | None = None,
    platforms: Sequence[str] | None = None,
    unread_only: bool = False,
    requires_action: bool = False,
) -> tuple[list[NotificationRead], int]:
    """Liste paginée et filtrée des notifications de l'utilisateur courant."""
    conditions = [Notification.id_users_recipient == id_users]

    if unread_only:
        conditions.append(Notification.is_read.is_(False))
    if requires_action:
        conditions.append(Notification.requires_action.is_(True))
    if source in (SOURCE_INTERNAL, SOURCE_PLATFORM):
        conditions.append(Notification.source_scope == source)
    if types:
        conditions.append(Notification.notification_type.in_(list(types)))
    if platforms:
        platform_clauses = []
        for p in platforms:
            if p == SOURCE_INTERNAL:
                platform_clauses.append(Notification.source_scope == SOURCE_INTERNAL)
            else:
                platform_clauses.append(Notification.platform_code == p)
        if platform_clauses:
            conditions.append(or_(*platform_clauses))
    if q and q.strip():
        motif = f"%{q.strip()}%"
        conditions.append(or_(Notification.title.ilike(motif), Notification.body.ilike(motif)))

    total = (
        await session.execute(select(func.count()).select_from(Notification).where(*conditions))
    ).scalar_one()

    rows = (
        await session.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id_notifications.desc())
            .offset(params.offset)
            .limit(params.size)
        )
    ).scalars().all()

    return await _hydrater(session, rows), int(total)


async def statistiques(session: AsyncSession, id_users: int) -> NotificationStatsRead:
    """Agrégats pour le bloc de stats et les compteurs de l'aside de filtres."""
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.id_users_recipient == id_users)
            .order_by(Notification.created_at.desc(), Notification.id_notifications.desc())
        )
    ).scalars().all()

    total = len(rows)
    unread = 0
    action_required = 0
    internal_count = 0
    platform_count = 0
    by_type: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    pending_raw: list[Notification] = []

    for n in rows:
        if not n.is_read:
            unread += 1
            if n.requires_action:
                action_required += 1
                if len(pending_raw) < 5:
                    pending_raw.append(n)
        if n.source_scope == SOURCE_INTERNAL:
            internal_count += 1
        else:
            platform_count += 1

        by_type[n.notification_type] = by_type.get(n.notification_type, 0) + 1
        plat_key = n.platform_code if n.platform_code else SOURCE_INTERNAL
        by_platform[plat_key] = by_platform.get(plat_key, 0) + 1

    pending_actions = await _hydrater(session, pending_raw)
    return NotificationStatsRead(
        total=total,
        unread=unread,
        action_required=action_required,
        internal_count=internal_count,
        platform_count=platform_count,
        by_type=by_type,
        by_platform=by_platform,
        pending_actions=pending_actions,
    )


async def _obtenir_pour_utilisateur(
    session: AsyncSession, id_notifications: int, id_users: int
) -> Notification:
    notification = await session.get(Notification, id_notifications)
    if notification is None or notification.id_users_recipient != id_users:
        raise NotFoundError("Notification introuvable.")
    return notification


async def marquer_lue(
    session: AsyncSession, id_notifications: int, id_users: int, *, lue: bool = True
) -> NotificationRead:
    notification = await _obtenir_pour_utilisateur(session, id_notifications, id_users)
    notification.is_read = lue
    notification.read_at = datetime.now(UTC) if lue else None
    await session.flush()
    await session.commit()
    return (await _hydrater(session, [notification]))[0]


async def tout_marquer_lu(session: AsyncSession, id_users: int) -> int:
    now = datetime.now(UTC)
    stmt = (
        update(Notification)
        .where(
            Notification.id_users_recipient == id_users,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    res = await session.execute(stmt)
    await session.commit()
    return int(res.rowcount or 0)


async def supprimer(session: AsyncSession, id_notifications: int, id_users: int) -> None:
    notification = await _obtenir_pour_utilisateur(session, id_notifications, id_users)
    await session.delete(notification)
    await session.commit()
