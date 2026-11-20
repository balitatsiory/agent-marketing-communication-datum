"""Réglages de l'application, lus depuis .env via pydantic-settings.

Aucune variable d'environnement n'est lue ailleurs : tout passe par
`get_settings()`. Un réglage manquant ou incohérent empêche le démarrage plutôt
que de provoquer une panne plus tard, en pleine utilisation.
"""

from functools import lru_cache
from typing import Literal, Self

from cryptography.fernet import Fernet
from pydantic import PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]


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
    TEST_DATABASE_URL: PostgresDsn | None = None

    # --- sécurité ---
    JWT_SECRET_KEY: SecretStr
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7
    TOKEN_ENCRYPTION_KEY: SecretStr

    # --- interface web ---
    # Liste d'origines séparées par des virgules ; voir la propriété cors_origins.
    CORS_ORIGINS: str = ""

    # --- connecteurs Meta (facultatifs : servent à appeler /debug_token) ---
    META_APP_ID: str = ""
    META_APP_SECRET: SecretStr | None = None

    # --- stockage des médias ---
    # « local » écrit dans un dossier du poste : c'est le mode des tests et du
    # développement, pour que la suite de tests ne dépende ni du réseau ni
    # d'identifiants Cloudflare. « r2 » est le mode réel.
    STORAGE_BACKEND: Literal["local", "r2"] = "local"
    STORAGE_LOCAL_DIR: str = "var/medias"

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: SecretStr | None = None
    R2_SECRET_ACCESS_KEY: SecretStr | None = None
    R2_BUCKET: str = ""
    # Domaine public du seau. La conception sert les médias par URL publique :
    # aucune signature n'est donc nécessaire en lecture.
    R2_PUBLIC_BASE_URL: str = ""

    # --- limites des médias ---
    # 8 Mo est le plafond de ce qui est RANGÉ : au-delà, l'image est compressée
    # pour y revenir, elle n'est pas refusée (architecture v1.4 du 21/10/2026).
    MEDIA_MAX_STORED_BYTES: int = 8 * 1024 * 1024
    # Garde-fou de SOUMISSION, au-delà duquel le dépôt est refusé sans être lu
    # jusqu'au bout. Repris du même document, où il porte la mention « à valider ».
    MEDIA_MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024
    # 36 millions de pixels : limite du même document, reprise de LinkedIn.
    MEDIA_MAX_PIXELS: int = 36_000_000

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
        une clé Fernet invalide ne se verrait qu'au moment de chiffrer un secret de
        plateforme, des semaines plus tard.
        """
        if self.JWT_SECRET_KEY.get_secret_value().startswith("a-remplacer"):
            raise ValueError(
                "JWT_SECRET_KEY a gardé sa valeur d'exemple. Générer une clé avec :\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Une clé Fernet est faite de 32 octets encodés en base64 url-safe, soit
        # 44 caractères. On le vérifie ici plutôt que de le découvrir plus tard.
        cle = self.TOKEN_ENCRYPTION_KEY.get_secret_value()
        try:
            Fernet(cle.encode("utf-8"))
        except (ValueError, TypeError) as erreur:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY n'est pas une clé Fernet valide. La générer avec :\n"
                '  python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from erreur

        if self.ACCESS_TOKEN_MINUTES < 1:
            raise ValueError("ACCESS_TOKEN_MINUTES doit valoir au moins 1.")
        if self.REFRESH_TOKEN_DAYS < 1:
            raise ValueError("REFRESH_TOKEN_DAYS doit valoir au moins 1.")

        # Un dépôt qui échouerait faute d'identifiants se verrait au premier
        # fichier envoyé, en pleine utilisation. On le refuse au démarrage.
        if self.STORAGE_BACKEND == "r2":
            manquants = [
                nom
                for nom, valeur in (
                    ("R2_ACCOUNT_ID", self.R2_ACCOUNT_ID),
                    ("R2_ACCESS_KEY_ID", self.R2_ACCESS_KEY_ID),
                    ("R2_SECRET_ACCESS_KEY", self.R2_SECRET_ACCESS_KEY),
                    ("R2_BUCKET", self.R2_BUCKET),
                )
                if not valeur
            ]
            if manquants:
                raise ValueError(
                    "STORAGE_BACKEND vaut « r2 » mais ces réglages manquent : "
                    + ", ".join(manquants)
                    + ". Les créer dans le tableau de bord Cloudflare, section R2 "
                    "puis « Manage R2 API Tokens »."
                )

            # Confusion fréquente : l'adresse S3 du compte n'est pas l'adresse
            # publique du seau. La première n'accepte que des requêtes signées
            # et porte le nom du seau dans son chemin ; la seconde est servie en
            # lecture anonyme et ne le porte pas. Comme url_publique() colle la
            # clé derrière cette base, s'y tromper produit des URL de média en
            # erreur 401, visibles seulement dans le navigateur de l'utilisateur.
            # Un nom de seau S3 ne contient pas de « / ». Colle tel quel dans
            # l'appel boto3, il produirait une requete refusee des le premier
            # depot. Faute facile quand on recopie un chemin du tableau de bord.
            if "/" in self.R2_BUCKET:
                raise ValueError(
                    "R2_BUCKET doit porter le seul nom du seau, sans « / » : "
                    f"lu « {self.R2_BUCKET} »."
                )

            if "r2.cloudflarestorage.com" in self.R2_PUBLIC_BASE_URL:
                raise ValueError(
                    "R2_PUBLIC_BASE_URL porte l'adresse S3 du compte "
                    "(r2.cloudflarestorage.com), qui n'est pas publique. Y mettre "
                    "l'URL de développement publique du seau (R2 > le seau > "
                    "Settings > Public Development URL) ou son domaine personnalisé."
                )

        if self.MEDIA_MAX_STORED_BYTES > self.MEDIA_MAX_UPLOAD_BYTES:
            raise ValueError(
                "MEDIA_MAX_STORED_BYTES dépasse MEDIA_MAX_UPLOAD_BYTES : un fichier "
                "serait refusé à la soumission avant d'avoir pu être compressé."
            )

        return self

    @property
    def r2_endpoint_url(self) -> str:
        """Adresse S3 du compte R2.

        R2 n'a pas de régions : boto3 en exige une, elle vaut « auto » et
        n'est pas utilisée.
        """
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


@lru_cache
def get_settings() -> Settings:
    """Renvoie les réglages, lus une seule fois puis conservés en mémoire."""
    # Les valeurs viennent de l'environnement, pas d'arguments : mypy l'ignore.
    return Settings()  # type: ignore[call-arg]
