"""Lecture des webinaires : filtres, tris et mise en forme des fiches.

Séparé de `service.py` (écritures) pour que chacun reste lisible.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Select,
    and_,
    case,
    cast,
    func,
    literal_column,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import Stockage
from app.modules.webinars.constants import (
    DEFAULT_DURATION_MINUTES,
    ORIGIN_SITE_IMPORT,
    PAGE_IAGORA_FORM,
    STATUS_PAST,
    STATUS_SCHEDULED,
)
from app.modules.webinars.models import (
    Webinar,
    WebinarCategory,
    WebinarCategoryLink,
    WebinarRegistration,
    WebinarRegistrationPage,
    WebinarStatus,
    WebinarType,
)
from app.modules.webinars.schemas import RefItem, SortDirection, SortKey, WebinarListItem
from app.modules.zoom_accounts import service as zoom_accounts_service

LONGUEUR_EXTRAIT = 220

# Une fiche avec ses deux référentiels.
type Ligne = tuple[Webinar, WebinarStatus, WebinarType]


@dataclass(frozen=True)
class WebinarFilters:
    """Filtres communs à la liste et aux statistiques."""

    status: str | None = None
    type_code: str | None = None
    category: str | None = None
    id_zoom_accounts: int | None = None
    unassigned: bool = False
    search: str | None = None


def statut_effectif() -> ColumnElement[str]:
    """Code d'état affiché : un événement « à venir » dont la fin est passée est « passé »."""
    duree = func.coalesce(Webinar.duration_minutes, DEFAULT_DURATION_MINUTES)
    fin = Webinar.starts_at + duree * literal_column("interval '1 minute'")
    return case(
        (
            and_(
                WebinarStatus.code == STATUS_SCHEDULED,
                Webinar.starts_at.is_not(None),
                fin < func.now(),
            ),
            literal_column(f"'{STATUS_PAST}'"),
        ),
        else_=WebinarStatus.code,
    )


def est_passe(code_statut: str, debut: datetime | None, duree: int | None) -> str:
    """Même règle que `statut_effectif`, pour une fiche déjà chargée."""
    if code_statut != STATUS_SCHEDULED or debut is None:
        return code_statut
    fin = debut + timedelta(minutes=duree or DEFAULT_DURATION_MINUTES)
    return STATUS_PAST if fin < datetime.now(UTC) else code_statut


def _echapper_like(texte: str) -> str:
    return texte.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def appliquer_filtres[*Ts](requete: Select[*Ts], filtres: WebinarFilters) -> Select[*Ts]:
    """Restreint une requête qui joint déjà `webinar_statuses` et `webinar_types`."""
    requete = requete.where(Webinar.deleted_at.is_(None))
    if filtres.status:
        requete = requete.where(statut_effectif() == filtres.status)
    if filtres.type_code:
        requete = requete.where(WebinarType.code == filtres.type_code)
    if filtres.id_zoom_accounts is not None:
        requete = requete.where(Webinar.id_zoom_accounts == filtres.id_zoom_accounts)
    elif filtres.unassigned:
        requete = requete.where(Webinar.id_zoom_accounts.is_(None))
    if filtres.category:
        requete = requete.where(
            select(WebinarCategoryLink.id_webinar_category_links)
            .join(
                WebinarCategory,
                WebinarCategory.id_webinar_categories == WebinarCategoryLink.id_webinar_categories,
            )
            .where(
                WebinarCategoryLink.id_webinars == Webinar.id_webinars,
                WebinarCategory.code == filtres.category,
            )
            .exists()
        )
    if filtres.search:
        motif = f"%{_echapper_like(filtres.search.strip())}%"
        requete = requete.where(
            or_(
                Webinar.title.ilike(motif, escape="\\"),
                Webinar.title_en.ilike(motif, escape="\\"),
            )
        )
    return requete


def requete_de_base() -> Select[Webinar, WebinarStatus, WebinarType]:
    return (
        select(Webinar, WebinarStatus, WebinarType)
        .join(WebinarStatus, WebinarStatus.id_webinar_statuses == Webinar.id_webinar_statuses)
        .join(WebinarType, WebinarType.id_webinar_types == Webinar.id_webinar_types)
    )


def trier(
    requete: Select[Webinar, WebinarStatus, WebinarType],
    cle: SortKey,
    sens: SortDirection,
) -> Select[Webinar, WebinarStatus, WebinarType]:
    """Ordonne la liste. L'identifiant départage les égalités : la pagination reste stable."""
    expression: ColumnElement[Any]
    if cle == "title":
        expression = func.lower(Webinar.title)
    elif cle == "registrations":
        expression = (
            select(func.count())
            .select_from(WebinarRegistration)
            .where(WebinarRegistration.id_webinars == Webinar.id_webinars)
            .scalar_subquery()
        )
    elif cle == "created":
        expression = Webinar.created_at.expression
    else:
        # Sans date de séance, la date de publication sur le site situe la fiche.
        expression = func.coalesce(
            Webinar.starts_at, cast(Webinar.published_on, DateTime(timezone=True))
        )
    ordonne = expression.asc() if sens == "asc" else expression.desc()
    departage = Webinar.id_webinars.asc() if sens == "asc" else Webinar.id_webinars.desc()
    return requete.order_by(ordonne.nulls_last(), departage)


async def lire_lignes(
    session: AsyncSession, requete: Select[Webinar, WebinarStatus, WebinarType]
) -> list[Ligne]:
    """Exécute une requête issue de `requete_de_base`."""
    resultat = await session.execute(requete)
    return [(ligne[0], ligne[1], ligne[2]) for ligne in resultat.all()]


