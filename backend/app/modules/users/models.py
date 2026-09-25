"""Tables users, permissions et user_permissions."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Permission(Base):
    """Droit attribuable : créer, valider, publier, consulter, administrer (F-22)."""

    __tablename__ = "permissions"
    __table_args__ = {
        "comment": "Droits attribuables aux utilisateurs. Table de référence, "
        "alimentée par migration : créer, valider, publier, consulter, administrer."
    }

    id_permissions: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant du droit."
    )
    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        comment="Code technique utilisé par le code Python : create, review, publish, read, admin. "
        "Ne change jamais.",
    )
    label: Mapped[str] = mapped_column(
        String(100), comment="Libellé affiché dans l'interface. Modifiable librement."
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="Ordre d'affichage dans les listes."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de création (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )


class UserPermission(Base):
    """Attribution d'un droit à un utilisateur."""

    __tablename__ = "user_permissions"
    __table_args__ = (
        UniqueConstraint("id_users", "id_permissions"),
        {
            "comment": "Quel utilisateur possède quel droit. Une personne peut en cumuler "
            "plusieurs, dans n'importe quelle combinaison : aucun rôle n'est figé."
        },
    )

    id_user_permissions: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
        comment="Identifiant de l'attribution.",
    )
    id_users: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id_users", ondelete="CASCADE"),
        comment="Utilisateur concerné. Supprimé avec lui.",
    )
    id_permissions: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id_permissions"), comment="Droit attribué."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date d'attribution du droit (UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )


class User(Base):
    """Membre de l'équipe DATUM Academy utilisant IAGORA."""

    __tablename__ = "users"
    __table_args__ = {
        "comment": "Membres de l'équipe DATUM Academy qui utilisent IAGORA. "
        "Ni les prospects, ni les inscrits aux webinaires : ceux-là vivent ailleurs."
    }

    id_users: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant de l'utilisateur."
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        comment="Adresse e-mail, identifiant de connexion. Toujours stockée en minuscules.",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        comment="Empreinte bcrypt du mot de passe. Irréversible : le mot de passe n'est "
        "jamais stocké, ni récupérable.",
    )
    first_name: Mapped[str] = mapped_column(String(100), comment="Prénom.")
    last_name: Mapped[str] = mapped_column(String(100), comment="Nom de famille.")

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        comment="Faux = compte suspendu temporairement : connexion refusée, mais le compte "
        "reste visible et réactivable.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Dernière connexion réussie (UTC). Vide si l'utilisateur ne s'est jamais connecté.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de création (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais "
        "l'historique et les publications continuent d'y renvoyer.",
    )

    permissions: Mapped[list[Permission]] = relationship(
        secondary="user_permissions", lazy="selectin", order_by=Permission.sort_order
    )

    @property
    def permission_codes(self) -> set[str]:
        return {permission.code for permission in self.permissions}

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_archived(self) -> bool:
        return self.deleted_at is not None
