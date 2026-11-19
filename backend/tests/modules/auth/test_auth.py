"""Connexion, renouvellement, déconnexion.

Le cœur de ces tests est la ROTATION : un jeton de renouvellement utilisé est
révoqué, et le rejeu d'un jeton révoqué invalide toute la lignée. Sans ces
tests, la rotation ressemblerait à de la rotation sans en être.
"""

from httpx import AsyncClient

from tests.conftest import entete

MOT_DE_PASSE = "Dev-Mot-De-Passe-2026"


class TestConnexion:
    async def test_un_compte_valide_recoit_deux_jetons(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        reponse = await client.post(
            "/api/v1/auth/login", json={"email": utilisateur.email, "password": MOT_DE_PASSE}
        )
        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["access_token"] and corps["refresh_token"]
        assert corps["token_type"] == "bearer"
        assert corps["expires_in"] == 900

    async def test_un_mauvais_mot_de_passe_est_refuse(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        reponse = await client.post(
            "/api/v1/auth/login", json={"email": utilisateur.email, "password": "faux-mot-de-passe"}
        )
        assert reponse.status_code == 401

    async def test_le_message_ne_dit_pas_laquelle_des_deux_valeurs_est_fausse(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        """Distinguer « adresse inconnue » de « mot de passe faux » révélerait
        quelles adresses ont un compte."""
        utilisateur = await fabrique_utilisateur()
        inconnue = await client.post(
            "/api/v1/auth/login",
            json={"email": "personne@iagora.example.com", "password": MOT_DE_PASSE},
        )
        mauvais = await client.post(
            "/api/v1/auth/login", json={"email": utilisateur.email, "password": "faux"}
        )
        assert inconnue.json()["error"] == mauvais.json()["error"]

    async def test_un_compte_suspendu_ne_peut_pas_se_connecter(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        utilisateur = await fabrique_utilisateur(is_active=False)
        reponse = await client.post(
            "/api/v1/auth/login", json={"email": utilisateur.email, "password": MOT_DE_PASSE}
        )
        assert reponse.status_code == 401
        assert "suspendu" in reponse.json()["error"]["message"].lower()

    async def test_un_compte_archive_ne_peut_pas_se_connecter(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        utilisateur = await fabrique_utilisateur(archive=True)
        reponse = await client.post(
            "/api/v1/auth/login", json={"email": utilisateur.email, "password": MOT_DE_PASSE}
        )
        assert reponse.status_code == 401

    async def test_la_casse_de_l_adresse_n_empeche_pas_la_connexion(
        self, client: AsyncClient, fabrique_utilisateur
    ) -> None:
        utilisateur = await fabrique_utilisateur(email="Casse@iagora.example.com")
        reponse = await client.post(
            "/api/v1/auth/login",
            json={"email": utilisateur.email.upper(), "password": MOT_DE_PASSE},
        )
        assert reponse.status_code == 200


class TestProfilCourant:
    async def test_sans_jeton_la_route_renvoie_401(self, client: AsyncClient) -> None:
        reponse = await client.get("/api/v1/auth/me")
        assert reponse.status_code == 401
        assert reponse.json()["error"]["code"] == "not_authenticated"

    async def test_le_profil_porte_les_droits(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(utilisateur.email)
        reponse = await client.get("/api/v1/auth/me", headers=entete(jetons))
        assert reponse.status_code == 200
        assert reponse.json()["permissions"] == ["manage_users"]

    async def test_un_jeton_invente_est_refuse(self, client: AsyncClient) -> None:
        reponse = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer pas-un-jeton"}
        )
        assert reponse.status_code == 401


class TestRotation:
    async def test_le_renouvellement_donne_un_nouveau_couple(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        reponse = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": jetons["refresh_token"]}
        )
        assert reponse.status_code == 200
        assert reponse.json()["refresh_token"] != jetons["refresh_token"]

    async def test_l_ancien_jeton_ne_sert_plus_apres_rotation(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        await client.post("/api/v1/auth/refresh", json={"refresh_token": jetons["refresh_token"]})

        rejeu = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": jetons["refresh_token"]}
        )
        assert rejeu.status_code == 401

    async def test_le_rejeu_invalide_toute_la_lignee(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """C'est la raison d'être de family_id.

        Un ancien jeton qui revient signifie qu'il a fuité ou que le client a
        perdu le fil : le jeton courant, pourtant légitime, doit cesser de
        fonctionner lui aussi. Sans cela, un voleur et le propriétaire
        continueraient tous deux à renouveler.
        """
        utilisateur = await fabrique_utilisateur()
        premier = await connexion(utilisateur.email)
        second = (
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": premier["refresh_token"]}
            )
        ).json()

        # Le voleur rejoue le premier jeton.
        await client.post("/api/v1/auth/refresh", json={"refresh_token": premier["refresh_token"]})

        # Le jeton courant, légitime, est mort avec la lignée.
        apres = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
        )
        assert apres.status_code == 401

    async def test_un_jeton_inconnu_est_refuse(self, client: AsyncClient) -> None:
        reponse = await client.post("/api/v1/auth/refresh", json={"refresh_token": "inconnu"})
        assert reponse.status_code == 401


class TestDeconnexion:
    async def test_apres_deconnexion_le_renouvellement_echoue(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        sortie = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": jetons["refresh_token"]}
        )
        assert sortie.status_code == 204

        reponse = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": jetons["refresh_token"]}
        )
        assert reponse.status_code == 401

    async def test_se_deconnecter_deux_fois_ne_produit_pas_d_erreur(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """Le résultat voulu est atteint dans les deux cas : inutile d'échouer."""
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        for _ in range(2):
            reponse = await client.post(
                "/api/v1/auth/logout", json={"refresh_token": jetons["refresh_token"]}
            )
            assert reponse.status_code == 204


class TestMotDePassePropre:
    async def test_le_changement_exige_le_mot_de_passe_actuel(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        reponse = await client.patch(
            "/api/v1/auth/me/password",
            headers=entete(jetons),
            json={"current_password": "pas-le-bon", "new_password": "Nouveau-Secret-2026"},
        )
        assert reponse.status_code == 400
        assert reponse.json()["error"]["code"] == "wrong_password"

    async def test_le_nouveau_mot_de_passe_permet_de_se_reconnecter(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        utilisateur = await fabrique_utilisateur()
        jetons = await connexion(utilisateur.email)
        reponse = await client.patch(
            "/api/v1/auth/me/password",
            headers=entete(jetons),
            json={"current_password": MOT_DE_PASSE, "new_password": "Nouveau-Secret-2026"},
        )
        assert reponse.status_code == 204

        nouvelle = await client.post(
            "/api/v1/auth/login",
            json={"email": utilisateur.email, "password": "Nouveau-Secret-2026"},
        )
        assert nouvelle.status_code == 200