# ---------------------------------------------------------------------------
# Mise en forme
# ---------------------------------------------------------------------------


async def categories_par_webinaire(
    session: AsyncSession, identifiants: Sequence[int]
) -> dict[int, list[RefItem]]:
    if not identifiants:
        return {}
    lignes = await session.execute(
        select(WebinarCategoryLink.id_webinars, WebinarCategory.code, WebinarCategory.label)
        .join(
            WebinarCategory,
            WebinarCategory.id_webinar_categories == WebinarCategoryLink.id_webinar_categories,
        )
        .where(WebinarCategoryLink.id_webinars.in_(identifiants))
        .order_by(WebinarCategory.sort_order)
    )
    resultat: dict[int, list[RefItem]] = {}
    for id_webinars, code, label in lignes.all():
        resultat.setdefault(id_webinars, []).append(RefItem(code=code, label=label))
    return resultat


async def inscriptions_par_webinaire(
    session: AsyncSession, identifiants: Sequence[int]
) -> dict[int, tuple[int, int]]:
    """Pour chaque webinaire : (inscrits, dont consentants)."""
    if not identifiants:
        return {}
    lignes = await session.execute(
        select(
            WebinarRegistration.id_webinars,
            func.count(),
            func.count().filter(WebinarRegistration.has_newsletter_consent),
        )
        .where(WebinarRegistration.id_webinars.in_(identifiants))
        .group_by(WebinarRegistration.id_webinars)
    )
    return {identifiant: (total, accord) for identifiant, total, accord in lignes.all()}


async def _formulaires_par_webinaire(
    session: AsyncSession, identifiants: Sequence[int]
) -> dict[int, str]:
    if not identifiants:
        return {}
    lignes = await session.execute(
        select(WebinarRegistrationPage.id_webinars, WebinarRegistrationPage.slug).where(
            WebinarRegistrationPage.id_webinars.in_(identifiants),
            WebinarRegistrationPage.kind == PAGE_IAGORA_FORM,
            WebinarRegistrationPage.is_active,
        )
    )
    return {identifiant: slug for identifiant, slug in lignes.all() if identifiant is not None}


async def libelles_statuts(session: AsyncSession) -> dict[str, str]:
    lignes = await session.execute(
        select(WebinarStatus.code, WebinarStatus.label).order_by(WebinarStatus.sort_order)
    )
    return dict(lignes.all())


def adresse_flyer(webinaire: Webinar, stockage: Stockage) -> str | None:
    """Le flyer rapatrié, sinon son adresse d'origine."""
    if webinaire.flyer_storage_key:
        return stockage.url_publique(webinaire.flyer_storage_key)
    return webinaire.flyer_source_url


def _extrait(texte: str | None) -> str | None:
    if not texte:
        return None
    if len(texte) <= LONGUEUR_EXTRAIT:
        return texte
    return texte[:LONGUEUR_EXTRAIT].rsplit(" ", 1)[0] + "…"


async def mettre_en_forme(
    session: AsyncSession,
    stockage: Stockage,
    lignes: Sequence[Ligne],
) -> list[WebinarListItem]:
    """Fiches de liste, avec leurs rattachements chargés en une fois."""
    identifiants = [webinaire.id_webinars for webinaire, _, _ in lignes]
    categories = await categories_par_webinaire(session, identifiants)
    inscriptions = await inscriptions_par_webinaire(session, identifiants)
    formulaires = await _formulaires_par_webinaire(session, identifiants)
    statuts = await libelles_statuts(session)
    comptes = await zoom_accounts_service.list_labels(session)

    fiches: list[WebinarListItem] = []
    for webinaire, statut, type_evenement in lignes:
        identifiant = webinaire.id_webinars
        code = est_passe(statut.code, webinaire.starts_at, webinaire.duration_minutes)
        total = inscriptions.get(identifiant, (0, 0))[0]
        # Les inscriptions du site ne sont pas dans les fichiers repris : zéro y
        # voudrait dire « personne », alors que la vérité est « inconnu ».
        inconnu = webinaire.origin == ORIGIN_SITE_IMPORT and total == 0
        fin = (
            webinaire.starts_at + timedelta(minutes=webinaire.duration_minutes)
            if webinaire.starts_at and webinaire.duration_minutes
            else None
        )
        fiches.append(
            WebinarListItem(
                id_webinars=identifiant,
                title=webinaire.title,
                status_code=code,
                status_label=statuts.get(code, code),
                type_code=type_evenement.code,
                type_label=type_evenement.label,
                origin=webinaire.origin,  # type: ignore[arg-type]
                categories=categories.get(identifiant, []),
                id_zoom_accounts=webinaire.id_zoom_accounts,
                zoom_account_label=(
                    comptes.get(webinaire.id_zoom_accounts)
                    if webinaire.id_zoom_accounts is not None
                    else None
                ),
                external_zoom_meeting_id=webinaire.external_zoom_meeting_id,
                starts_at=webinaire.starts_at,
                ends_at=fin,
                is_date_confirmed=webinaire.is_date_confirmed,
                is_time_known=webinaire.is_time_known,
                published_on=webinaire.published_on,
                duration_minutes=webinaire.duration_minutes,
                join_url=webinaire.join_url,
                registration_mode=webinaire.registration_mode,  # type: ignore[arg-type]
                registration_url=webinaire.registration_url,
                form_slug=formulaires.get(identifiant),
                replay_url=webinaire.replay_url,
                flyer_url=adresse_flyer(webinaire, stockage),
                registration_count=None if inconnu else total,
                excerpt=_extrait(webinaire.description or webinaire.description_en),
            )
        )
    return fiches
