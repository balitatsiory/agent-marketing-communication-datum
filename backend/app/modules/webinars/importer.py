"""Reprise des webinaires du site datumacademy.com à partir des fichiers JSON.

L'import peut être rejoué : une fiche est retrouvée par son slug. Il ne réécrit
ni une fiche modifiée à la main, ni une fiche archivée, ni un rattachement de
page déjà établi.

Les dates des fichiers sont souvent déduites (page d'inscription rapprochée,
date lue dans le texte) : elles sont enregistrées « à confirmer ».
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.users.models import User
from app.modules.webinars import service
from app.modules.webinars.constants import (
    LINK_MANUAL,
    ORIGIN_SITE_IMPORT,
    PAGE_EXTERNAL,
    REGISTRATION_EXTERNAL,
    REGISTRATION_NONE,
    STATUS_DRAFT,
    STATUS_PAST,
    STATUS_SCHEDULED,
    TYPE_SITE_WEBINAR,
)
from app.modules.webinars.import_schemas import (
    Evenement,
    FlyerManifest,
    PageDeFiche,
    PagesExport,
    SiteExport,
    SitePage,
    SiteWebinar,
)
from app.modules.webinars.models import (
    Webinar,
    WebinarCategory,
    WebinarRegistrationPage,
)
from app.modules.webinars.schemas import ImportReport

logger = logging.getLogger(__name__)

STATUTS_CONNUS = (STATUS_DRAFT, STATUS_SCHEDULED, STATUS_PAST)
# Décalages cités dans les textes du site.
FUSEAUX = {"GMT": 0, "UTC": 0, "CET": 1, "GMT+1": 1, "UTC+1": 1, "CEST": 2, "GMT+2": 2, "GMT+3": 3}
# Heure retenue quand seul le jour est connu : à midi UTC, le jour affiché reste
# le même dans tous les fuseaux d'Europe et d'Afrique.
HEURE_INCONNUE = 12


@dataclass(frozen=True)
class DateReprise:
    starts_at: datetime | None
    duration_minutes: int | None
    is_confirmed: bool
    is_time_known: bool


def lire_fichier[T: BaseModel](contenu: bytes, modele: type[T], nom: str) -> T:
    """Lit et contrôle un fichier JSON.

    Raises:
        ApiError: fichier illisible ou d'une autre forme que l'export attendu.
    """
    try:
        return modele.model_validate(json.loads(contenu.decode("utf-8-sig")))
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ApiError(
            "invalid_import_file", f"{nom} n'est pas un JSON en UTF-8 lisible.", 422
        ) from erreur
    except ValidationError as erreur:
        premiere = erreur.errors()[0]
        chemin = ".".join(str(morceau) for morceau in premiere["loc"])
        raise ApiError(
            "invalid_import_file",
            f"{nom} n'a pas la forme attendue : champ « {chemin} » absent ou invalide.",
            422,
        ) from erreur


def normaliser_slug(texte: str) -> str:
    """Slug sans accents ni caractères encodés, casse conservée."""
    ascii_ = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_-]+", "-", ascii_).strip("-")


def _adresse(valeur: str | None) -> str | None:
    """L'adresse si elle est en http(s), sinon rien."""
    if not valeur:
        return None
    morceaux = urlsplit(valeur)
    return valeur if morceaux.scheme in ("http", "https") and morceaux.netloc else None


def _horodatage(valeur: str | None) -> datetime | None:
    """Date du fichier ; sans fuseau, elle est lue en UTC."""
    if not valeur:
        return None
    try:
        lue = datetime.fromisoformat(valeur)
    except ValueError:
        return None
    return lue if lue.tzinfo else lue.replace(tzinfo=UTC)


def _jour(valeur: str | None) -> date | None:
    lu = _horodatage(valeur)
    return lu.date() if lu else None


def dater(evenement: Evenement) -> DateReprise:
    """Meilleure date disponible : sûre, puis candidate, puis lue dans le texte."""
    sure = _horodatage(evenement.debut_utc)
    if sure is not None:
        return DateReprise(sure, evenement.duree_minutes, True, True)

    if evenement.date_candidate is not None:
        debut = _horodatage(evenement.date_candidate.debut)
        fin = _horodatage(evenement.date_candidate.fin)
        if debut is not None:
            duree = int((fin - debut) / timedelta(minutes=1)) if fin and fin > debut else None
            return DateReprise(debut, duree, False, True)

    for detectee in evenement.dates_detectees:
        jour = _jour(detectee.iso)
        if jour is None:
            continue
        heure = re.fullmatch(r"(\d{1,2}):(\d{2})", detectee.heure or "")
        if heure is None:
            quand = datetime(jour.year, jour.month, jour.day, HEURE_INCONNUE, tzinfo=UTC)
            return DateReprise(quand, None, False, False)
        fuseau = timezone(timedelta(hours=FUSEAUX.get(detectee.fuseau or "", 0)))
        quand = datetime(
            jour.year, jour.month, jour.day, int(heure[1]), int(heure[2]), tzinfo=fuseau
        )
        return DateReprise(quand.astimezone(UTC), None, False, True)

    return DateReprise(None, evenement.duree_minutes, True, True)


