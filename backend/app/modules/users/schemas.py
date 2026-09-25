"""Entrées et sorties de l'API pour les utilisateurs et leurs droits."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import MAX_PASSWORD_BYTES
from app.modules.users.constants import PermissionCode
from app.modules.users.models import Permission, User


class PermissionRead(BaseModel):
    """Droit, tel qu'affiché dans l'interface."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str


class UserCreate(BaseModel):
    """Création d'un compte par un administrateur (F-22)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "sarah@datum-academy.fr",
                "password": "un-mot-de-passe-solide",
                "first_name": "Sarah",
                "last_name": "Lemoine",
                "permissions": ["read", "create"],
            }
        },
    )

    email: EmailStr = Field(description="Sert d'identifiant de connexion. Doit être libre.")
    password: str = Field(
        min_length=12,
        max_length=MAX_PASSWORD_BYTES,
        description="12 caractères minimum, 72 octets maximum (limite de bcrypt).",
    )
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    permissions: list[PermissionCode] = Field(
        default_factory=list,
        description="Droits accordés : read, create, review, publish, admin.",
    )


class UserUpdate(BaseModel):
    """Modification d'un compte. Tous les champs sont facultatifs.

    Ni l'email ni le mot de passe : ils relèvent d'opérations dédiées.
    """

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = Field(
        default=None, description="Faux = compte suspendu, réactivable à tout moment."
    )
    permissions: list[PermissionCode] | None = Field(
        default=None,
        description="Remplace la liste des droits. Omettre le champ la laisse intacte.",
    )


class UserRead(BaseModel):
    """Compte tel que renvoyé par l'API.

    Ni `password_hash`, ni `deleted_at` : ils ne sortent jamais.
    """

    id_users: int
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    is_active: bool
    last_login_at: datetime | None
    permissions: list[PermissionRead]

    @classmethod
    def from_model(cls, user: User) -> Self:
        return cls(
            id_users=user.id_users,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            permissions=[
                PermissionRead.model_validate(permission) for permission in user.permissions
            ],
        )


class PasswordChange(BaseModel):
    """Changement de son propre mot de passe."""

    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str = Field(min_length=12, max_length=MAX_PASSWORD_BYTES)


def permission_to_read(permission: Permission) -> PermissionRead:
    return PermissionRead.model_validate(permission)
