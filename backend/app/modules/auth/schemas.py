"""Entrées et sorties de l'authentification."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Identifiants de connexion."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"email": "admin@datum-academy.fr", "password": "votre-mot-de-passe"}
        },
    )

    email: EmailStr = Field(description="Adresse e-mail du compte.")
    password: str = Field(min_length=1, description="Mot de passe en clair, transmis en HTTPS.")


class RefreshRequest(BaseModel):
    """Demande d'un nouveau jeton d'accès."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, description="Le `refresh_token` reçu à la connexion.")


class TokenPair(BaseModel):
    """Couple de jetons remis au client.

    `expires_in` est en secondes : le front sait quand demander un renouvellement
    sans attendre une erreur 401.
    """

    access_token: str = Field(description="À coller dans le bouton « Authorize » de Swagger.")
    refresh_token: str = Field(description="À conserver pour renouveler le jeton d'accès.")
    token_type: str = "bearer"
    expires_in: int = Field(description="Durée de validité du jeton d'accès, en secondes.")
