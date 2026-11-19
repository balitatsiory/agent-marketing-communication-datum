"""Module 03 Media, et la table de reference des plateformes.

Cinq tables : social_platforms, media, media_variants,
media_reference_natures, media_references.

social_platforms appartient au perimetre du module 05, mais elle est creee
ici : media_variants porte une cle etrangere vers elle, et une variante n'a
pas de sens sans la plateforme qu'elle vise. C'est d'ailleurs une table
partagee par les modules 03, 06, 07 et 08, non une table propre au 05.
Elle est semee sans ses valeurs d'API : une version d'API se verifie dans la
documentation de chaque reseau, elle ne s'invente pas dans une migration.

Colonnes reprises du modele de donnees : media et media_variants, puis
media_references et media_reference_natures validees le 30 octobre 2026,
social_platforms validee le 21 octobre 2026.

Revision : 0002
Revision precedente : 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Origine d'un media. Contrainte CHECK et non table de reference : deux
# valeurs techniques, jamais triees, dont aucun comportement ne depend.
ORIGINES_DE_MEDIA = ("upload", "generated")

TABLES_HORODATEES = (
    "social_platforms",
    "media",
    "media_variants",
    "media_reference_natures",
    "media_references",
)

COMMENTAIRES: dict[str, dict[str, str]] = {
    "social_platforms": {
        "code": "Identifiant stable du reseau, en anglais et minuscules : facebook, linkedin.",
        "is_enabled": (
            "Un reseau se desactive, il ne se supprime pas : les publications "
            "passees le referencent."
        ),
        "api_base_url": (
            "Adresse de base de l'API. Seul endroit a modifier pour changer de version."
        ),
        "api_settings_json": "Reglages propres au reseau qui ne meritent pas une colonne chacun.",
        "max_description_length": (
            "Longueur maximale du texte publie, description et hashtags assembles."
        ),
        "message_response_window_hours": (
            "Duree pendant laquelle une reponse automatisee reste permise. "
            "Nulle si le reseau ne l'autorise pas."
        ),
    },
    "media": {
        "storage_key": (
            "Cle de l'objet dans le stockage. La base ne garde JAMAIS l'URL : "
            "une URL expire ou change de domaine, la cle non."
        ),
        "file_type": "Type MIME detecte a la lecture du fichier, et non deduit de son extension.",
        "source": "upload (depose par un utilisateur) | generated (produit par la generation).",
        "display_name": "Nom montre dans la bibliotheque. Sans rapport avec la cle de stockage.",
        "width": "Nul pour un fichier sans dimensions, un document par exemple.",
        "video_duration_seconds": "Renseigne pour une video seulement.",
        "deleted_at": (
            "Archivage. Un media utilise par une publication deja diffusee ne "
            "peut pas disparaitre sans emporter l'historique avec lui."
        ),
    },
    "media_variants": {
        "storage_key": "Cle de la copie adaptee. L'original reste dans media, qui fait foi.",
        "file_type": "Images uniquement : une video n'est pas reencodee par IAGORA.",
    },
    "media_reference_natures": {
        "code": "logo | personne | lieu | objet | fond.",
        "description": "Ce que le modele d'image doit faire de ce genre de reference.",
    },
    "media_references": {
        "id_media": (
            "Table satellite de media, sur le patron de media_variants : le "
            "fichier reste dans media, qui demeure la seule verite. Un media "
            "n'est reference qu'une fois."
        ),
        "label": "Nom donne a la reference par l'utilisateur qui la declare.",
        "description": (
            "Description ecrite une seule fois par un appel de vision au premier "
            "depot, puis relue a chaque publication. Sert aussi de texte de "
            "recherche dans la bibliotheque."
        ),
        "is_active": "Etat d'exploitation, reversible : reference ecartee sans etre archivee.",
    },
}


def upgrade() -> None:
    op.create_table(
        "social_platforms",
        sa.Column("id_social_platforms", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("api_base_url", sa.String(255), nullable=True),
        sa.Column("api_version", sa.String(40), nullable=True),
        sa.Column("api_settings_json", postgresql.JSONB, nullable=True),
        sa.Column("max_description_length", sa.Integer, nullable=True),
        sa.Column("supports_event_polling", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "supports_account_metrics", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "allows_automated_message_reply",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("message_response_window_hours", sa.Integer, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_social_platforms", name="pk_social_platforms"),
        sa.UniqueConstraint("code", name="uq_social_platforms_code"),
        # Validee le 21 octobre : une fenetre de reponse sur un reseau qui
        # n'autorise pas la reponse automatisee serait une duree sans objet.
        sa.CheckConstraint(
            "message_response_window_hours IS NULL OR allows_automated_message_reply",
            name="fenetre_sans_reponse_automatisee",
        ),
        sa.CheckConstraint(
            "max_description_length IS NULL OR max_description_length > 0", name="longueur_positive"
        ),
        comment=(
            "Reseaux connus et leurs regles. Seul endroit a modifier pour changer "
            "de version d'API. Zoom, Google Calendar et la messagerie d'envoi en "
            "sont exclus depuis le 20 octobre 2026 : ce ne sont pas des reseaux "
            "sociaux, ils n'ont ni comptes a raccorder ni mesures quotidiennes."
        ),
    )

    op.create_table(
        "media",
        sa.Column("id_media", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("video_duration_seconds", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_deleted_by", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("id_media", name="pk_media"),
        # Non partielle, a la difference de users.email : deux lignes ne doivent
        # jamais designer le meme objet de stockage, archivees ou non.
        sa.UniqueConstraint("storage_key", name="uq_media_storage_key"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"], ["users.id_users"], name="fk_media_id_users_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["id_users_deleted_by"], ["users.id_users"], name="fk_media_id_users_deleted_by_users"
        ),
        sa.CheckConstraint("source IN ('" + "', '".join(ORIGINES_DE_MEDIA) + "')", name="source"),
        sa.CheckConstraint("size_bytes > 0", name="poids_positif"),
        # Une largeur sans hauteur ne permet ni d'afficher ni de recadrer :
        # c'est une ligne qu'on ne saurait pas interpreter.
        sa.CheckConstraint("(width IS NULL) = (height IS NULL)", name="dimensions_completes"),
        sa.CheckConstraint(
            "video_duration_seconds IS NULL OR file_type LIKE 'video/%'",
            name="duree_reservee_aux_videos",
        ),
        comment=(
            "Fichier d'origine, depose par un utilisateur ou produit par la "
            "generation. La base ne garde que la cle de stockage, jamais l'URL."
        ),
    )

    op.create_table(
        "media_variants",
        sa.Column("id_media_variants", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_media", sa.Integer, nullable=False),
        sa.Column("id_social_platforms", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_media_variants", name="pk_media_variants"),
        sa.UniqueConstraint("storage_key", name="uq_media_variants_storage_key"),
        sa.UniqueConstraint(
            "id_media", "id_social_platforms", name="uq_media_variants_media_plateforme"
        ),
        sa.ForeignKeyConstraint(
            ["id_media"], ["media.id_media"], name="fk_media_variants_id_media_media"
        ),
        sa.ForeignKeyConstraint(
            ["id_social_platforms"],
            ["social_platforms.id_social_platforms"],
            name="fk_media_variants_id_social_platforms",
        ),
        sa.CheckConstraint("file_type LIKE 'image/%'", name="images_seulement"),
        sa.CheckConstraint("size_bytes > 0", name="poids_positif"),
        sa.CheckConstraint("width > 0 AND height > 0", name="dimensions_positives"),
        comment=(
            "Copie d'un media adaptee a une plateforme, creee seulement si "
            "l'original ne convient pas. Une seule par media et par plateforme. "
            "Pas de deleted_at : une variante est une donnee derivee, "
            "regenerable a partir de l'original, et rien ne s'y rattache."
        ),
    )

    op.create_table(
        "media_reference_natures",
        sa.Column(
            "id_media_reference_natures", sa.Integer, sa.Identity(always=False), nullable=False
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_media_reference_natures", name="pk_media_reference_natures"),
        sa.UniqueConstraint("code", name="uq_media_reference_natures_code"),
        comment=(
            "Ce qu'un media de reference represente, pour que le modele d'image "
            "sache quoi en faire. Sans cette distinction, un flyer portant un "
            "logo et un portrait recoit deux images indifferenciees, et le logo "
            "ressort deforme."
        ),
    )

    op.create_table(
        "media_references",
        sa.Column("id_media_references", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_media", sa.Integer, nullable=False),
        sa.Column("id_media_reference_natures", sa.Integer, nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_deleted_by", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("id_media_references", name="pk_media_references"),
        sa.ForeignKeyConstraint(
            ["id_media"], ["media.id_media"], name="fk_media_references_id_media_media"
        ),
        sa.ForeignKeyConstraint(
            ["id_media_reference_natures"],
            ["media_reference_natures.id_media_reference_natures"],
            name="fk_media_references_id_media_reference_natures",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_media_references_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_deleted_by"],
            ["users.id_users"],
            name="fk_media_references_id_users_deleted_by_users",
        ),
        comment=(
            "Dit qu'un fichier sert de reference a la generation d'images, et "
            "porte ce qui le qualifie comme tel. La ligne nait sur un geste "
            "explicite : l'utilisateur designe le media et choisit sa nature."
        ),
    )

    # Unicite PARTIELLE : un media n'est reference qu'une fois, mais une
    # reference archivee ne doit pas interdire de le declarer a nouveau.
    op.create_index(
        "uq_media_references_media_actif",
        "media_references",
        ["id_media"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # La bibliotheque liste les medias non archives, du plus recent au plus
    # ancien : c'est la requete chaude de ce module.
    op.create_index(
        "ix_media_created_at",
        "media",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
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

    # Reseaux semes sans leurs valeurs d'API, desactives : adresse, version et
    # longueur maximale se lisent dans la documentation de chaque reseau et
    # changent avec elle. Le module 07 les renseignera, source a l'appui.
    op.bulk_insert(
        sa.table(
            "social_platforms",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"code": "facebook", "label": "Facebook", "sort_order": 10},
            {"code": "instagram", "label": "Instagram", "sort_order": 20},
            {"code": "linkedin", "label": "LinkedIn", "sort_order": 30},
            {"code": "tiktok", "label": "TikTok", "sort_order": 40},
        ],
    )

    op.bulk_insert(
        sa.table(
            "media_reference_natures",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "code": "logo",
                "label": "Logo",
                "description": "A poser tel quel, sans le deformer ni le recolorer.",
                "sort_order": 10,
            },
            {
                "code": "personne",
                "label": "Personne",
                "description": "A integrer dans la scene, visage preserve.",
                "sort_order": 20,
            },
            {
                "code": "lieu",
                "label": "Lieu",
                "description": "Decor ou arriere-plan de l'image produite.",
                "sort_order": 30,
            },
            {
                "code": "objet",
                "label": "Objet",
                "description": "Element a faire figurer dans l'image.",
                "sort_order": 40,
            },
            {
                "code": "fond",
                "label": "Fond",
                "description": "Matiere ou texture, et non sujet de l'image.",
                "sort_order": 50,
            },
        ],
    )

    # Seuls les droits de CE module. sort_order : numero du module x 100.
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
                "code": "manage_media",
                "label": "Gerer les medias",
                "description": (
                    "Deposer un fichier dans la bibliotheque, le renommer et "
                    "l'archiver. L'archivage le retire des listes sans le detruire."
                ),
                "sort_order": 300,
            },
            {
                "code": "manage_media_reference",
                "label": "Gerer les medias de reference",
                "description": (
                    "Declarer qu'un media sert de reference a la generation "
                    "d'images, et choisir ce qu'il represente."
                ),
                "sort_order": 310,
            },
            {
                "code": "purge_media",
                "label": "Supprimer definitivement un media",
                "description": (
                    "Detruire le fichier et sa ligne, sans retour possible. "
                    "Distinct de l'archivage, et reserve a ce qui n'aurait "
                    "jamais du etre depose."
                ),
                "sort_order": 320,
            },
        ],
    )


def downgrade() -> None:
    for table in TABLES_HORODATEES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute(
        "DELETE FROM permissions WHERE code IN "
        "('manage_media', 'manage_media_reference', 'purge_media')"
    )
    op.drop_table("media_references")
    op.drop_table("media_reference_natures")
    op.drop_table("media_variants")
    op.drop_table("media")
    op.drop_table("social_platforms")
