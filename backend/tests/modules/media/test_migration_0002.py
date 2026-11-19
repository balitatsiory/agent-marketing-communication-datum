"""Ce que la migration 0002 garantit, vérifié dans la base.

Comme pour la 0001, ces tests n'empruntent aucun modèle : ils interrogent le
schéma directement. Une contrainte oubliée dans la migration ne serait pas
rattrapée par l'application, puisque c'est la base qui doit l'imposer.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

INSERTION_MEDIA = text(
    """
    INSERT INTO media (storage_key, file_type, source, display_name, size_bytes,
                       width, height, video_duration_seconds)
    VALUES (:cle, :type, :source, 'Essai', :poids, :largeur, :hauteur, :duree)
    RETURNING id_media
    """
)


async def creer_media(
    session: AsyncSession,
    cle: str,
    *,
    type_fichier: str = "image/png",
    source: str = "upload",
    poids: int = 1024,
    largeur: int | None = 800,
    hauteur: int | None = 600,
    duree: int | None = None,
) -> int:
    resultat = await session.execute(
        INSERTION_MEDIA,
        {
            "cle": cle,
            "type": type_fichier,
            "source": source,
            "poids": poids,
            "largeur": largeur,
            "hauteur": hauteur,
            "duree": duree,
        },
    )
    return int(resultat.scalar_one())


async def id_plateforme(session: AsyncSession, code: str = "facebook") -> int:
    resultat = await session.execute(
        text("SELECT id_social_platforms FROM social_platforms WHERE code = :c"), {"c": code}
    )
    return int(resultat.scalar_one())


class TestSchema:
    async def test_les_cinq_tables_existent(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('social_platforms', 'media', 'media_variants',
                                     'media_reference_natures', 'media_references')
                """
            )
        )
        assert len(resultat.scalars().all()) == 5

    async def test_les_nouvelles_tables_sont_commentees(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                """
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                  AND c.relname IN ('social_platforms', 'media', 'media_variants',
                                    'media_reference_natures', 'media_references')
                  AND obj_description(c.oid) IS NULL
                """
            )
        )
        assert resultat.scalars().all() == []

    async def test_chaque_table_a_son_declencheur_updated_at(self, session: AsyncSession) -> None:
        """Sans lui, une modification faite directement en base laisserait
        updated_at figé à la date de création."""
        resultat = await session.execute(
            text(
                """
                SELECT event_object_table FROM information_schema.triggers
                WHERE trigger_name LIKE 'trg_%_updated_at'
                  AND event_object_table IN ('social_platforms', 'media', 'media_variants',
                                             'media_reference_natures', 'media_references')
                """
            )
        )
        assert len(set(resultat.scalars().all())) == 5


class TestAmorces:
    async def test_les_cinq_natures_sont_semees_dans_l_ordre(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text("SELECT code FROM media_reference_natures ORDER BY sort_order")
        )
        assert resultat.scalars().all() == ["logo", "personne", "lieu", "objet", "fond"]

    async def test_les_plateformes_sont_semees_desactivees_et_sans_api(
        self, session: AsyncSession
    ) -> None:
        """Une version d'API se vérifie dans la documentation du réseau : la
        migration sème les codes, le module 07 renseignera le reste."""
        resultat = await session.execute(
            text(
                """
                SELECT code, is_enabled, api_version IS NULL
                FROM social_platforms ORDER BY sort_order
                """
            )
        )
        lignes = resultat.all()
        assert [ligne[0] for ligne in lignes] == ["facebook", "instagram", "linkedin", "tiktok"]
        assert all(ligne[1] is False for ligne in lignes)
        assert all(ligne[2] is True for ligne in lignes)

    async def test_les_trois_droits_du_module_sont_semes(self, session: AsyncSession) -> None:
        resultat = await session.execute(
            text(
                "SELECT code FROM permissions WHERE sort_order BETWEEN 300 AND 399 "
                "ORDER BY sort_order"
            )
        )
        assert resultat.scalars().all() == [
            "manage_media",
            "manage_media_reference",
            "purge_media",
        ]


