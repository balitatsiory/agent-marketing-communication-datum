"""Lecture des réseaux connus, pour les autres modules."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platforms.models import SocialPlatform


async def list_platforms(session: AsyncSession) -> list[SocialPlatform]:
    """Tous les réseaux, dans leur ordre d'affichage."""
    requete = select(SocialPlatform).order_by(SocialPlatform.sort_order)
    return list((await session.execute(requete)).scalars().all())
