"""Tables du module Media.

Quatre tables : media, media_variants, media_reference_natures,
media_references. La table des plateformes, dont media_variants depend, vit
dans le module platforms parce que quatre modules la lisent.

Les contraintes, index et commentaires sont declares ici A L'IDENTIQUE de la
migration 0002 : `alembic check` echoue sur le moindre ecart, et tout ce qui
manquerait ici serait propose en SUPPRESSION dans la migration suivante.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Origine d'un media. Contrainte CHECK et non table de reference : deux
# valeurs techniques, jamais triees, dont aucun comportement ne depend.
ORIGINES_DE_MEDIA = ("upload", "generated")


class Media(Base):
    """Fichier d'origine, depose ou produit par la generation."""

    __tablename__ = "media"
    __table_args__ = (
        # Non partielle, a la difference de users.email : deux lignes ne doivent
        # jamais designer le meme objet de stockage, archivees ou non.
        UniqueConstraint("storage_key", name="uq_media_storage_key"),
        CheckConstraint("source IN ('" + "', '".join(ORIGINES_DE_MEDIA) + "')", name="source"),
        CheckConstraint("size_bytes > 0", name="poids_positif"),
        CheckConstraint("(width IS NULL) = (height IS NULL)", name="dimensions_completes"),
        CheckConstraint(
            "video_duration_seconds IS NULL OR file_type LIKE 'video/%'",
            name="duree_reservee_aux_videos",
        ),
        Index(
            "ix_media_created_at",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Fichier d'origine, depose par un utilisateur ou produit par la "
                "generation. La base ne garde que la cle de stockage, jamais l'URL."
            )
        },
    )

    id_media: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_key: Mapped[str] = mapped_column(
        String(512),
        comment=(
            "Cle de l'objet dans le stockage. La base ne garde JAMAIS l'URL : "
            "une URL expire ou change de domaine, la cle non."
        ),
    )
    file_type: Mapped[str] = mapped_column(
        String(100),
        comment="Type MIME detecte a la lecture du fichier, et non deduit de son extension.",
    )
    source: Mapped[str] = mapped_column(
        String(20),
        comment="upload (depose par un utilisateur) | generated (produit par la generation).",
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        comment="Nom montre dans la bibliotheque. Sans rapport avec la cle de stockage.",
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(
        Integer, comment="Nul pour un fichier sans dimensions, un document par exemple."
    )
    height: Mapped[int | None] = mapped_column(Integer)
    video_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, comment="Renseigne pour une video seulement."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment=(
            "Archivage. Un media utilise par une publication deja diffusee ne "
            "peut pas disparaitre sans emporter l'historique avec lui."
        ),
    )
    id_users_created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
    id_users_deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))

    @property
    def est_visible(self) -> bool:
        """Un media archive sort des listes."""
        return self.deleted_at is None


class MediaVariant(Base):
    """Copie d'un media adaptee a une plateforme."""

    __tablename__ = "media_variants"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_media_variants_storage_key"),
        UniqueConstraint(
            "id_media", "id_social_platforms", name="uq_media_variants_media_plateforme"
        ),
        CheckConstraint("file_type LIKE 'image/%'", name="images_seulement"),
        CheckConstraint("size_bytes > 0", name="poids_positif"),
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positives"),
        {
            "comment": (
                "Copie d'un media adaptee a une plateforme, creee seulement si "
                "l'original ne convient pas. Une seule par media et par plateforme. "
                "Pas de deleted_at : une variante est une donnee derivee, "
                "regenerable a partir de l'original, et rien ne s'y rattache."
            )
        },
    )

    id_media_variants: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_media: Mapped[int] = mapped_column(
        ForeignKey("media.id_media", name="fk_media_variants_id_media_media")
    )
    id_social_platforms: Mapped[int] = mapped_column(
        ForeignKey(
            "social_platforms.id_social_platforms",
            name="fk_media_variants_id_social_platforms",
        )
    )
    storage_key: Mapped[str] = mapped_column(
        String(512),
        comment="Cle de la copie adaptee. L'original reste dans media, qui fait foi.",
    )
    file_type: Mapped[str] = mapped_column(
        String(100),
        comment="Images uniquement : une video n'est pas reencodee par IAGORA.",
    )
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaReferenceNature(Base):
    """Ce qu'un media de reference represente."""

    __tablename__ = "media_reference_natures"
    __table_args__ = (
        UniqueConstraint("code", name="uq_media_reference_natures_code"),
        {
            "comment": (
                "Ce qu'un media de reference represente, pour que le modele d'image "
                "sache quoi en faire. Sans cette distinction, un flyer portant un "
                "logo et un portrait recoit deux images indifferenciees, et le logo "
                "ressort deforme."
            )
        },
    )

    id_media_reference_natures: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), comment="logo | personne | lieu | objet | fond.")
    label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(
        String(255),
        comment="Ce que le modele d'image doit faire de ce genre de reference.",
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=func.true())
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaReference(Base):
    """Un media qui sert de reference a la generation d'images."""

    __tablename__ = "media_references"
    __table_args__ = (
        # Unicite PARTIELLE : un media n'est reference qu'une fois, mais une
        # reference archivee ne doit pas interdire de le declarer a nouveau.
        Index(
            "uq_media_references_media_actif",
            "id_media",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Dit qu'un fichier sert de reference a la generation d'images, et "
                "porte ce qui le qualifie comme tel. La ligne nait sur un geste "
                "explicite : l'utilisateur designe le media et choisit sa nature."
            )
        },
    )

    id_media_references: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_media: Mapped[int] = mapped_column(
        ForeignKey("media.id_media", name="fk_media_references_id_media_media"),
        comment=(
            "Table satellite de media, sur le patron de media_variants : le "
            "fichier reste dans media, qui demeure la seule verite. Un media "
            "n'est reference qu'une fois."
        ),
    )
    id_media_reference_natures: Mapped[int] = mapped_column(
        ForeignKey(
            "media_reference_natures.id_media_reference_natures",
            name="fk_media_references_id_media_reference_natures",
        )
    )
    label: Mapped[str] = mapped_column(
        String(120), comment="Nom donne a la reference par l'utilisateur qui la declare."
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        comment=(
            "Description ecrite une seule fois par un appel de vision au premier "
            "depot, puis relue a chaque publication. Sert aussi de texte de "
            "recherche dans la bibliotheque."
        ),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.true(),
        comment="Etat d'exploitation, reversible : reference ecartee sans etre archivee.",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_media_references_id_users_created_by_users")
    )
    id_users_deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_media_references_id_users_deleted_by_users")
    )
