"""Pagination commune à toutes les listes de l'API.

Une liste ne sort JAMAIS comme un tableau nu au premier niveau : un tableau nu
ne peut plus accueillir un total le jour où un écran en a besoin.
"""

from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel

TAILLE_MAX = 200


@dataclass(frozen=True)
class PageParams:
    """Paramètres de pagination, injectés en dépendance."""

    page: int = 1
    size: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: int = Query(1, ge=1, description="Numéro de page, à partir de 1."),
    size: int = Query(50, ge=1, le=TAILLE_MAX, description="Nombre d'éléments par page."),
) -> PageParams:
    return PageParams(page=page, size=size)


class Page[T](BaseModel):
    """Une page de résultats."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        pages = (total + params.size - 1) // params.size if total else 0
        return cls(items=items, total=total, page=params.page, size=params.size, pages=pages)
