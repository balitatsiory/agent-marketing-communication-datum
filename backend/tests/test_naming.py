"""Garde-fou sur les noms en base.

PostgreSQL tronque tout identifiant à **63 octets**, sans prévenir. Une contrainte au
nom trop long est donc créée sous un autre nom que celui déclaré, et la migration qui
la supprimerait échouerait. Ce test attrape le problème à l'écriture du modèle.
"""

from app.core.database import Base

# Import des modèles : sans cela, leurs tables ne sont pas dans Base.metadata.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.social_accounts import models as social_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

LIMITE_POSTGRESQL = 63

MOTS_RESERVES = {"user", "order", "group", "table", "select", "check", "session", "all"}


def test_aucun_nom_ne_depasse_la_limite_postgresql() -> None:
    trop_longs = []
    for nom_table, table in Base.metadata.tables.items():
        if len(nom_table) > LIMITE_POSTGRESQL:
            trop_longs.append(f"table {nom_table} ({len(nom_table)})")
        for contrainte in table.constraints | set(table.indexes):
            nom = contrainte.name
            if nom and len(str(nom)) > LIMITE_POSTGRESQL:
                trop_longs.append(f"{nom} ({len(str(nom))})")

    assert not trop_longs, "Noms trop longs pour PostgreSQL : " + ", ".join(trop_longs)


def test_les_tables_ne_portent_pas_de_mot_reserve() -> None:
    fautives = [nom for nom in Base.metadata.tables if nom.lower() in MOTS_RESERVES]

    assert not fautives, f"Tables nommées avec un mot réservé : {fautives}"


def test_les_tables_sont_au_pluriel_et_en_minuscules() -> None:
    fautives = [
        nom
        for nom in Base.metadata.tables
        if nom != nom.lower() or not nom.endswith(("s", "media"))
    ]

    assert not fautives, f"Tables hors convention (pluriel, minuscules) : {fautives}"


def test_chaque_table_a_sa_cle_primaire_id_table() -> None:
    fautives = []
    for nom_table, table in Base.metadata.tables.items():
        colonnes = [colonne.name for colonne in table.primary_key.columns]
        if colonnes != [f"id_{nom_table}"]:
            fautives.append(f"{nom_table} → {colonnes}")

    assert not fautives, f"Clés primaires hors convention id_<table> : {fautives}"
