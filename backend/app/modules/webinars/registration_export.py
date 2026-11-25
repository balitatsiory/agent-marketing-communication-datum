"""Export CSV des inscrits d'un webinaire.

Le fichier est destiné à un tableur en français : séparateur « ; », UTF-8 avec
marque d'ordre des octets pour que les accents s'ouvrent juste.

Les noms viennent d'un formulaire public : une valeur commençant par « = », « + »,
« - » ou « @ » serait exécutée comme une formule par le tableur. Elle est
précédée d'une apostrophe, qui la force à rester du texte.

C'est une sortie de données personnelles : chaque export est journalisé, avec des
identifiants seulement.
"""

import csv
import io
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.webinars import service
from app.modules.webinars.constants import (
    EXPORT_COLUMNS,
    EXPORT_FORMULA_PREFIXES,
    EXPORT_SOURCE_LABELS,
)
from app.modules.webinars.models import WebinarRegistration

logger = logging.getLogger(__name__)


def _texte(valeur: str | None) -> str:
    """Valeur d'une cellule, neutralisée si un tableur la prendrait pour une formule."""
    if not valeur:
        return ""
    if valeur.lstrip(" ").startswith(EXPORT_FORMULA_PREFIXES):
        return f"'{valeur}"
    return valeur


def _date(valeur: datetime | None) -> str:
    return f"{valeur.astimezone(UTC):%Y-%m-%d %H:%M}" if valeur else ""


def _ligne(inscription: WebinarRegistration) -> list[str]:
    return [
        _texte(inscription.first_name),
        _texte(inscription.last_name),
        _texte(inscription.email),
        EXPORT_SOURCE_LABELS.get(inscription.source, inscription.source),
        _date(inscription.registered_at),
        "oui" if inscription.has_newsletter_consent else "non",
        _date(inscription.consented_at),
        _texte(inscription.zoom_status),
        _texte(inscription.zoom_error),
    ]


async def export_registrations(session: AsyncSession, id_webinars: int, par: User) -> str:
    """Tous les inscrits d'un webinaire, du plus ancien au plus récent.

    Les inscriptions effacées n'ont plus de données : elles n'y figurent pas. Le
    lien personnel de connexion n'est pas exporté, il vaut un accès à la séance.

    Raises:
        NotFoundError: webinaire inconnu ou archivé.
    """
    await service.charger(session, id_webinars)
    inscriptions = (
        (
            await session.execute(
                select(WebinarRegistration)
                .where(
                    WebinarRegistration.id_webinars == id_webinars,
                    WebinarRegistration.anonymized_at.is_(None),
                )
                .order_by(
                    WebinarRegistration.registered_at,
                    WebinarRegistration.id_webinar_registrations,
                )
            )
        )
        .scalars()
        .all()
    )
    sortie = io.StringIO()
    # La marque d'ordre des octets : sans elle, Excel lit l'UTF-8 comme du latin-1.
    sortie.write("\ufeff")
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(EXPORT_COLUMNS)
    ecrivain.writerows(_ligne(inscription) for inscription in inscriptions)
    logger.info(
        "Export des inscrits du webinaire %s : %s ligne(s), par l'utilisateur %s",
        id_webinars,
        len(inscriptions),
        par.id_users,
    )
    return sortie.getvalue()
