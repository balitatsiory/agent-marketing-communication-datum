"""Forme des fichiers exportés du site datumacademy.com.

Les noms de champs sont ceux des fichiers (`data/reprise-webinaires`), donc en
français : ils décrivent une donnée d'entrée, pas l'API d'IAGORA. Tout champ
non listé est ignoré.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Ligne(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TexteBilingue(_Ligne):
    fr: str | None = None
    en: str | None = None


class DateCandidate(_Ligne):
    debut: str
    fin: str | None = None


class DateDetectee(_Ligne):
    iso: str
    heure: str | None = None
    fuseau: str | None = None
    extrait: str | None = None


class Evenement(_Ligne):
    debut_utc: str | None = None
    duree_minutes: int | None = None
    source_date: str | None = None
    date_candidate: DateCandidate | None = None
    dates_detectees: list[DateDetectee] = Field(default_factory=list)
    publication_approximative: str | None = None


class Replay(_Ligne):
    urls: list[str] = Field(default_factory=list)


class PageDeFiche(_Ligne):
    slug: str = Field(..., min_length=1, max_length=255)
    url: str
    active: bool = True


class Inscription(_Ligne):
    pages: list[PageDeFiche] = Field(default_factory=list)


class Flyer(_Ligne):
    url_source: str | None = None


class Source(_Ligne):
    url_detail_fr: str | None = None


class SiteWebinar(_Ligne):
    slug: str = Field(..., min_length=1, max_length=255)
    titre: TexteBilingue
    contenu: TexteBilingue = Field(default_factory=TexteBilingue)
    statut_suggere: str | None = None
    statut_motif: str | None = None
    categories: list[str] = Field(default_factory=list)
    evenement: Evenement = Field(default_factory=Evenement)
    replay: Replay | None = None
    inscription: Inscription = Field(default_factory=Inscription)
    flyer: Flyer | None = None
    source: Source = Field(default_factory=Source)
    liens_externes: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)


class SiteExport(_Ligne):
    """`webinaires.json`."""

    webinaires: list[SiteWebinar] = Field(..., max_length=2000)


class Candidat(_Ligne):
    slug: str
    score: float | None = Field(default=None, ge=0, le=1)


class SitePage(PageDeFiche):
    calendar_from: str | None = None
    calendar_to: str | None = None
    webinaire_rattache: str | None = None
    webinaire_candidat: Candidat | None = None
    remarque: str | None = None


class PagesExport(_Ligne):
    """`pages-inscription.json`."""

    pages: list[SitePage] = Field(..., max_length=2000)


class FlyerLigne(_Ligne):
    slug: str
    url_source: str


class FlyerManifest(_Ligne):
    """`flyers.manifest.json`."""

    flyers: list[FlyerLigne] = Field(..., max_length=2000)