async def _codes_categories(session: AsyncSession, libelles: set[str]) -> dict[str, str]:
    """Code de chaque libellé, en créant les catégories encore inconnues."""
    lignes = await session.execute(
        select(WebinarCategory.label, WebinarCategory.code, WebinarCategory.sort_order)
    )
    connues: dict[str, str] = {}
    rang = 0
    for nom, code_connu, ordre in lignes.all():
        connues[nom.casefold()] = code_connu
        rang = max(rang, ordre)
    resultat: dict[str, str] = {}
    for libelle in sorted(libelles):
        cle = libelle.casefold()
        if cle not in connues:
            connues[cle] = normaliser_slug(libelle).lower().replace("-", "_")[:60]
            rang += 10
            session.add(WebinarCategory(code=connues[cle], label=libelle[:120], sort_order=rang))
        resultat[libelle] = connues[cle]
    await session.flush()
    return resultat


def _page_principale(pages: list[PageDeFiche]) -> PageDeFiche | None:
    """La page d'inscription en ligne de préférence à celle du présentiel."""
    return min(pages, key=lambda p: ("presentiel" in p.slug.lower(), len(p.slug)), default=None)


def _remplir(webinaire: Webinar, ligne: SiteWebinar, flyer_url: str | None) -> None:
    quand = dater(ligne.evenement)
    webinaire.title = (ligne.titre.fr or ligne.titre.en or ligne.slug).strip()[:255]
    webinaire.title_en = (ligne.titre.en or "").strip()[:255] or None
    webinaire.description = (ligne.contenu.fr or "").strip() or None
    webinaire.description_en = (ligne.contenu.en or "").strip() or None
    webinaire.starts_at = quand.starts_at
    webinaire.duration_minutes = quand.duration_minutes or None
    webinaire.is_date_confirmed = quand.is_confirmed
    webinaire.is_time_known = quand.is_time_known
    webinaire.published_on = _jour(ligne.evenement.publication_approximative)
    webinaire.replay_url = (
        _adresse(ligne.replay.urls[0]) if ligne.replay and ligne.replay.urls else None
    )
    webinaire.source_url = _adresse(ligne.source.url_detail_fr)
    nouveau_flyer = _adresse(flyer_url)
    if nouveau_flyer != webinaire.flyer_source_url:
        # Une autre adresse est un autre fichier : à rapatrier de nouveau.
        webinaire.flyer_source_url = nouveau_flyer
        webinaire.flyer_storage_key = None
        webinaire.flyer_sha256 = None
        webinaire.flyer_byte_size = None
        webinaire.flyer_error = None
    page = _page_principale(ligne.inscription.pages)
    adresse = _adresse(page.url) if page else None
    webinaire.registration_mode = REGISTRATION_EXTERNAL if adresse else REGISTRATION_NONE
    webinaire.registration_url = adresse
    webinaire.import_details_json = {
        "anomalies": ligne.anomalies,
        "statut_motif": ligne.statut_motif,
        "date_source": ligne.evenement.source_date,
        "dates_detectees": [d.model_dump() for d in ligne.evenement.dates_detectees],
        "liens_externes": ligne.liens_externes,
    }


async def _importer_webinaires(
    session: AsyncSession,
    export: SiteExport,
    flyers: dict[str, str],
    par: User | None,
    rapport: ImportReport,
) -> dict[str, Webinar]:
    existants = {
        webinaire.external_site_slug: webinaire
        for webinaire in (
            await session.execute(select(Webinar).where(Webinar.external_site_slug.is_not(None)))
        ).scalars()
    }
    codes = await _codes_categories(
        session, {nom for ligne in export.webinaires for nom in ligne.categories}
    )
    id_type = await service.id_type(session, TYPE_SITE_WEBINAR)
    statuts = {code: await service.id_statut(session, code) for code in STATUTS_CONNUS}

    par_slug: dict[str, Webinar] = {}
    for ligne in export.webinaires:
        if ligne.slug in par_slug:
            rapport.warnings.append(f"Slug en double ignoré : {ligne.slug}")
            continue
        webinaire = existants.get(ligne.slug)
        if webinaire is not None and (
            webinaire.deleted_at is not None or webinaire.id_users_changed_by is not None
        ):
            rapport.webinars_kept += 1
            par_slug[ligne.slug] = webinaire
            continue
        nouveau = webinaire is None
        if webinaire is None:
            webinaire = Webinar(
                external_site_slug=ligne.slug,
                origin=ORIGIN_SITE_IMPORT,
                id_webinar_types=id_type,
                link_mode=LINK_MANUAL,
                id_users_created_by=par.id_users if par else None,
            )
            rapport.webinars_created += 1
        else:
            rapport.webinars_updated += 1
        webinaire.id_webinar_statuses = statuts.get(
            ligne.statut_suggere or "", statuts[STATUS_PAST]
        )
        _remplir(
            webinaire,
            ligne,
            flyers.get(ligne.slug) or (ligne.flyer.url_source if ligne.flyer else None),
        )
        if nouveau:
            session.add(webinaire)
        await session.flush()
        await service.definir_categories(
            session, webinaire.id_webinars, [codes[nom] for nom in ligne.categories]
        )
        par_slug[ligne.slug] = webinaire
    return par_slug


