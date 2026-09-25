"""Accès aux tables de référence.

Les tables de référence (`platforms`, `social_account_statuses`, plus tard les statuts
de publication) traduisent un **code** stable en identifiant numérique. Ces valeurs ne
changent pratiquement jamais : on les garde donc en mémoire après la première lecture,
plutôt que d'interroger la base à chaque requête.

Le cache est volontairement simple. Une modification faite directement en base ne sera
visible qu'après redémarrage : c'est acceptable, puisque ces valeurs sont posées par
migration.
"""

from typing import Any, Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError


class ReferenceRow(Protocol):
    """Toute table de référence a un code et un libellé."""

    code: Any
    label: Any


T = TypeVar("T", bound=ReferenceRow)

# {nom de table: {code: identifiant}} et son inverse.
_codes_vers_id: dict[str, dict[str, int]] = {}
_id_vers_code: dict[str, dict[int, str]] = {}


def _cle_primaire(modele: type[Any]) -> str:
    return str(modele.__mapper__.primary_key[0].name)


async def _charger(session: AsyncSession, modele: type[Any]) -> None:
    table = str(modele.__tablename__)
    lignes: list[Any] = list((await session.execute(select(modele))).scalars().all())
    colonne = _cle_primaire(modele)
    _codes_vers_id[table] = {ligne.code: getattr(ligne, colonne) for ligne in lignes}
    _id_vers_code[table] = {getattr(ligne, colonne): ligne.code for ligne in lignes}


async def resolve_code(session: AsyncSession, modele: type[Any], code: str) -> int:
    """Renvoie l'identifiant correspondant à un code, ou lève NotFoundError."""
    table = str(modele.__tablename__)
    if table not in _codes_vers_id or code not in _codes_vers_id[table]:
        await _charger(session, modele)

    identifiant = _codes_vers_id.get(table, {}).get(code)
    if identifiant is None:
        raise NotFoundError(f"Valeur inconnue « {code} » dans {table}.", code="reference_not_found")
    return identifiant


async def code_of(session: AsyncSession, modele: type[Any], identifiant: int) -> str:
    """Renvoie le code correspondant à un identifiant."""
    table = str(modele.__tablename__)
    if table not in _id_vers_code or identifiant not in _id_vers_code[table]:
        await _charger(session, modele)

    code = _id_vers_code.get(table, {}).get(identifiant)
    if code is None:
        raise NotFoundError(
            f"Identifiant inconnu {identifiant} dans {table}.", code="reference_not_found"
        )
    return code


def clear_cache() -> None:
    """Vide le cache. Utilisé par les tests, qui repartent d'une base neuve."""
    _codes_vers_id.clear()
    _id_vers_code.clear()
