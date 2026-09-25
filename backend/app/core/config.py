"""Réglages de l'application, lus depuis .env via pydantic-settings.

Aucune valeur d'environnement n'est lue ailleurs : tout passe par `get_settings()`.
Un réglage manquant ou incohérent empêche le démarrage, plutôt que de provoquer
une erreur plus tard, en pleine utilisation.
"""

from functools import lru_cache
from typing import Literal, Self

from cryptography.fernet import Fernet
from pydantic import PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]
SocialGateway = Literal["n8n", "meta"]


class Settings(BaseSettings):
    """Ensemble des réglages de l'API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- environnement ---
    ENVIRONMENT: Environment = "local"

    # --- base de données ---
    DATABASE_URL: PostgresDsn

    # --- sécurité ---
    JWT_SECRET_KEY: SecretStr
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    TOKEN_ENCRYPTION_KEY: SecretStr

    # --- interface web ---
    # Liste d'origines séparées par des virgules ; voir la propriété cors_origins.
    CORS_ORIGINS: str = ""

    # --- réseaux sociaux ---
    SOCIAL_GATEWAY: SocialGateway = "n8n"
    N8N_BASE_URL: str | None = None
    META_API_VERSION: str = "v26.0"
    META_APP_ID: str | None = None
    META_APP_SECRET: SecretStr | None = None
    META_WEBHOOK_VERIFY_TOKEN: SecretStr | None = None

    # --- intelligence artificielle (étape ultérieure) ---
    LLM_PROVIDER: str | None = None
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        """Origines autorisées, converties depuis la chaîne séparée par des virgules."""
        return [origine.strip() for origine in self.CORS_ORIGINS.split(",") if origine.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @model_validator(mode="after")
    def verifier_coherence(self) -> Self:
        """Refuse une configuration incomplète ou restée aux valeurs d'exemple.

        Mieux vaut échouer au démarrage, avec un message clair, qu'au premier usage :
        une clé Fernet invalide ne se verrait qu'au moment de chiffrer un jeton Meta,
        des semaines plus tard.
        """
        if self.SOCIAL_GATEWAY == "n8n" and not self.N8N_BASE_URL:
            raise ValueError("SOCIAL_GATEWAY=n8n exige N8N_BASE_URL.")
        if self.SOCIAL_GATEWAY == "meta" and not (self.META_APP_ID and self.META_APP_SECRET):
            raise ValueError("SOCIAL_GATEWAY=meta exige META_APP_ID et META_APP_SECRET.")

        if self.JWT_SECRET_KEY.get_secret_value().startswith("a-remplacer"):
            raise ValueError(
                "JWT_SECRET_KEY a gardé sa valeur d'exemple. Générer une clé avec :\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Une clé Fernet est faite de 32 octets encodés en base64 url-safe, soit
        # 44 caractères. On le vérifie ici plutôt que de découvrir l'erreur plus tard.
        cle = self.TOKEN_ENCRYPTION_KEY.get_secret_value()
        try:
            Fernet(cle.encode("utf-8"))
        except (ValueError, TypeError) as erreur:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY n'est pas une clé Fernet valide. La générer avec :\n"
                '  python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from erreur

        return self


@lru_cache
def get_settings() -> Settings:
    """Renvoie les réglages, lus une seule fois puis conservés en mémoire."""
    # Les valeurs viennent de l'environnement, pas d'arguments : mypy ne peut pas le savoir.
    return Settings()  # type: ignore[call-arg]
