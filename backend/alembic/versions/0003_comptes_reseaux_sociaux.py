"""Module 05 Comptes reseaux sociaux.

Dix tables. social_platforms, onziieme du module, a ete creee par la
migration 0002 : media_variants en dependait.

Colonnes reprises du modele de donnees. Les causes de panne y sont annoncees
au nombre de sept sans etre enumerees, et l'etat des conceptions les porte
encore comme « reste a valider » : les sept codes semes ici sont donc une
PROPOSITION, signalee comme telle. Une valeur de referentiel se corrige par
migration, ce qui est le moindre cout parmi les facons de se tromper.

Deux vocabulaires sont laisses libres faute d'etre arretes : token_kind et
sync_kind. Une contrainte CHECK posee sur des valeurs devinees interdirait
precisement ce que le module 07 decouvrira en branchant les connecteurs.

Revision : 0003
Revision precedente : 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Un compte emprunte-t-il ses cles a un autre ? Contrainte CHECK et non table
# de reference : deux valeurs techniques, jamais affichees ni triees.
MODES_DE_CREDENTIAL = ("own", "inherited")

# Issues d'un passage. Documentees le 23 octobre : « on y est alle, il n'y
# avait rien » n'est pas « on n'y est pas alle ».
ISSUES_DE_PASSAGE = ("succeeded", "empty", "failed")

# Un stock ne s'additionne pas d'un jour a l'autre, un flux si.
NATURES_DE_MESURE = ("stock", "flux")

TABLES_HORODATEES = (
    "social_account_statuses",
    "social_account_error_causes",
    "social_accounts",
    "social_account_statistic_types",
    "social_platform_statistic_types",
)

COMMENTAIRES: dict[str, dict[str, str]] = {
    "social_account_error_causes": {
        "recommended_action": (
            "Phrase ecrite pour le charge de communication, pas pour un developpeur."
        ),
        "writes_on_account": "La panne remonte-t-elle jusqu'a la fiche du compte ?",
        "id_social_account_statuses_target": (
            "Etat dans lequel cette panne place le compte. Nul pour une panne "
            "qui ne change pas l'etat. Sort la regle « quand telle panne "
            "survient, fais ceci » du code des connecteurs."
        ),
    },
    "social_accounts": {
        "id_social_accounts_parent": (
            "Compte dont celui-ci emprunte les cles : un compte Instagram "
            "rattache a sa page Facebook n'a aucune delivrance a son nom."
        ),
        "credential_mode": "own (cles a son nom) | inherited (cles du compte parent).",
        "account_external_id": "Identifiant du compte CHEZ le reseau, jamais celui d'IAGORA.",
        "current_error_message": "Message brut du reseau, conserve pour le diagnostic.",
    },
    "social_account_tokens": {
        "access_token_encrypted": (
            "Chiffre par Fernet. Le jeton en clair ne touche jamais le disque."
        ),
        "granted_api_permissions_json": "Permissions reellement accordees par la plateforme.",
        "token_kind": (
            "Sorte de jeton chez la plateforme. Vocabulaire libre tant que le "
            "module 07 n'a pas branche les connecteurs."
        ),
        "superseded_at": "Remplacement par une delivrance plus recente.",
        "id_users_created_by": (
            "Rempli quand une personne a fait le parcours d'autorisation, vide "
            "quand la tache de fond a renouvele seule."
        ),
    },
    "social_account_statistics": {
        "metric_date": "Jour MESURE.",
        "collected_at": (
            "Instant de la LECTURE. Les deux different : les reseaux publient "
            "leurs chiffres avec retard et les corrigent apres coup."
        ),
        "raw_response_json": "Reponse brute du reseau, conservee telle quelle.",
    },
    "social_account_statistic_values": {
        "value": "L'absence de ligne vaut « non mesure par le reseau », jamais zero.",
    },
    "social_account_statistic_types": {
        "nature": "stock (ne s'additionne pas) | flux.",
        "is_summable": "La mesure se cumule-t-elle d'un jour a l'autre ?",
    },
    "social_platform_statistic_types": {
        "platform_metric_name": "Nom de la mesure CHEZ le reseau.",
    },
    "social_account_syncs": {
        "sync_kind": "Sorte de passage. Vocabulaire libre jusqu'au module 07.",
        "covered_until_date": "Jusqu'ou le releve est alle.",
        "retry_after": "Instant avant lequel il est inutile de reessayer.",
    },
    "social_posts": {
        "post_external_id": "Identifiant du post CHEZ le reseau.",
        "archived_on_platform_at": "Retire de la plateforme par une personne.",
        "deleted_on_platform_at": "Constate absent lors d'un passage.",
    },
}


def upgrade() -> None:
    op.create_table(
        "social_account_statuses",
        sa.Column(
            "id_social_account_statuses", sa.Integer, sa.Identity(always=False), nullable=False
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_social_account_statuses", name="pk_social_account_statuses"),
        sa.UniqueConstraint("code", name="uq_social_account_statuses_code"),
        comment="Etats d'un compte raccorde : connecte, a reconnecter, deconnecte.",
    )

    op.create_table(
        "social_account_error_causes",
        sa.Column(
            "id_social_account_error_causes",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("recommended_action", sa.String(255), nullable=False),
        sa.Column("writes_on_account", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("id_social_account_statuses_target", sa.Integer, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint(
            "id_social_account_error_causes", name="pk_social_account_error_causes"
        ),
        sa.UniqueConstraint("code", name="uq_social_account_error_causes_code"),
        sa.ForeignKeyConstraint(
            ["id_social_account_statuses_target"],
            ["social_account_statuses.id_social_account_statuses"],
            name="fk_social_account_error_causes_statuses_target",
        ),
        # « writes_on_account » et l'etat vise ne se deduisent pas l'un de
        # l'autre : une panne peut remonter sur la fiche sans changer l'etat.
        # Mais placer un compte dans un etat sans que cela se voie sur sa
        # fiche serait incoherent.
        sa.CheckConstraint(
            "id_social_account_statuses_target IS NULL OR writes_on_account",
            name="etat_vise_implique_ecriture",
        ),
        comment=(
            "Causes de panne d'un compte, dans le vocabulaire d'IAGORA et non "
            "dans celui des reseaux. La liste est ouverte : chaque cause "
            "designe l'etat ou elle place le compte, ce qui sort la regle "
            "« quand telle panne survient, fais ceci » du code des connecteurs."
        ),
    )

    op.create_table(
        "social_accounts",
        sa.Column("id_social_accounts", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_social_platforms", sa.Integer, nullable=False),
        sa.Column("id_social_account_statuses_current", sa.Integer, nullable=False),
        sa.Column("id_social_accounts_parent", sa.Integer, nullable=True),
        sa.Column("id_social_account_error_causes_current", sa.Integer, nullable=True),
        sa.Column("account_external_id", sa.String(120), nullable=False),
        sa.Column("account_display_name", sa.String(255), nullable=False),
        sa.Column("account_username", sa.String(120), nullable=True),
        sa.Column("credential_mode", sa.String(20), nullable=False),
        sa.Column("current_error_message", sa.Text, nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_changed_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_social_accounts", name="pk_social_accounts"),
        sa.ForeignKeyConstraint(
            ["id_social_platforms"],
            ["social_platforms.id_social_platforms"],
            name="fk_social_accounts_id_social_platforms",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_statuses_current"],
            ["social_account_statuses.id_social_account_statuses"],
            name="fk_social_accounts_statuses_current",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_accounts_parent"],
            ["social_accounts.id_social_accounts"],
            name="fk_social_accounts_parent",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_error_causes_current"],
            ["social_account_error_causes.id_social_account_error_causes"],
            name="fk_social_accounts_error_causes_current",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_social_accounts_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_social_accounts_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "credential_mode IN ('" + "', '".join(MODES_DE_CREDENTIAL) + "')",
            name="credential_mode",
        ),
        # Un compte qui emprunte ses cles doit dire a qui : sans parent, il
        # n'aurait aucun moyen d'appeler l'API, et la panne ne se verrait
        # qu'au premier envoi.
        sa.CheckConstraint(
            "credential_mode <> 'inherited' OR id_social_accounts_parent IS NOT NULL",
            name="heritage_exige_un_parent",
        ),
        sa.CheckConstraint(
            "id_social_accounts_parent IS NULL OR id_social_accounts_parent <> id_social_accounts",
            name="parent_different_de_soi",
        ),
        comment=(
            "Comptes officiels de DATUM Academy raccordes a IAGORA. Les cles "
            "n'y sont plus : elles vivent dans social_account_tokens, une "
            "ligne par delivrance."
        ),
    )
    # Un meme compte ne se raccorde qu'une fois par reseau. L'unicite est
    # PARTIELLE : un compte debranche puis rebranche doit pouvoir revenir.
    op.create_index(
        "uq_social_accounts_plateforme_externe",
        "social_accounts",
        ["id_social_platforms", "account_external_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "social_account_tokens",
        sa.Column(
            "id_social_account_tokens", sa.Integer, sa.Identity(always=False), nullable=False
        ),
        sa.Column("id_social_accounts", sa.Integer, nullable=False),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_api_permissions_json", postgresql.JSONB, nullable=True),
        sa.Column("token_kind", sa.String(40), nullable=True),
        sa.Column(
            "obtained_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_social_account_tokens", name="pk_social_account_tokens"),
        sa.ForeignKeyConstraint(
            ["id_social_accounts"],
            ["social_accounts.id_social_accounts"],
            name="fk_social_account_tokens_id_social_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_social_account_tokens_id_users_created_by_users",
        ),
        comment=(
            "Une ligne par delivrance de cles. Un renouvellement cree une "
            "nouvelle ligne et marque la precedente remplacee : l'historique "
            "des autorisations fait partie de la tracabilite. Pas d'updated_at, "
            "la ligne est ecrite une fois."
        ),
    )
    # Une seule delivrance active par compte. L'unicite est PARTIELLE :
    # les delivrances remplacees ou revoquees restent, par dizaines.
    op.create_index(
        "uq_social_account_tokens_actif",
        "social_account_tokens",
        ["id_social_accounts"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "social_posts",
        sa.Column("id_social_posts", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_social_accounts", sa.Integer, nullable=False),
        sa.Column("post_external_id", sa.String(255), nullable=False),
        sa.Column("permalink", sa.String(1024), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_on_platform_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_archived_by", sa.Integer, nullable=True),
        sa.Column("deleted_on_platform_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_social_posts", name="pk_social_posts"),
        sa.UniqueConstraint(
            "id_social_accounts", "post_external_id", name="uq_social_posts_compte_externe"
        ),
        sa.ForeignKeyConstraint(
            ["id_social_accounts"],
            ["social_accounts.id_social_accounts"],
            name="fk_social_posts_id_social_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_archived_by"],
            ["users.id_users"],
            name="fk_social_posts_id_users_archived_by_users",
        ),
        comment=(
            "Posts parus sur les reseaux. archived_on_platform_at est un geste "
            "humain, deleted_on_platform_at un constat fait lors d'un passage : "
            "les deux ne se confondent pas."
        ),
    )

    op.create_table(
        "social_account_statistic_types",
        sa.Column(
            "id_social_account_statistic_types",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("nature", sa.String(10), nullable=False),
        sa.Column("is_summable", sa.Boolean, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint(
            "id_social_account_statistic_types", name="pk_social_account_statistic_types"
        ),
        sa.UniqueConstraint("code", name="uq_social_account_statistic_types_code"),
        sa.CheckConstraint("nature IN ('" + "', '".join(NATURES_DE_MESURE) + "')", name="nature"),
        # Un stock ne se cumule jamais : un nombre d'abonnes additionne sur
        # sept jours ne veut rien dire.
        sa.CheckConstraint("nature <> 'stock' OR NOT is_summable", name="stock_non_cumulable"),
        comment=(
            "Vocabulaire ferme des mesures. Mesurer une statistique de plus "
            "ajoute une ligne de referentiel, non une colonne."
        ),
    )

    op.create_table(
        "social_platform_statistic_types",
        sa.Column(
            "id_social_platform_statistic_types",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("id_social_platforms", sa.Integer, nullable=False),
        sa.Column("id_social_account_statistic_types", sa.Integer, nullable=False),
        sa.Column("platform_metric_name", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint(
            "id_social_platform_statistic_types", name="pk_social_platform_statistic_types"
        ),
        sa.UniqueConstraint(
            "id_social_platforms",
            "id_social_account_statistic_types",
            name="uq_social_platform_statistic_types_couple",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_platforms"],
            ["social_platforms.id_social_platforms"],
            name="fk_social_platform_statistic_types_plateforme",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_statistic_types"],
            ["social_account_statistic_types.id_social_account_statistic_types"],
            name="fk_social_platform_statistic_types_mesure",
        ),
        comment=(
            "Quel reseau fournit quelle mesure, et sous quel nom chez lui. "
            "Permet a l'ecran de distinguer « zero », « pas encore releve » et "
            "« ce reseau ne le fournit pas », et au collecteur de savoir quels "
            "appels faire sans liste codee en dur."
        ),
    )

    op.create_table(
        "social_account_statistics",
        sa.Column(
            "id_social_account_statistics", sa.Integer, sa.Identity(always=False), nullable=False
        ),
        sa.Column("id_social_accounts", sa.Integer, nullable=False),
        sa.Column("metric_date", sa.Date, nullable=False),
        sa.Column(
            "collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("raw_response_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint(
            "id_social_account_statistics", name="pk_social_account_statistics"
        ),
        sa.ForeignKeyConstraint(
            ["id_social_accounts"],
            ["social_accounts.id_social_accounts"],
            name="fk_social_account_statistics_id_social_accounts",
        ),
        comment=(
            "Un releve par compte, par jour mesure et par lecture. Actualiser "
            "en cours de journee n'ecrase rien : la valeur d'un jour est le "
            "releve le plus recent de ce jour. PAS d'unicite sur (compte, jour) "
            "pour cette raison."
        ),
    )
    # La lecture chaude : le dernier releve d'un compte pour un jour donne.
    op.create_index(
        "ix_social_account_statistics_dernier",
        "social_account_statistics",
        ["id_social_accounts", "metric_date", sa.text("collected_at DESC")],
    )

    op.create_table(
        "social_account_statistic_values",
        sa.Column(
            "id_social_account_statistic_values",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("id_social_account_statistics", sa.Integer, nullable=False),
        sa.Column("id_social_account_statistic_types", sa.Integer, nullable=False),
        sa.Column("value", sa.BigInteger, nullable=False),
        sa.PrimaryKeyConstraint(
            "id_social_account_statistic_values", name="pk_social_account_statistic_values"
        ),
        sa.UniqueConstraint(
            "id_social_account_statistics",
            "id_social_account_statistic_types",
            name="uq_social_account_statistic_values_couple",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_statistics"],
            ["social_account_statistics.id_social_account_statistics"],
            name="fk_social_account_statistic_values_releve",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_statistic_types"],
            ["social_account_statistic_types.id_social_account_statistic_types"],
            name="fk_social_account_statistic_values_type",
        ),
        comment=(
            "Une ligne par mesure relevee. L'ABSENCE de ligne veut dire « non "
            "mesure par le reseau », jamais zero : c'est pourquoi la valeur "
            "n'est pas nullable et qu'aucune ligne n'est creee a vide."
        ),
    )

    op.create_table(
        "social_account_syncs",
        sa.Column("id_social_account_syncs", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_social_accounts", sa.Integer, nullable=False),
        sa.Column("sync_kind", sa.String(40), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_outcome", sa.String(20), nullable=True),
        sa.Column("covered_until_date", sa.Date, nullable=True),
        sa.Column("id_social_account_error_causes", sa.Integer, nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_triggered_by", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("id_social_account_syncs", name="pk_social_account_syncs"),
        sa.ForeignKeyConstraint(
            ["id_social_accounts"],
            ["social_accounts.id_social_accounts"],
            name="fk_social_account_syncs_id_social_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_account_error_causes"],
            ["social_account_error_causes.id_social_account_error_causes"],
            name="fk_social_account_syncs_error_causes",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_triggered_by"],
            ["users.id_users"],
            name="fk_social_account_syncs_id_users_triggered_by_users",
        ),
        sa.CheckConstraint(
            "sync_outcome IS NULL OR sync_outcome IN ('" + "', '".join(ISSUES_DE_PASSAGE) + "')",
            name="sync_outcome",
        ),
        # Un passage termine a une issue, un passage en cours n'en a pas.
        sa.CheckConstraint(
            "(finished_at IS NULL) = (sync_outcome IS NULL)", name="issue_et_fin_ensemble"
        ),
        comment=(
            "Carnet des passages : quand IAGORA est alle chercher quelque "
            "chose, pour quel compte, et jusqu'ou il avait releve. La ligne "
            "nait au DEBUT du passage, pour qu'un processus tue laisse une "
            "trace. Trois issues, parce que « on y est alle, il n'y avait "
            "rien » n'est pas « on n'y est pas alle »."
        ),
    )
    # Un seul passage en cours par compte et par sorte : sans quoi deux
    # collecteurs lances ensemble doubleraient les relevés.
    op.create_index(
        "uq_social_account_syncs_en_cours",
        "social_account_syncs",
        ["id_social_accounts", "sync_kind"],
        unique=True,
        postgresql_where=sa.text("finished_at IS NULL"),
    )

    for table, colonnes in COMMENTAIRES.items():
        for colonne, texte in colonnes.items():
            echappe = texte.replace("'", "''")
            op.execute(f"COMMENT ON COLUMN {table}.{colonne} IS '{echappe}'")

    for table in TABLES_HORODATEES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    # --- amorces -----------------------------------------------------------

    op.bulk_insert(
        sa.table(
            "social_account_statuses",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"code": "connected", "label": "Connecte", "sort_order": 10},
            {"code": "needs_reconnect", "label": "A reconnecter", "sort_order": 20},
            {"code": "disconnected", "label": "Deconnecte", "sort_order": 30},
        ],
    )

    # PROPOSITION. Le modele annonce sept causes sans les enumerer, et l'etat
    # des conceptions les porte encore comme « reste a valider ». Les codes et
    # les actions recommandees ci-dessous sont donc a relire avec Balita ; une
    # valeur de referentiel se corrige par migration.
    #
    # unknown s'inscrit SANS changer l'etat : c'est la seule regle que le
    # document enonce explicitement, et elle est respectee ici.
    op.execute(
        """
        INSERT INTO social_account_error_causes
            (code, label, recommended_action, writes_on_account,
             id_social_account_statuses_target, sort_order)
        SELECT v.code, v.label, v.action, v.ecrit,
               (SELECT id_social_account_statuses FROM social_account_statuses s
                WHERE s.code = v.etat_vise),
               v.ordre
        FROM (VALUES
            ('token_expired', 'Autorisation expiree',
             'Relancer le raccordement : l''autorisation donnee au reseau a expire.',
             true, 'needs_reconnect', 10),
            ('token_revoked', 'Autorisation retiree',
             'Le reseau a retire l''autorisation. Raccorder le compte a nouveau.',
             true, 'disconnected', 20),
            ('permission_missing', 'Permission manquante',
             'Le compte n''a pas accorde toutes les permissions demandees. '
             'Refaire le parcours en les acceptant toutes.',
             true, 'needs_reconnect', 30),
            ('account_restricted', 'Compte restreint par le reseau',
             'Le reseau a restreint ou suspendu le compte. '
             'Verifier son etat sur la plateforme.',
             true, 'disconnected', 40),
            ('rate_limited', 'Quota d''appels atteint',
             'Rien a faire : IAGORA reessaiera de lui-meme quand le quota sera rendu.',
             false, NULL, 50),
            ('platform_unavailable', 'Reseau indisponible',
             'Panne du cote du reseau. Rien a faire : IAGORA reessaiera.',
             false, NULL, 60),
            ('unknown', 'Cause non identifiee',
             'IAGORA n''a pas su classer cette erreur. '
             'Signaler le cas pour qu''elle soit ajoutee au referentiel.',
             false, NULL, 70)
        ) AS v(code, label, action, ecrit, etat_vise, ordre)
        """
    )

    # posts_count est retiree et profile_views n'est pas semee : Meta ne
    # l'expose plus. Decision portee au modele de donnees.
    op.bulk_insert(
        sa.table(
            "social_account_statistic_types",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.String),
            sa.column("nature", sa.String),
            sa.column("is_summable", sa.Boolean),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "code": "followers",
                "label": "Abonnes",
                "description": "Nombre d'abonnes au jour mesure.",
                "nature": "stock",
                "is_summable": False,
                "sort_order": 10,
            },
            {
                "code": "reach",
                "label": "Portee",
                "description": (
                    "Comptes distincts ayant vu un contenu. Ne s'additionne pas "
                    "d'un jour a l'autre."
                ),
                "nature": "flux",
                "is_summable": False,
                "sort_order": 20,
            },
            {
                "code": "views",
                "label": "Vues",
                "description": "Nombre d'affichages. S'additionne.",
                "nature": "flux",
                "is_summable": True,
                "sort_order": 30,
            },
            {
                "code": "interactions",
                "label": "Interactions",
                "description": "Mentions j'aime, commentaires et partages. S'additionne.",
                "nature": "flux",
                "is_summable": True,
                "sort_order": 40,
            },
        ],
    )

    # Droits du module. sort_order : numero du module x 100.
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "code": "manage_social_accounts",
                "label": "Gerer les comptes de reseaux",
                "description": (
                    "Raccorder un compte de reseau social, le reconnecter et le "
                    "debrancher. Donne acces aux cles du compte."
                ),
                "sort_order": 500,
            },
            {
                "code": "read_social_statistics",
                "label": "Consulter les statistiques de compte",
                "description": (
                    "Lire les relevés d'abonnes, de portee, de vues et "
                    "d'interactions des comptes raccordes."
                ),
                "sort_order": 510,
            },
        ],
    )


def downgrade() -> None:
    for table in TABLES_HORODATEES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute(
        "DELETE FROM permissions WHERE code IN ('manage_social_accounts', 'read_social_statistics')"
    )
    op.drop_table("social_account_syncs")
    op.drop_table("social_account_statistic_values")
    op.drop_table("social_account_statistics")
    op.drop_table("social_platform_statistic_types")
    op.drop_table("social_account_statistic_types")
    op.drop_table("social_posts")
    op.drop_table("social_account_tokens")
    op.drop_table("social_accounts")
    op.drop_table("social_account_error_causes")
    op.drop_table("social_account_statuses")