class TestContraintesSurMedia:
    async def test_deux_lignes_ne_peuvent_pas_designer_le_meme_objet(
        self, session: AsyncSession
    ) -> None:
        await creer_media(session, "stockage/a.png")
        with pytest.raises(IntegrityError):
            await creer_media(session, "stockage/a.png")

    async def test_une_origine_inconnue_est_refusee(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await creer_media(session, "stockage/b.png", source="importe")

    async def test_un_poids_nul_est_refuse(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await creer_media(session, "stockage/c.png", poids=0)

    async def test_une_largeur_sans_hauteur_est_refusee(self, session: AsyncSession) -> None:
        """Une dimension seule ne permet ni d'afficher ni de recadrer."""
        with pytest.raises(IntegrityError):
            await creer_media(session, "stockage/d.png", largeur=800, hauteur=None)

    async def test_un_fichier_sans_dimensions_est_accepte(self, session: AsyncSession) -> None:
        """Un document PDF n'a pas de largeur."""
        id_media = await creer_media(
            session,
            "stockage/e.pdf",
            type_fichier="application/pdf",
            largeur=None,
            hauteur=None,
        )
        assert id_media > 0

    async def test_une_duree_sur_une_image_est_refusee(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await creer_media(session, "stockage/f.png", duree=30)

    async def test_une_duree_sur_une_video_est_acceptee(self, session: AsyncSession) -> None:
        id_media = await creer_media(session, "stockage/g.mp4", type_fichier="video/mp4", duree=30)
        assert id_media > 0


class TestContraintesSurLesVariantes:
    async def test_une_seule_variante_par_media_et_par_plateforme(
        self, session: AsyncSession
    ) -> None:
        id_media = await creer_media(session, "stockage/h.png")
        id_plate = await id_plateforme(session)
        insertion = text(
            """
            INSERT INTO media_variants (id_media, id_social_platforms, storage_key,
                                        file_type, size_bytes, width, height)
            VALUES (:m, :p, :cle, 'image/jpeg', 2048, 1080, 1080)
            """
        )
        await session.execute(insertion, {"m": id_media, "p": id_plate, "cle": "var/1.jpg"})
        with pytest.raises(IntegrityError):
            await session.execute(insertion, {"m": id_media, "p": id_plate, "cle": "var/2.jpg"})

    async def test_une_variante_video_est_refusee(self, session: AsyncSession) -> None:
        """IAGORA ne réencode pas les vidéos : la contrainte le dit en base."""
        id_media = await creer_media(session, "stockage/i.mp4", type_fichier="video/mp4")
        id_plate = await id_plateforme(session)
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO media_variants (id_media, id_social_platforms, storage_key,
                                                file_type, size_bytes, width, height)
                    VALUES (:m, :p, 'var/3.mp4', 'video/mp4', 2048, 1080, 1080)
                    """
                ),
                {"m": id_media, "p": id_plate},
            )


class TestContraintesSurLesReferences:
    async def test_un_media_n_est_reference_qu_une_fois(self, session: AsyncSession) -> None:
        id_media = await creer_media(session, "stockage/j.png")
        insertion = text(
            """
            INSERT INTO media_references (id_media, id_media_reference_natures, label)
            SELECT :m, id_media_reference_natures, :lib
            FROM media_reference_natures WHERE code = 'logo'
            """
        )
        await session.execute(insertion, {"m": id_media, "lib": "Logo DATUM"})
        with pytest.raises(IntegrityError):
            await session.execute(insertion, {"m": id_media, "lib": "Logo bis"})

    async def test_une_reference_archivee_laisse_redeclarer_le_media(
        self, session: AsyncSession
    ) -> None:
        """L'unicité est partielle : sinon une erreur de saisie archivée
        interdirait à jamais de déclarer ce média."""
        id_media = await creer_media(session, "stockage/k.png")
        insertion = text(
            """
            INSERT INTO media_references (id_media, id_media_reference_natures, label)
            SELECT :m, id_media_reference_natures, :lib
            FROM media_reference_natures WHERE code = 'logo'
            """
        )
        await session.execute(insertion, {"m": id_media, "lib": "Premiere"})
        await session.execute(
            text("UPDATE media_references SET deleted_at = now() WHERE id_media = :m"),
            {"m": id_media},
        )
        await session.execute(insertion, {"m": id_media, "lib": "Seconde"})

        resultat = await session.execute(
            text("SELECT count(*) FROM media_references WHERE id_media = :m"), {"m": id_media}
        )
        assert resultat.scalar_one() == 2


class TestContraintesSurLesPlateformes:
    async def test_une_fenetre_de_reponse_sans_reponse_automatisee_est_refusee(
        self, session: AsyncSession
    ) -> None:
        """Validé le 21 octobre : une durée sans objet n'a pas de sens."""
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO social_platforms (code, label, sort_order,
                                                  allows_automated_message_reply,
                                                  message_response_window_hours)
                    VALUES ('essai', 'Essai', 90, false, 24)
                    """
                )
            )

    async def test_deux_reseaux_ne_partagent_pas_un_code(self, session: AsyncSession) -> None:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO social_platforms (code, label, sort_order) "
                    "VALUES ('facebook', 'Doublon', 99)"
                )
            )
