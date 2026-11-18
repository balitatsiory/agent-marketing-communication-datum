"""Données fictives de développement.

Ce script n'est PAS une migration, et c'est volontaire : une migration part en
production, et cinq faux comptes arriveraient sur la base de DATUM Academy. Il
refuse donc de s'exécuter si ENVIRONMENT n'est pas « local ».

Les adresses utilisent le domaine `.test`, réservé par la norme et qui ne peut
exister sur Internet. Aucun courriel d'essai ne peut donc atteindre une vraie
personne — ce qui comptera dès que le module Newsletters enverra des lots.

    python -m scripts.seed_dev
"""

import asyncio
import sys

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.security import hash_password

# Les mots de passe sont en clair ici : ce sont des comptes de développement,
# sur une base locale, et les connaître est le but du script.
COMPTES = [
    {
        "email": "admin@iagora.test",
        "mot_de_passe": "Dev-Admin-2026",
        "first_name": "Ana",
        "last_name": "Administratrice",
        "droits": ["manage_users", "manage_permissions"],
        "is_active": True,
        "archive": False,
        "sert_a": "le parcours administrateur",
    },
    {
        "email": "simple@iagora.test",
        "mot_de_passe": "Dev-Simple-2026",
        "first_name": "Simon",
        "last_name": "Sansdroit",
        "droits": [],
        "is_active": True,
        "archive": False,
        "sert_a": "le refus 403 : authentifié mais sans droit",
    },
    {
        "email": "desactive@iagora.test",
        "mot_de_passe": "Dev-Desac-2026",
        "first_name": "Denise",
        "last_name": "Suspendue",
        "droits": [],
        "is_active": False,
        "archive": False,
        "sert_a": "le refus de connexion d'un compte suspendu",
    },
    {
        "email": "archive@iagora.test",
        "mot_de_passe": "Dev-Archi-2026",
        "first_name": "Arnaud",
        "last_name": "Archive",
        "droits": [],
        "is_active": True,
        "archive": True,
        "sert_a": "l'exclusion des listes, la paternité restant acquise",
    },
]


async def semer() -> int:
    reglages = get_settings()
    if reglages.ENVIRONMENT != "local":
        print(
            f"Refus : ENVIRONMENT vaut « {reglages.ENVIRONMENT} ». "
            "Ce script ne s'exécute qu'en local.",
            file=sys.stderr,
        )
        return 1

    crees, deja_la = 0, 0
    async with SessionFactory() as session:
        for compte in COMPTES:
            existe = await session.execute(
                text("SELECT id_users FROM users WHERE lower(email) = lower(:e)"),
                {"e": compte["email"]},
            )
            if existe.first() is not None:
                deja_la += 1
                continue

            resultat = await session.execute(
                text(
                    """
                    INSERT INTO users
                        (email, password_hash, first_name, last_name, is_active, deleted_at)
                    VALUES
                        (:email, :empreinte, :prenom, :nom, :actif,
                         CASE WHEN :archive THEN now() ELSE NULL END)
                    RETURNING id_users
                    """
                ),
                {
                    "email": compte["email"],
                    "empreinte": hash_password(str(compte["mot_de_passe"])),
                    "prenom": compte["first_name"],
                    "nom": compte["last_name"],
                    "actif": compte["is_active"],
                    "archive": compte["archive"],
                },
            )
            id_users = int(resultat.scalar_one())
            crees += 1

            for code in compte["droits"]:  # type: ignore[union-attr]
                await session.execute(
                    text(
                        """
                        INSERT INTO user_permissions (id_users, id_permissions)
                        SELECT :i, id_permissions FROM permissions WHERE code = :c
                        """
                    ),
                    {"i": id_users, "c": code},
                )
        await session.commit()

    print(f"{crees} compte(s) créé(s), {deja_la} déjà présent(s).\n")
    print(f"{'Adresse':<26} {'Mot de passe':<18} {'État':<22} Sert à")
    print("-" * 100)
    for compte in COMPTES:
        if compte["archive"]:
            etat = "archivé"
        elif not compte["is_active"]:
            etat = "suspendu"
        elif compte["droits"]:
            etat = ", ".join(compte["droits"])  # type: ignore[arg-type]
        else:
            etat = "aucun droit"
        print(
            f"{compte['email']:<26} {compte['mot_de_passe']:<18} {etat[:21]:<22} {compte['sert_a']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(semer()))
