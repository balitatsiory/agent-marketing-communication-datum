"""Rendu d'un courriel : la coquille, le corps du modèle, et les variables.

Un modèle ne porte que son CORPS. La bannière et la signature vivent une seule
fois, dans `templates/coquille.html` : sans cela, changer le logo demanderait de
rouvrir chaque modèle, et un modèle oublié enverrait l'ancien.

Les variables s'écrivent `{{nom}}`. Deux règles :

1. Toute valeur substituée est ÉCHAPPÉE. Une valeur vient d'une saisie ou d'un
   inscrit : laisser passer du HTML, ce serait accepter qu'un titre de webinaire
   referme une balise et casse la mise en page de tous les destinataires.
2. Une variable sans valeur reste visible telle quelle, accolades comprises.
   Un trou béant dans l'aperçu se voit ; une chaîne vide ne se voit pas.
"""

import html
import re
from functools import lru_cache
from pathlib import Path

from app.modules.newsletter.constants import VALEURS_COQUILLE

DOSSIER_TEMPLATES = Path(__file__).parent / "templates"

# `{{ nom }}` ou `{{nom}}` : les espaces intérieurs sont tolérés, parce qu'on
# les écrit sans y penser.
MOTIF_VARIABLE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

# Balises dont le contenu ne doit pas se retrouver dans la version texte.
MOTIF_BLOCS_MUETS = re.compile(r"<(script|style|head)[^>]*>.*?</\1>", re.S | re.I)
MOTIF_COMMENTAIRE = re.compile(r"<!--.*?-->", re.S)
MOTIF_BALISE = re.compile(r"<[^>]+>")
MOTIF_LIGNES_VIDES = re.compile(r"\n{3,}")

# Le pré-entête est suivi d'un rembourrage de caractères invisibles, qui empêche
# la boîte de réception d'afficher le début du message à sa suite. Invisible en
# HTML, il ressortirait tel quel dans la version texte.
MOTIF_REMBOURRAGE = re.compile(
    "[" + "".join(chr(c) for c in (0x034F, 0x200B, 0x200C, 0x200D, 0x00A0, 0xFEFF)) + "]+"
)


@lru_cache(maxsize=1)
def coquille() -> str:
    """La coquille, lue une fois puis gardée en mémoire."""
    return (DOSSIER_TEMPLATES / "coquille.html").read_text(encoding="utf-8")


def corps_standard(fichier: str) -> str:
    """Le corps d'un modèle standard, lu dans `templates/corps/`."""
    chemin = (DOSSIER_TEMPLATES / "corps" / fichier).resolve()
    dossier = (DOSSIER_TEMPLATES / "corps").resolve()
    # Le nom vient de nos constantes, jamais d'une requête ; la vérification
    # coûte une ligne et interdit qu'un jour elle en vienne.
    if dossier not in chemin.parents:
        raise ValueError(f"Corps de modèle hors du dossier prévu : {fichier}")
    return chemin.read_text(encoding="utf-8")


def variables_de(*textes: str) -> list[str]:
    """Variables citées par ces textes, sans doublon, dans l'ordre d'apparition."""
    vues: list[str] = []
    for texte in textes:
        for nom in MOTIF_VARIABLE.findall(texte):
            if nom not in vues:
                vues.append(nom)
    return vues


def substituer(texte: str, valeurs: dict[str, str]) -> str:
    """Remplace les variables connues, laisse les autres en place."""

    def remplacer(trouve: re.Match[str]) -> str:
        nom = trouve.group(1)
        if nom not in valeurs:
            return trouve.group(0)
        return html.escape(str(valeurs[nom]), quote=True)

    return MOTIF_VARIABLE.sub(remplacer, texte)


def rendre_html(corps: str, objet: str, preheader: str | None, valeurs: dict[str, str]) -> str:
    """Compose le message complet : coquille + corps, variables substituées.

    L'objet et le pré-entête entrent aussi dans la coquille — le pré-entête est
    ce que la boîte de réception affiche après l'objet, et il se rédige donc
    avec lui.
    """
    toutes: dict[str, str] = {**VALEURS_COQUILLE, **valeurs}
    corps_rendu = substituer(corps, toutes)
    complet = coquille().replace("{{contenu}}", corps_rendu)
    return substituer(
        complet,
        {
            **toutes,
            "objet": substituer(objet, toutes),
            "preheader": substituer(preheader or objet, toutes),
        },
    )


def rendre_texte(html_rendu: str) -> str:
    """Version texte du message, pour les clients qui refusent le HTML.

    Ce n'est pas un convertisseur HTML complet et ça n'a pas à l'être : le but
    est qu'un message reste LISIBLE, pas qu'il reste beau. Les liens sont
    conservés en clair, puisque c'est tout ce que ce courriel demande de faire.
    """
    texte = MOTIF_BLOCS_MUETS.sub(" ", html_rendu)
    texte = MOTIF_COMMENTAIRE.sub(" ", texte)
    # Un lien devient « libellé (adresse) » : sans cela, le bouton principal
    # disparaîtrait purement et simplement de la version texte.
    texte = re.sub(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        lambda t: f"{MOTIF_BALISE.sub('', t.group(2)).strip()} ({t.group(1)})",
        texte,
        flags=re.S | re.I,
    )
    texte = re.sub(r"</(tr|div|p|table)>", "\n", texte, flags=re.I)
    texte = MOTIF_BALISE.sub("", texte)
    texte = html.unescape(texte)
    texte = MOTIF_REMBOURRAGE.sub(" ", texte)
    lignes = [ligne.strip() for ligne in texte.splitlines()]
    texte = "\n".join(ligne for ligne in lignes if ligne)
    return MOTIF_LIGNES_VIDES.sub("\n\n", texte).strip()
