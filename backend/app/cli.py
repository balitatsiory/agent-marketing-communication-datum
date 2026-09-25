"""Commandes d'administration en ligne de commande.

    python -m app.cli create-admin --email marie@datum.mg --first-name Marie --last-name R
    python -m app.cli db-doc > IAdocs/base-de-donnees.md
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import text

from app.core.database import SessionFactory
from app.modules.users import service as users_service
from app.modules.users.constants import PermissionCode
from app.modules.users.schemas import UserCreate

# Regroupement des tables dans le document, par domaine.
GROUPES: list[tuple[str, list[str]]] = [
    ("Utilisateurs et accès", ["users", "permissions", "user_permissions", "refresh_tokens"]),
    (
        "Réseaux sociaux",
        ["platforms", "social_account_statuses", "social_accounts", "social_account_metrics"],
    ),
]

TYPES_COURTS = {
    "character varying": "varchar",
    "timestamp with time zone": "timestamptz",
    "double precision": "float8",
}

REQUETE_COLONNES = text("""
    SELECT c.relname AS table_name,
           a.attname AS column_name,
           format_type(a.atttypid, a.atttypmod) AS data_type,
           a.attnotnull AS not_null,
           coalesce(col_description(c.oid, a.attnum), '') AS column_comment,
           coalesce(obj_description(c.oid), '') AS table_comment
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
    ORDER BY c.relname, a.attnum
""")

REQUETE_CONTRAINTES = text("""
    SELECT conrelid::regclass::text AS table_name,
           conname AS name,
           pg_get_constraintdef(oid) AS definition
    FROM pg_constraint
    WHERE connamespace = 'public'::regnamespace AND conname <> 'alembic_version_pkc'
    ORDER BY 1, 2
""")


def _type_court(valeur: str) -> str:
    for long, court in TYPES_COURTS.items():
        valeur = valeur.replace(long, court)
    return valeur


async def _db_doc() -> str:
    """Produit le dictionnaire de données à partir des commentaires de la base."""
    async with SessionFactory() as session:
        colonnes = (await session.execute(REQUETE_COLONNES)).all()
        contraintes = (await session.execute(REQUETE_CONTRAINTES)).all()

    par_table: dict[str, list[tuple[str, str, bool, str]]] = {}
    commentaire_table: dict[str, str] = {}
    for ligne in colonnes:
        par_table.setdefault(ligne.table_name, []).append(
            (ligne.column_name, ligne.data_type, ligne.not_null, ligne.column_comment)
        )
        commentaire_table[ligne.table_name] = ligne.table_comment

    par_table_contraintes: dict[str, list[tuple[str, str]]] = {}
    for ligne in contraintes:
        par_table_contraintes.setdefault(ligne.table_name, []).append(
            (ligne.name, ligne.definition)
        )

    total_colonnes = sum(len(valeurs) for valeurs in par_table.values())
    lignes = [
        "# Dictionnaire de données — IAGORA",
        "",
        "> **Généré depuis la base**, à partir des commentaires PostgreSQL",
        "> (`COMMENT ON TABLE` / `COMMENT ON COLUMN`), eux-mêmes déclarés dans les modèles.",
        "> Les mêmes textes s'affichent dans DataGrip, pgAdmin et psql.",
        ">",
        "> Régénérer après une migration, depuis `backend/` :",
        "> `.\\venv\\Scripts\\python.exe -m app.cli db-doc > ..\\IAdocs\\base-de-donnees.md`",
        "",
        f"Tables documentées : **{len(par_table)}** · colonnes : **{total_colonnes}**.",
        "",
    ]

    connues = {table for _, tables in GROUPES for table in tables}
    groupes = [*GROUPES, ("Autres tables", sorted(set(par_table) - connues))]

    for titre, tables in groupes:
        tables_presentes = [table for table in tables if table in par_table]
        if not tables_presentes:
            continue
        lignes += [f"## {titre}", ""]
        for table in tables_presentes:
            lignes += [f"### `{table}`", "", commentaire_table[table], ""]
            lignes += ["| Colonne | Type | Nul | Description |", "|---|---|---|---|"]
            for nom, type_sql, not_null, commentaire in par_table[table]:
                nul = "non" if not_null else "oui"
                lignes.append(f"| `{nom}` | {_type_court(type_sql)} | {nul} | {commentaire} |")
            lignes.append("")
            if table in par_table_contraintes:
                lignes += ["**Contraintes**", ""]
                lignes += [
                    f"- `{nom}` — {definition}"
                    for nom, definition in par_table_contraintes[table]
                ]
                lignes.append("")

    return "\n".join(lignes)


async def _create_admin(email: str, first_name: str, last_name: str, password: str) -> None:
    async with SessionFactory() as session:
        payload = UserCreate(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            permissions=list(PermissionCode),
        )
        user = await users_service.create_user(session, payload)
        await session.commit()
        print(f"Administrateur créé : {user.email} (id {user.id_users})")


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="app.cli", description="Administration d'IAGORA")
    commandes = parseur.add_subparsers(dest="commande", required=True)

    creer = commandes.add_parser("create-admin", help="Crée un compte avec tous les droits")
    creer.add_argument("--email", required=True)
    creer.add_argument("--first-name", required=True)
    creer.add_argument("--last-name", required=True)

    commandes.add_parser(
        "db-doc", help="Écrit le dictionnaire de données sur la sortie standard"
    )

    arguments = parseur.parse_args(argv)

    if arguments.commande == "create-admin":
        # Le mot de passe est demandé à la saisie : il ne reste pas dans l'historique
        # du terminal, et n'apparaît pas dans la liste des processus.
        password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
        if password != getpass.getpass("Confirmation : "):
            print("Les deux saisies diffèrent.", file=sys.stderr)
            return 1
        asyncio.run(
            _create_admin(arguments.email, arguments.first_name, arguments.last_name, password)
        )
    elif arguments.commande == "db-doc":
        print(asyncio.run(_db_doc()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
