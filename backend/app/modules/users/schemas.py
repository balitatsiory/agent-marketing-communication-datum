"""Formats d'entrée et de sortie du module Utilisateurs et droits."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import MOT_DE_PASSE_OCTETS_MAX

# bcrypt ignore tout au-delà de 72 OCTETS. La borne porte sur les caractères,
# qui en valent jusqu'à quatre en UTF-8 : le service revérifie en octets.
MotDePasse = Field(min_length=10, max_length=MOT_DE_PASSE_OCTETS_MAX)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_users: int
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = MotDePasse
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserUpdate(BaseModel):
    """Modification partielle : seuls les champs fournis sont appliqués."""

    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class PasswordSet(BaseModel):
    """Changement de mot de passe par un administrateur."""

    password: str = MotDePasse


class PasswordChange(BaseModel):
    """Changement de son propre mot de passe : l'ancien est exigé."""

    current_password: str
    new_password: str = MotDePasse


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    description: str | None
    sort_order: int


class PermissionCodes(BaseModel):
    """Ensemble COMPLET des droits de l'utilisateur, pas un ajout.

    L'écran des habilitations coche et décoche des cases puis enregistre un
    état : c'est ce que PUT exprime, et cela évite la question « qu'arrive-t-il
    aux droits non mentionnés ».
    """

    codes: list[str]
