"""Reprend les webinaires du site datumacademy.com dans la base d'IAGORA.

    python -m scripts.import_webinaires webinaires.json \
        --pages pages-inscription.json --flyers flyers.manifest.json --fetch-flyers

Rejouable sans doublon : une fiche est retrouvée par son slug, et ce qui a été
modifié à la main n'est pas réécrit. `--fetch-flyers` télécharge ensuite les
visuels depuis le site et les dépose dans le stockage configuré (local ou R2).

La même reprise se fait depuis l'écran Webinaires, bouton « Importer ».
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.database import SessionFactory
from app.core.errors import ApiError
from app.core.storage import get_stockage
from app.modules.webinars import flyers, importer
from app.modules.webinars.constants import FLYER_BATCH_MAX
from app.modules.webinars.import_schemas import FlyerManifest, PagesExport, SiteExport


def _arguments() -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(description="Importer les webinaires du site.")
    analyseur.add_argument("webinaires", type=Path, help="webinaires.json")
    analyseur.add_argument("--pages", type=Path, help="pages-inscription.json")
    analyseur.add_argument("--flyers", type=Path, help="flyers.manifest.json")
    analyseur.add_argument(
        "--fetch-flyers", action="store_true", help="Rapatrier aussi les visuels."
    )
    return analyseur.parse_args()


async def importer_fichiers(arguments: argparse.Namespace) -> int:
    try:
        export = importer.lire_fichier(
            arguments.webinaires.read_bytes(), SiteExport, arguments.webinaires.name
        )
        pages = (
            importer.lire_fichier(arguments.pages.read_bytes(), PagesExport, arguments.pages.name)
            if arguments.pages
            else None
        )
        manifeste = (
            importer.lire_fichier(
                arguments.flyers.read_bytes(), FlyerManifest, arguments.flyers.name
            )
            if arguments.flyers
            else None
        )
    except (OSError, ApiError) as erreur:
        print(f"Refus : {erreur}", file=sys.stderr)
        return 1

    async with SessionFactory() as session:
        rapport = await importer.import_site_export(session, export, pages, manifeste)
        await session.commit()
    print(
        f"Fiches : {rapport.webinars_created} créée(s), {rapport.webinars_updated} "
        f"actualisée(s), {rapport.webinars_kept} conservée(s).\n"
        f"Pages d'inscription : {rapport.pages_created} créée(s), "
        f"{rapport.pages_updated} actualisée(s).\n"
        f"Dates à confirmer : {rapport.dates_to_confirm}. "
        f"Flyers à rapatrier : {rapport.pending_flyers}."
    )
    for avertissement in rapport.warnings:
        print(f"Attention : {avertissement}")

    if not arguments.fetch_flyers:
        return 0
    stockes = echecs = 0
    # Le premier lot reprend aussi les échecs d'une exécution précédente.
    reprise = True
    while True:
        # Une transaction par lot : une interruption ne perd que le lot en cours.
        async with SessionFactory() as session:
            lot = await flyers.fetch_pending_flyers(
                session, get_stockage(), FLYER_BATCH_MAX, retry_failed=reprise
            )
            await session.commit()
        reprise = False
        stockes += lot.stored
        echecs += lot.failed
        for erreur_flyer in lot.errors:
            print(f"Flyer refusé — {erreur_flyer.title} : {erreur_flyer.message}")
        print(f"Flyers : {stockes} rapatrié(s), {echecs} en échec, {lot.remaining} restant(s).")
        if lot.remaining == 0 or lot.stored + lot.failed == 0:
            return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(importer_fichiers(_arguments())))
