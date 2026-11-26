"""Reprend les logos d'organisations comme médias de référence de nature « logo ».

    python -m scripts.import_logos_organisations organisations.json

La base et le stockage sont ceux de la configuration : le script les annonce
avant d'écrire. Rejouable sans doublon. Du fichier, seuls le nom, le texte
alternatif et le logo sont conservés ; rôle, site et remarque n'ont pas de
colonne.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.storage import get_stockage
from app.modules.media.import_schemas import OrganisationsExport
from app.modules.media.logo_import import LogoOutcome, import_logos


def _arguments() -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(description="Importer les logos d'organisations.")
    analyseur.add_argument("fichier", type=Path, help="organisations.json")
    return analyseur.parse_args()


async def importer_fichier(chemin: Path) -> int:
    try:
        export = OrganisationsExport.model_validate_json(chemin.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValidationError) as erreur:
        print(f"Refus : {erreur}", file=sys.stderr)
        return 1

    reglages = get_settings()
    base = reglages.DATABASE_URL.path or ""
    print(f"Base : {base.lstrip('/')} · stockage : {reglages.STORAGE_BACKEND}")
    lues = len(export.organisations)
    if export.announced_count is not None and export.announced_count != lues:
        print(
            f"Attention : le fichier annonce {export.announced_count} organisations "
            f"mais en contient {lues}."
        )

    resultats = await import_logos(SessionFactory, get_stockage(), export.organisations)
    for resultat in resultats:
        print(f"[{resultat.outcome}] {resultat.code} : {resultat.message}")
        if resultat.storage_key:
            print(f"    {resultat.storage_key}")
        for avertissement in resultat.warnings:
            print(f"    Attention : {avertissement}")

    bilan = Counter(resultat.outcome for resultat in resultats)
    print(
        f"{bilan[LogoOutcome.IMPORTED]} importé(s), "
        f"{bilan[LogoOutcome.ALREADY_PRESENT]} déjà présent(s), "
        f"{bilan[LogoOutcome.SKIPPED]} laissé(s) tel(s) quel(s), "
        f"{bilan[LogoOutcome.FAILED]} en échec."
    )
    return 1 if bilan[LogoOutcome.FAILED] else 0


if __name__ == "__main__":
    # La console Windows n'est pas toujours en UTF-8 : un nom accentué ne doit rien casser.
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(errors="replace")
    sys.exit(asyncio.run(importer_fichier(_arguments().fichier)))
