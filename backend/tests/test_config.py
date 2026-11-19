"""Règles de cohérence des réglages, vérifiées au démarrage de l'API.

Ces règles existent pour échouer tôt, avec un message utile, plutôt que de
laisser la panne arriver au premier dépôt de média. Elles méritent donc
d'être testées : un garde-fou qui ne garde rien est pire que pas de
garde-fou, parce qu'on croit être protégé.
"""

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings

ADRESSE_S3 = "https://1234567890abcdef.r2.cloudflarestorage.com"


def _reglages(**surcharges: object) -> Settings:
    """Jeu de réglages minimal et valide, .env ignoré, surchargé au besoin."""
    valeurs: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:5433/iagora",
        "JWT_SECRET_KEY": "cle-de-test-" + "x" * 40,
        "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }
    valeurs.update(surcharges)
    return Settings(_env_file=None, **valeurs)


def test_le_mode_local_ne_demande_aucun_identifiant() -> None:
    reglages = _reglages()
    assert reglages.STORAGE_BACKEND == "local"


def test_le_mode_r2_sans_identifiants_est_refuse() -> None:
    with pytest.raises(ValidationError) as echec:
        _reglages(STORAGE_BACKEND="r2")
    message = str(echec.value)
    for nom in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        assert nom in message


def _reglages_r2(url_publique: str) -> Settings:
    return _reglages(
        STORAGE_BACKEND="r2",
        R2_ACCOUNT_ID="1234567890abcdef",
        R2_ACCESS_KEY_ID="identifiant-de-test",
        R2_SECRET_ACCESS_KEY="secret-de-test",
        R2_BUCKET="iagora-medias",
        R2_PUBLIC_BASE_URL=url_publique,
    )


def _reglages_r2_seau(seau: str) -> Settings:
    return _reglages(
        STORAGE_BACKEND="r2",
        R2_ACCOUNT_ID="1234567890abcdef",
        R2_ACCESS_KEY_ID="identifiant-de-test",
        R2_SECRET_ACCESS_KEY="secret-de-test",
        R2_BUCKET=seau,
        R2_PUBLIC_BASE_URL="https://pub-abcdef1234.r2.dev",
    )


def test_l_adresse_s3_est_refusee_comme_url_publique() -> None:
    """L'erreur la plus facile à commettre : les deux URL ne sont pas la même."""
    with pytest.raises(ValidationError) as echec:
        _reglages_r2(ADRESSE_S3)
    assert "r2.cloudflarestorage.com" in str(echec.value)


def test_l_url_de_developpement_publique_est_acceptee() -> None:
    reglages = _reglages_r2("https://pub-abcdef1234.r2.dev")
    assert reglages.R2_PUBLIC_BASE_URL == "https://pub-abcdef1234.r2.dev"


def test_un_domaine_personnalise_est_accepte() -> None:
    reglages = _reglages_r2("https://medias.datum-academy.com")
    assert reglages.R2_PUBLIC_BASE_URL == "https://medias.datum-academy.com"


def test_l_adresse_s3_du_compte_est_construite_depuis_l_identifiant() -> None:
    reglages = _reglages_r2("https://pub-abcdef1234.r2.dev")
    assert reglages.r2_endpoint_url == ADRESSE_S3


def test_un_nom_de_seau_avec_une_barre_oblique_est_refuse() -> None:
    """Faute commise une fois : « bucket-datum-academy/ » recopie du tableau de bord."""
    with pytest.raises(ValidationError) as echec:
        _reglages_r2_seau("iagora-medias/")
    assert "sans « / »" in str(echec.value)