def _pages_a_importer(export: SiteExport, pages: PagesExport | None) -> dict[str, SitePage]:
    """Une entrée par slug : le fichier des pages, complété par celles citées dans les fiches."""
    resultat = {page.slug: page for page in pages.pages} if pages else {}
    for ligne in export.webinaires:
        for page in ligne.inscription.pages:
            if page.slug not in resultat:
                resultat[page.slug] = SitePage(**page.model_dump(), webinaire_rattache=ligne.slug)
            elif resultat[page.slug].webinaire_rattache is None:
                resultat[page.slug].webinaire_rattache = ligne.slug
    return resultat


async def _importer_pages(
    session: AsyncSession,
    pages: dict[str, SitePage],
    webinaires: dict[str, Webinar],
    rapport: ImportReport,
) -> None:
    existantes = {
        page.slug: page
        for page in (
            await session.execute(
                select(WebinarRegistrationPage).where(WebinarRegistrationPage.kind == PAGE_EXTERNAL)
            )
        ).scalars()
    }

    def identifiant(slug: str | None) -> int | None:
        if slug is None:
            return None
        webinaire = webinaires.get(slug)
        if webinaire is None:
            rapport.warnings.append(f"Page rattachée à une fiche absente : {slug}")
            return None
        return webinaire.id_webinars

    for slug, ligne in pages.items():
        adresse = _adresse(ligne.url)
        if adresse is None:
            rapport.warnings.append(f"Page ignorée, adresse invalide : {slug}")
            continue
        page = existantes.get(slug)
        if page is None:
            page = WebinarRegistrationPage(kind=PAGE_EXTERNAL, slug=slug)
            session.add(page)
            rapport.pages_created += 1
        else:
            rapport.pages_updated += 1
        page.url = adresse
        page.is_active = ligne.active
        page.event_starts_at = _horodatage(ligne.calendar_from)
        page.event_ends_at = _horodatage(ligne.calendar_to)
        page.note = ligne.remarque
        if page.id_webinars is None:
            page.id_webinars = identifiant(ligne.webinaire_rattache)
        candidat = ligne.webinaire_candidat
        page.id_webinars_candidate = identifiant(candidat.slug) if candidat else None
        page.candidate_score = (
            Decimal(str(round(candidat.score, 3)))
            if candidat and candidat.score is not None
            else None
        )
    await session.flush()


async def import_site_export(
    session: AsyncSession,
    export: SiteExport,
    pages: PagesExport | None = None,
    manifest: FlyerManifest | None = None,
    par: User | None = None,
) -> ImportReport:
    """Enregistre les webinaires et les pages d'inscription des fichiers du site."""
    rapport = ImportReport(
        webinars_created=0,
        webinars_updated=0,
        webinars_kept=0,
        pages_created=0,
        pages_updated=0,
        dates_to_confirm=0,
        pending_flyers=0,
        warnings=[],
    )
    flyers = {ligne.slug: ligne.url_source for ligne in manifest.flyers} if manifest else {}
    webinaires = await _importer_webinaires(session, export, flyers, par, rapport)
    await _importer_pages(session, _pages_a_importer(export, pages), webinaires, rapport)

    actifs = (Webinar.deleted_at.is_(None), Webinar.origin == ORIGIN_SITE_IMPORT)
    rapport.dates_to_confirm = (
        await session.execute(
            select(func.count())
            .select_from(Webinar)
            .where(*actifs, Webinar.is_date_confirmed.is_(False))
        )
    ).scalar_one()
    rapport.pending_flyers = (
        await session.execute(
            select(func.count())
            .select_from(Webinar)
            .where(
                *actifs,
                Webinar.flyer_source_url.is_not(None),
                Webinar.flyer_storage_key.is_(None),
            )
        )
    ).scalar_one()
    logger.info(
        "Import du site : %s fiche(s) créée(s), %s actualisée(s)",
        rapport.webinars_created,
        rapport.webinars_updated,
    )
    return rapport
