"""Schémas Pydantic du module Comptes Zoom.

Le Client Secret n'entre que par `client_secret` et ne ressort jamais, même
chiffré. Le jeton d'accès non plus : l'interface ne reçoit que ses dates.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.zoom_accounts.constants import (
    CLIENT_SECRET_LENGTH_MAX,
    CLIENT_SECRET_LENGTH_MIN,
)

CheckKind = Literal["connection", "token_refresh"]


class ZoomAccountCreate(BaseModel):
    """Raccordement d'un compte Zoom."""

    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(..., min_length=1, max_length=120)
    host_email: EmailStr = Field(..., description="Adresse Zoom de la personne hôte.")
    external_zoom_account_id: str = Field(..., min_length=1, max_length=128)
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: str = Field(
        ..., min_length=CLIENT_SECRET_LENGTH_MIN, max_length=CLIENT_SECRET_LENGTH_MAX
    )
    verify_immediately: bool = True


class ZoomAccountUpdate(BaseModel):
    """Modification des champs non secrets. Le secret a sa propre route."""

    model_config = ConfigDict(str_strip_whitespace=True)

    label: str | None = Field(default=None, min_length=1, max_length=120)
    host_email: EmailStr | None = None
    external_zoom_account_id: str | None = Field(default=None, min_length=1, max_length=128)
    client_id: str | None = Field(default=None, min_length=1, max_length=255)


class ZoomClientSecretSave(BaseModel):
    """Remplacement du Client Secret."""

    model_config = ConfigDict(str_strip_whitespace=True)

    client_secret: str = Field(
        ..., min_length=CLIENT_SECRET_LENGTH_MIN, max_length=CLIENT_SECRET_LENGTH_MAX
    )
    verify_immediately: bool = True


class ZoomScopeRead(BaseModel):
    """Un droit Zoom attendu, et sa présence sur le dernier jeton."""

    scope: str
    label: str
    is_granted: bool


class ZoomAccountRead(BaseModel):
    """Fiche d'un compte Zoom, sans aucun secret."""

    id_zoom_accounts: int
    label: str
    host_email: str
    external_zoom_account_id: str
    client_id: str
    has_client_secret: bool
    client_secret_masked: str | None
    client_secret_obtained_at: datetime | None
    token_obtained_at: datetime | None
    token_expires_at: datetime | None
    has_valid_token: bool
    scopes: list[ZoomScopeRead] = Field(
        ..., description="Droits attendus ; tous « absents » tant qu'aucun jeton n'a été obtenu."
    )
    granted_scopes: list[str]
    last_verified_at: datetime | None
    last_verify_ok: bool | None
    last_verify_message: str | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ZoomAccountVerifyRead(BaseModel):
    """Résultat d'un échange réel avec Zoom.

    `verified` à faux n'est pas une erreur HTTP : un secret refusé arrive en 200
    et se lit dans `message`, comme pour les comptes d'envoi.
    """

    verified: bool
    message: str
    latency_ms: int
    account: ZoomAccountRead


class ZoomAccountCheckRead(BaseModel):
    """Une ligne de l'historique des vérifications."""

    id_zoom_account_checks: int
    kind: CheckKind
    is_ok: bool
    message: str | None
    latency_ms: int | None
    checked_at: datetime
    checked_by_name: str | None = None
