"""Gestion des comptes et attribution des droits.

Deux points méritent l'attention particulière des tests : la frontière entre
`manage_users` et `manage_permissions`, qui est une frontière de sécurité, et
l'archivage, qui doit révoquer les sessions dans la même transaction.
"""

from httpx import AsyncClient

from tests.conftest import entete

MOT_DE_PASSE = "Dev-Mot-De-Passe-2026"


class TestDroitsRequis:
    async def test_sans_droit_la_liste_est_refusee(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        simple = await fabrique_utilisateur()
        jetons = await connexion(simple.email)
        reponse = await client.get("/api/v1/users", headers=entete(jetons))
        assert reponse.status_code == 403
        assert reponse.json()["error"]["code"] == "permission_denied"

    async def test_sans_jeton_c_est_401_et_non_403(self, client: AsyncClient) -> None:
        """La distinction compte : le frontend redirige dans un cas, affiche un
        refus dans l'autre."""
        reponse = await client.get("/api/v1/users")
        assert reponse.status_code == 401

    async def test_manage_users_ne_donne_pas_le_droit_d_attribuer_les_droits(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """C'est la frontière de sécurité qui a motivé la séparation des deux
        droits : qui peut attribuer des droits peut s'octroyer tous les pouvoirs.
        """
        gestionnaire = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons = await connexion(gestionnaire.email)

        liste = await client.get("/api/v1/users", headers=entete(jetons))
        assert liste.status_code == 200

        attribution = await client.put(
            f"/api/v1/users/{cible.id_users}/permissions",
            headers=entete(jetons),
            json={"codes": ["manage_users"]},
        )
        assert attribution.status_code == 403


class TestListeEtLecture:
    async def test_la_liste_est_paginee(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        for _ in range(3):
            await fabrique_utilisateur()
        jetons = await connexion(admin.email)

        reponse = await client.get("/api/v1/users?page=1&size=2", headers=entete(jetons))
        assert reponse.status_code == 200
        corps = reponse.json()
        assert len(corps["items"]) == 2
        assert corps["total"] == 4
        assert corps["pages"] == 2

    async def test_les_comptes_archives_sont_exclus_par_defaut(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        await fabrique_utilisateur(archive=True)
        jetons = await connexion(admin.email)

        defaut = await client.get("/api/v1/users", headers=entete(jetons))
        assert defaut.json()["total"] == 1

        avec = await client.get("/api/v1/users?include_archived=true", headers=entete(jetons))
        assert avec.json()["total"] == 2

    async def test_un_identifiant_inexistant_renvoie_404(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.get("/api/v1/users/999999", headers=entete(jetons))
        assert reponse.status_code == 404


class TestCreation:
    async def test_un_compte_est_cree_avec_l_en_tete_location(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.post(
            "/api/v1/users",
            headers=entete(jetons),
            json={
                "email": "nouvelle@iagora.example.com",
                "password": "Un-Mot-De-Passe-2026",
                "first_name": "Nouvelle",
                "last_name": "Recrue",
            },
        )
        assert reponse.status_code == 201
        assert "Location" in reponse.headers
        assert reponse.json()["is_active"] is True

    async def test_une_adresse_deja_prise_renvoie_409_meme_en_casse_differente(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        existant = await fabrique_utilisateur(email="deja@iagora.example.com")
        jetons = await connexion(admin.email)
        reponse = await client.post(
            "/api/v1/users",
            headers=entete(jetons),
            json={
                "email": existant.email.upper(),
                "password": "Un-Mot-De-Passe-2026",
                "first_name": "Double",
                "last_name": "Compte",
            },
        )
        assert reponse.status_code == 409

    async def test_un_mot_de_passe_trop_court_est_refuse(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.post(
            "/api/v1/users",
            headers=entete(jetons),
            json={
                "email": "court@iagora.example.com",
                "password": "court",
                "first_name": "Trop",
                "last_name": "Court",
            },
        )
        assert reponse.status_code == 422


class TestModification:
    async def test_la_suspension_coupe_l_acces(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """La suspension ne révoque pas les jetons, mais le jeton d'accès cesse
        de donner accès à quoi que ce soit : l'exposition se limite à sa durée
        de vie, et non à celle du jeton de renouvellement."""
        admin = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons_cible = await connexion(cible.email)
        jetons_admin = await connexion(admin.email)

        avant = await client.get("/api/v1/auth/me", headers=entete(jetons_cible))
        assert avant.status_code == 200

        await client.patch(
            f"/api/v1/users/{cible.id_users}",
            headers=entete(jetons_admin),
            json={"is_active": False},
        )

        apres = await client.get("/api/v1/auth/me", headers=entete(jetons_cible))
        assert apres.status_code == 401

    async def test_un_compte_archive_n_est_plus_modifiable(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        archive = await fabrique_utilisateur(archive=True)
        jetons = await connexion(admin.email)
        reponse = await client.patch(
            f"/api/v1/users/{archive.id_users}",
            headers=entete(jetons),
            json={"first_name": "Tentative"},
        )
        assert reponse.status_code == 409


class TestArchivage:
    async def test_l_archivage_revoque_les_sessions(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """« On garde l'histoire, on détruit le pouvoir » : la ligne demeure,
        les sessions cessent dans la même transaction."""
        admin = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons_cible = await connexion(cible.email)
        jetons_admin = await connexion(admin.email)

        reponse = await client.delete(
            f"/api/v1/users/{cible.id_users}", headers=entete(jetons_admin)
        )
        assert reponse.status_code == 204

        renouvellement = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": jetons_cible["refresh_token"]}
        )
        assert renouvellement.status_code == 401

    async def test_le_compte_archive_reste_lisible_par_son_identifiant(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """La paternité des publications passées en dépend."""
        admin = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons = await connexion(admin.email)
        await client.delete(f"/api/v1/users/{cible.id_users}", headers=entete(jetons))

        reponse = await client.get(f"/api/v1/users/{cible.id_users}", headers=entete(jetons))
        assert reponse.status_code == 200
        assert reponse.json()["deleted_at"] is not None

    async def test_on_ne_peut_pas_archiver_son_propre_compte(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.delete(f"/api/v1/users/{admin.id_users}", headers=entete(jetons))
        assert reponse.status_code == 409

    async def test_archiver_deux_fois_renvoie_409(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons = await connexion(admin.email)
        await client.delete(f"/api/v1/users/{cible.id_users}", headers=entete(jetons))
        reponse = await client.delete(f"/api/v1/users/{cible.id_users}", headers=entete(jetons))
        assert reponse.status_code == 409


class TestAttributionDesDroits:
    async def test_les_droits_sont_remplaces_et_non_ajoutes(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """PUT enregistre un ÉTAT : l'écran coche et décoche des cases."""
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        cible = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)

        reponse = await client.put(
            f"/api/v1/users/{cible.id_users}/permissions",
            headers=entete(jetons),
            json={"codes": ["manage_permissions"]},
        )
        assert reponse.status_code == 200
        assert reponse.json() == ["manage_permissions"]

    async def test_retirer_tous_les_droits_est_possible(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        cible = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.put(
            f"/api/v1/users/{cible.id_users}/permissions",
            headers=entete(jetons),
            json={"codes": []},
        )
        assert reponse.json() == []

    async def test_un_droit_retire_puis_redonne_repasse_bien(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """L'unicité partielle doit permettre la réattribution, l'ancienne ligne
        restant archivée au titre de l'historique."""
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        cible = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        url = f"/api/v1/users/{cible.id_users}/permissions"

        await client.put(url, headers=entete(jetons), json={"codes": []})
        reponse = await client.put(url, headers=entete(jetons), json={"codes": ["manage_users"]})
        assert reponse.json() == ["manage_users"]

    async def test_un_code_inconnu_est_refuse(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        cible = await fabrique_utilisateur()
        jetons = await connexion(admin.email)
        reponse = await client.put(
            f"/api/v1/users/{cible.id_users}/permissions",
            headers=entete(jetons),
            json={"codes": ["droit_invente"]},
        )
        assert reponse.status_code == 400
        assert reponse.json()["error"]["code"] == "unknown_permission"

    async def test_la_liste_des_droits_expose_leur_description(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """La description existe pour que l'explication ne soit pas codée en dur
        dans l'interface."""
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)
        reponse = await client.get("/api/v1/permissions", headers=entete(jetons))
        assert reponse.status_code == 200
        droits = reponse.json()
        assert [d["code"] for d in droits] == ["manage_users", "manage_permissions"]
        assert all(d["description"] for d in droits)


class TestMotDePasseParAdministrateur:
    async def test_l_administrateur_change_le_mot_de_passe_sans_courriel(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users"])
        cible = await fabrique_utilisateur()
        jetons = await connexion(admin.email)

        reponse = await client.patch(
            f"/api/v1/users/{cible.id_users}/password",
            headers=entete(jetons),
            json={"password": "Impose-Par-Admin-2026"},
        )
        assert reponse.status_code == 204

        nouvelle = await client.post(
            "/api/v1/auth/login",
            json={"email": cible.email, "password": "Impose-Par-Admin-2026"},
        )
        assert nouvelle.status_code == 200


class TestDroitsPortesParLaLecture:
    """`UserRead` porte les droits du compte.

    L'écran des habilitations affiche un résumé des droits sous chaque nom.
    Les réclamer compte par compte reviendrait à une requête par ligne, d'où
    leur présence dans la lecture elle-même.
    """

    async def test_la_liste_porte_les_droits_de_chaque_compte(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        simple = await fabrique_utilisateur()
        jetons = await connexion(admin.email)

        reponse = await client.get("/api/v1/users", headers=entete(jetons))
        assert reponse.status_code == 200

        par_identifiant = {u["id_users"]: u["permissions"] for u in reponse.json()["items"]}
        assert par_identifiant[admin.id_users] == ["manage_users", "manage_permissions"]
        assert par_identifiant[simple.id_users] == []

    async def test_les_droits_suivent_l_ordre_d_affichage(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """`sort_order` et non l'ordre d'attribution : l'écran coche des cases
        dans un ordre stable, qui ne doit pas dépendre de l'historique."""
        admin = await fabrique_utilisateur(droits=["manage_permissions", "manage_users"])
        jetons = await connexion(admin.email)

        reponse = await client.get(f"/api/v1/users/{admin.id_users}", headers=entete(jetons))
        assert reponse.status_code == 200
        assert reponse.json()["permissions"] == ["manage_users", "manage_permissions"]

    async def test_un_droit_revoque_disparait_de_la_lecture(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """La ligne reste archivée en base ; elle ne doit plus paraître ici."""
        admin = await fabrique_utilisateur(droits=["manage_users", "manage_permissions"])
        cible = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)

        retrait = await client.put(
            f"/api/v1/users/{cible.id_users}/permissions",
            headers=entete(jetons),
            json={"codes": []},
        )
        assert retrait.status_code == 200

        reponse = await client.get(f"/api/v1/users/{cible.id_users}", headers=entete(jetons))
        assert reponse.json()["permissions"] == []

    async def test_un_compte_cree_part_sans_aucun_droit(
        self, client: AsyncClient, fabrique_utilisateur, connexion
    ) -> None:
        """Aucun droit par défaut : un compte neuf ne peut rien, et c'est
        l'administrateur qui ouvre les accès un par un."""
        admin = await fabrique_utilisateur(droits=["manage_users"])
        jetons = await connexion(admin.email)

        reponse = await client.post(
            "/api/v1/users",
            headers=entete(jetons),
            json={
                "email": "nouveau.sans.droit@iagora.example.com",
                "password": MOT_DE_PASSE,
                "first_name": "Nouveau",
                "last_name": "Compte",
            },
        )
        assert reponse.status_code == 201
        assert reponse.json()["permissions"] == []
