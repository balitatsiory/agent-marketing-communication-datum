"""Tests de app/core/security.py — aucune base de données nécessaire."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.errors import AuthenticationError


# --------------------------------------------------------------------------
# Mots de passe
# --------------------------------------------------------------------------
def test_un_mot_de_passe_correct_est_reconnu() -> None:
    empreinte = security.hash_password("motdepasse-de-test")
    assert security.verify_password("motdepasse-de-test", empreinte)


def test_un_mot_de_passe_faux_est_refuse() -> None:
    empreinte = security.hash_password("motdepasse-de-test")
    assert not security.verify_password("autre-mot-de-passe", empreinte)


def test_deux_hachages_du_meme_mot_de_passe_different() -> None:
    # Le sel est tiré au hasard : deux empreintes identiques révéleraient
    # que deux comptes ont le même mot de passe.
    assert security.hash_password("identique") != security.hash_password("identique")


def test_un_mot_de_passe_trop_long_est_refuse() -> None:
    # bcrypt ignorerait silencieusement ce qui dépasse 72 octets.
    with pytest.raises(ValueError, match="72"):
        security.hash_password("a" * 73)


def test_une_empreinte_illisible_ne_fait_pas_planter() -> None:
    assert not security.verify_password("peu importe", "ceci-n-est-pas-une-empreinte")


# --------------------------------------------------------------------------
# Jetons d'accès
# --------------------------------------------------------------------------
def test_un_jeton_d_acces_conserve_utilisateur_et_droits() -> None:
    jeton = security.create_access_token(12, ["read", "review"])
    contenu = security.decode_access_token(jeton)

    assert contenu.id_users == 12
    assert contenu.permissions == ["read", "review"]


def test_un_jeton_falsifie_est_refuse() -> None:
    jeton = security.create_access_token(12, ["read"])
    falsifie = jeton[:-3] + ("aaa" if not jeton.endswith("aaa") else "bbb")

    with pytest.raises(AuthenticationError):
        security.decode_access_token(falsifie)


def test_un_jeton_signe_avec_une_autre_cle_est_refuse() -> None:
    jeton = jwt.encode({"sub": "12", "type": "access"}, "cle-de-l-attaquant", algorithm="HS256")

    with pytest.raises(AuthenticationError):
        security.decode_access_token(jeton)


def test_un_jeton_expire_est_refuse() -> None:
    passe = datetime.now(UTC) - timedelta(minutes=1)
    jeton = jwt.encode(
        {"sub": "12", "perms": [], "type": "access", "exp": passe},
        security.settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError, match="expiré"):
        security.decode_access_token(jeton)


def test_un_jeton_de_renouvellement_ne_passe_pas_pour_un_jeton_d_acces() -> None:
    jeton = jwt.encode(
        {"sub": "12", "type": "refresh", "exp": datetime.now(UTC) + timedelta(days=1)},
        security.settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError):
        security.decode_access_token(jeton)


# --------------------------------------------------------------------------
# Jetons de renouvellement
# --------------------------------------------------------------------------
def test_deux_jetons_de_renouvellement_sont_differents() -> None:
    assert security.generate_refresh_token() != security.generate_refresh_token()


def test_l_empreinte_d_un_jeton_de_renouvellement_est_stable() -> None:
    # Déterministe, sinon on ne pourrait pas retrouver la session en base.
    jeton = security.generate_refresh_token()
    assert security.hash_refresh_token(jeton) == security.hash_refresh_token(jeton)
    assert jeton not in security.hash_refresh_token(jeton)


def test_l_expiration_est_dans_le_futur() -> None:
    assert security.refresh_token_expiry() > datetime.now(UTC)


# --------------------------------------------------------------------------
# Chiffrement des jetons Meta
# --------------------------------------------------------------------------
def test_un_jeton_meta_se_retrouve_apres_chiffrement() -> None:
    clair = "EAAGm0PX4ZCpsBA-jeton-de-page"
    chiffre = security.encrypt_token(clair)

    assert chiffre != clair
    assert security.decrypt_token(chiffre) == clair


def test_une_valeur_corrompue_est_signalee() -> None:
    with pytest.raises(ValueError, match="illisible"):
        security.decrypt_token("valeur-corrompue")
