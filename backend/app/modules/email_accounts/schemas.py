"""Schémas Pydantic du module Comptes d'envoi (SMTP).

Le mot de passe n'entre que par `password` et ne ressort jamais : aucun schéma
de lecture ne le porte, même chiffré. Ce que l'interface reçoit, c'est
`password_masked` — de quoi montrer qu'un mot de passe existe et depuis quand.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.email_accounts.constants import (
    IONOS_HOST,
    PASSWORD_LENGTH_MAX,
    PASSWORD_LENGTH_MIN,
    PORT_SSL_TLS,
    TIMEOUT_SECONDS_DEFAULT,
    TIMEOUT_SECONDS_MAX,
    TIMEOUT_SECONDS_MIN,
)

Security = Literal["ssl_tls", "starttls"]
CheckKind = Literal["connection", "test_message"]


class EmailAccountCreate(BaseModel):
    """Création d'un compte d'envoi, mot de passe compris.

    Les valeurs par défaut sont celles d'IONOS en SSL/TLS : c'est le cas
    courant, et l'interface n'a qu'à les montrer.
    """

    label: str = Field(..., min_length=1, max_length=120)
    host: str = Field(default=IONOS_HOST, min_length=1, max_length=255)
    port: int = Field(default=PORT_SSL_TLS, ge=1, le=65535)
    security: Security = "ssl_tls"
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=PASSWORD_LENGTH_MIN, max_length=PASSWORD_LENGTH_MAX)
    from_email: EmailStr
    from_name: str | None = Field(default=None, max_length=120)
    reply_to_email: EmailStr | None = None
    timeout_seconds: int = Field(
        default=TIMEOUT_SECONDS_DEFAULT, ge=TIMEOUT_SECONDS_MIN, le=TIMEOUT_SECONDS_MAX
    )
    is_default: bool = False
    verify_immediately: bool = True


class EmailAccountUpdate(BaseModel):
    """Modification des champs non secrets. Le mot de passe a sa propre route."""

    label: str | None = Field(default=None, min_length=1, max_length=120)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    security: Security | None = None
    username: str | None = Field(default=None, min_length=1, max_length=255)
    from_email: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=120)
    reply_to_email: EmailStr | None = None
    timeout_seconds: int | None = Field(
        default=None, ge=TIMEOUT_SECONDS_MIN, le=TIMEOUT_SECONDS_MAX
    )


class EmailAccountPasswordSave(BaseModel):
    """Remplacement du mot de passe d'un compte."""

    password: str = Field(..., min_length=PASSWORD_LENGTH_MIN, max_length=PASSWORD_LENGTH_MAX)
    verify_immediately: bool = True


class EmailAccountTestMessage(BaseModel):
    """Message de test à envoyer réellement, pour vérifier la chaîne de bout en bout."""

    recipient_email: EmailStr
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=5000)


class EmailAccountRead(BaseModel):
    """Fiche d'un compte d'envoi. Jamais de mot de passe, même chiffré."""

    model_config = ConfigDict(from_attributes=True)

    id_email_accounts: int
    label: str
    host: str
    port: int
    security: Security
    username: str
    from_email: str
    from_name: str | None
    reply_to_email: str | None
    timeout_seconds: int
    is_default: bool
    has_password: bool
    password_masked: str | None
    password_obtained_at: datetime | None
    last_verified_at: datetime | None
    last_verify_ok: bool | None
    last_verify_message: str | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class EmailAccountVerifyRead(BaseModel):
    """Résultat d'un échange réel avec le serveur SMTP.

    `verified` à faux n'est pas une erreur d'API : un mot de passe refusé par
    IONOS est un résultat à afficher, pas une panne de l'API.
    """

    verified: bool
    message: str
    latency_ms: int
    account: EmailAccountRead


class EmailAccountCheckRead(BaseModel):
    """Une ligne de l'historique des vérifications."""

    model_config = ConfigDict(from_attributes=True)

    id_email_account_checks: int
    kind: CheckKind
    is_ok: bool
    message: str | None
    recipient_email: str | None
    latency_ms: int | None
    checked_at: datetime
    checked_by_name: str | None = None
