"""Tables du module Utilisateurs et droits.

Les commentaires, contraintes d'unicité et index sont déclarés ici À L'IDENTIQUE
de la migration 0001. Ce n'est pas de la redondance : `alembic revision
--autogenerate` compare les modèles à la base, et tout ce qui n'est pas déclaré
ici serait proposé en SUPPRESSION dans la migration d'un module suivant.
`alembic check` le vérifie.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """Membre de l'équipe DATUM Academy.

    `is_active` est l'état d'exploitation, réversible. `deleted_at` est
    l'archivage, posé par-dessus cet état : le compte sort des listes mais reste
    l'auteur de ses publications passées.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Index PARTIEL sur lower(email) : sans lui, deux comptes existeraient
        # pour la même personne ; sans la clause partielle, un compte archivé
        # interdirait de recréer son adresse.
        Index(
            "uq_users_email_actif",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Membres de l'equipe DATUM Academy qui utilisent IAGORA. Un compte "
                "archive (deleted_at) disparait des listes mais reste l'auteur de "
                "ses publications passees."
            )
        },
    )

    id_users: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(
        String(254),
        comment="Identifiant de connexion. Unique a la casse pres, parmi les comptes non archives.",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        comment=(
            "Empreinte bcrypt. Dimensionnee large pour ne pas bloquer un passage "
            "ulterieur a argon2, qui produit des empreintes plus longues."
        ),
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.true(),
        comment="Etat d'exploitation, reversible : acces suspendu sans archivage.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Derniere connexion reussie."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment=(
            "Archivage, pose PAR-DESSUS l'etat et non a sa place. L'archivage "
            "revoque tous les jetons de l'utilisateur dans la meme transaction."
        ),
    )
    id_users_created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
    id_users_changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
    id_users_deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))

    @property
    def est_utilisable(self) -> bool:
        """Un compte archivé ou suspendu ne peut ni se connecter ni agir."""
        return self.deleted_at is None and self.is_active

    @property
    def nom_affiche(self) -> str:
        """Nom à montrer dans l'interface, l'adresse à défaut de nom.

        Déclaré ici plutôt que recopié dans chaque module : trois services
        composaient déjà « prénom nom » à leur façon.
        """
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Permission(Base):
    """Droit attribuable. Référentiel alimenté par migration."""

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
        {
            "comment": (
                "Droits attribuables, alimentes par migration. Chaque module insere "
                "les siens, avec un sort_order valant son numero de module multiplie "
                "par 100, par pas de 10. Un droit se retire par migration : il ne "
                "s'archive pas."
            )
        },
    )

    id_permissions: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(60),
        comment="Identifiant stable du droit, en anglais, minuscules et tiret bas.",
    )
    label: Mapped[str] = mapped_column(
        String(120), comment="Libelle francais affiche dans l'ecran des habilitations."
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        comment="Phrase expliquant ce que le droit autorise, affichee a l'administrateur.",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, comment="Ordre d'affichage : numero du module x 100, par pas de 10."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPermission(Base):
    """Attribution d'un droit à un utilisateur.

    Une révocation archive la ligne au lieu de la supprimer : l'historique des
    attributions est lui-même une information de traçabilité.
    """

    __tablename__ = "user_permissions"
    __table_args__ = (
        # Unicité PARTIELLE : un droit révoqué doit pouvoir être réattribué,
        # l'ancienne ligne restant archivée.
        Index(
            "uq_user_permissions_actif",
            "id_users",
            "id_permissions",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Quel utilisateur possede quel droit. Aucun role n'est fige : les "
                "droits se cumulent. Une revocation archive la ligne au lieu de la "
                "supprimer, pour garder la trace de qui a pu faire quoi et quand."
            )
        },
    )

    id_user_permissions: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_users: Mapped[int] = mapped_column(ForeignKey("users.id_users"))
    id_permissions: Mapped[int] = mapped_column(ForeignKey("permissions.id_permissions"))
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users"), comment="Qui a attribue ce droit."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Revocation du droit. La ligne est conservee pour l'historique.",
    )
    id_users_deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
