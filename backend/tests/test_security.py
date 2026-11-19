"""Empreintes et jetons.

Ces tests ne touchent pas la base : ils vérifient les deux fonctions de hachage
et le cycle d'un jeton d'accès. C'est le socle sur lequel repose toute
l'authentification, et une régression y serait silencieuse.
"""

import pytest

from app.core.errors import ApiError, NotAuthenticatedError
from app.core.security import (
    MOT_DE_PASSE_OCTETS_MAX,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)


class TestMotDePasse:
    def test_une_empreinte_bcrypt_est_produite(self) -> None:
        assert hash_password("Dev-Admin-2026").startswith("$2")

    def test_le_bon_mot_de_passe_est_accepte(self) -> None:
        empreinte = hash_password("Dev-Admin-2026")
        assert verify_password("Dev-Admin-2026", empreinte)

    def test_un_mauvais_mot_de_passe_est_refuse(self) -> None:
        empreinte = hash_password("Dev-Admin-2026")
        assert not verify_password("Dev-Admin-2027", empreinte)

    def test_deux_empreintes_du_meme_mot_de_passe_diffèrent(self) -> None:
        """Le sel doit être différent à chaque fois, sinon deux comptes avec le
        même mot de passe seraient reconnaissables en base."""
        assert hash_password("identique") != hash_password("identique")

    def test_une_empreinte_illisible_ne_fait_pas_echouer_la_requete(self) -> None:
        """Une valeur abîmée en base doit refuser la connexion, pas provoquer
        une erreur 500."""
        assert not verify_password("peu importe", "ceci-n-est-pas-une-empreinte")


class TestLimiteDeBcrypt:
    """bcrypt ignore tout au-delà de 72 octets. On refuse explicitement."""

    def test_un_mot_de_passe_trop_long_est_refuse(self) -> None:
        with pytest.raises(ApiError) as erreur:
            hash_password("a" * (MOT_DE_PASSE_OCTETS_MAX + 1))
        assert erreur.value.code == "password_too_long"

    def test_les_caracteres_accentues_comptent_double(self) -> None:
        """Le piège réel : 40 caractères accentués font 80 octets en UTF-8.

        Une phrase de passe française d'apparence raisonnable dépasse donc la
        limite, alors que 40 caractères ASCII passeraient.
        """
        phrase = "é" * 40
        assert len(phrase) < MOT_DE_PASSE_OCTETS_MAX
        assert len(phrase.encode("utf-8")) > MOT_DE_PASSE_OCTETS_MAX
        with pytest.raises(ApiError):
            hash_password(phrase)

    def test_un_mot_de_passe_trop_long_ne_peut_pas_se_verifier(self) -> None:
        assert not verify_password("a" * 100, hash_password("court"))


class TestJetonDeRenouvellement:
    def test_le_jeton_est_assez_long(self) -> None:
        assert len(new_refresh_token()) >= 60

    def test_l_empreinte_fait_64_caracteres_hexadecimaux(self) -> None:
        empreinte = hash_token(new_refresh_token())
        assert len(empreinte) == 64
        assert all(caractere in "0123456789abcdef" for caractere in empreinte)

    def test_l_empreinte_est_deterministe(self) -> None:
        """Contrairement à bcrypt : c'est par l'empreinte qu'on RETROUVE la ligne
        en base, elle doit donc être calculable à l'identique."""
        jeton = new_refresh_token()
        assert hash_token(jeton) == hash_token(jeton)

    def test_deux_jetons_donnent_deux_empreintes(self) -> None:
        assert hash_token(new_refresh_token()) != hash_token(new_refresh_token())


class TestJetonDAcces:
    def test_le_jeton_se_decode_vers_le_bon_identifiant(self) -> None:
        assert decode_access_token(create_access_token(42)) == 42

    def test_un_jeton_falsifie_est_refuse(self) -> None:
        with pytest.raises(NotAuthenticatedError):
            decode_access_token(create_access_token(42) + "falsifie")

    def test_un_jeton_mal_forme_est_refuse(self) -> None:
        with pytest.raises(NotAuthenticatedError):
            decode_access_token("n-importe-quoi")
