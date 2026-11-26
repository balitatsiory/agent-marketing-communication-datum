"""Tests du cycle complet : publication A -> validation B -> correction -> confirmation/publication."""

from httpx import AsyncClient

from tests.conftest import entete


async def test_cycle_validation_et_notifications(
    client: AsyncClient,
    fabrique_utilisateur,  # type: ignore[no-untyped-def]
    connexion,  # type: ignore[no-untyped-def]
) -> None:
    user_a = await fabrique_utilisateur(email="alice@iagora.example.com")
    user_b = await fabrique_utilisateur(email="bob@iagora.example.com")

    headers_a = entete(await connexion(user_a.email))
    headers_b = entete(await connexion(user_b.email))

    # 1. Utilisateur A crée une publication programmée et l'envoie à validation à B.
    res_create = await client.post(
        "/api/v1/publications",
        headers=headers_a,
        json={
            "title": "Lancement Masterclass IA",
            "caption": "Rejoignez-nous jeudi pour notre masterclass ! #DatumAcademy #IA",
            "format_code": "image",
            "platform_codes": ["instagram", "linkedin"],
            "scheduled_at": "2026-12-01T15:30:00Z",
            "id_users_validator": user_b.id_users,
            "submit_for_validation": True,
        },
    )
    assert res_create.status_code == 201, res_create.text
    pub = res_create.json()
    pub_id = pub["id_publications"]
    assert pub["status_code"] == "review"
    assert len(pub["events"]) == 2

    # 2. Utilisateur B reçoit la notification interne pointant vers /publications/{id}.
    res_stats_b = await client.get("/api/v1/notifications/stats", headers=headers_b)
    assert res_stats_b.status_code == 200
    stats_b = res_stats_b.json()
    assert stats_b["total"] == 1
    assert stats_b["unread"] == 1
    assert stats_b["action_required"] == 1
    assert stats_b["internal_count"] == 1
    assert stats_b["platform_count"] == 0
    assert stats_b["by_type"]["validation_request"] == 1
    assert stats_b["by_platform"]["internal"] == 1

    res_list_b = await client.get(
        "/api/v1/notifications",
        headers=headers_b,
        params={"source": "internal", "type": "validation_request"},
    )
    assert res_list_b.status_code == 200
    items_b = res_list_b.json()["items"]
    assert len(items_b) == 1
    notif_b = items_b[0]
    assert notif_b["action_url"] == f"/publications/{pub_id}"
    assert notif_b["requires_action"] is True

    # Filtrer sur platform ne renvoie rien pour le moment.
    res_plat_b = await client.get(
        "/api/v1/notifications",
        headers=headers_b,
        params={"source": "platform"},
    )
    assert res_plat_b.json()["total"] == 0

    # 3. Utilisateur B suggère une correction en commentaire.
    res_changes = await client.post(
        f"/api/v1/publications/{pub_id}/request-changes",
        headers=headers_b,
        json={"comment": "Merci de préciser l'heure en GMT et ajouter le lien d'inscription."},
    )
    assert res_changes.status_code == 200, res_changes.text
    pub_changes = res_changes.json()
    assert pub_changes["status_code"] == "changes_requested"
    assert any(
        ev["kind"] == "changes_requested" and "GMT" in (ev["comment"] or "")
        for ev in pub_changes["events"]
    )

    # La notification de validation de B a été marquée lue automatiquement.
    stats_b_after = (await client.get("/api/v1/notifications/stats", headers=headers_b)).json()
    assert stats_b_after["unread"] == 0
    assert stats_b_after["action_required"] == 0

    # 4. Utilisateur A reçoit la notification de correction suggérée.
    res_list_a = await client.get("/api/v1/notifications", headers=headers_a)
    assert res_list_a.status_code == 200
    items_a = res_list_a.json()["items"]
    assert len(items_a) == 1
    assert items_a[0]["notification_type"] == "correction_suggested"
    assert items_a[0]["action_url"] == f"/publications/{pub_id}"
    assert "GMT" in items_a[0]["body"]

    # 5. Utilisateur A corrige la publication et renvoie à validation.
    res_patch = await client.patch(
        f"/api/v1/publications/{pub_id}",
        headers=headers_a,
        json={
            "caption": "Rejoignez-nous jeudi à 15h30 GMT ! Lien en bio. #DatumAcademy #IA",
        },
    )
    assert res_patch.status_code == 200

    res_resubmit = await client.post(
        f"/api/v1/publications/{pub_id}/submit",
        headers=headers_a,
        json={"comment": "Heure GMT ajoutée."},
    )
    assert res_resubmit.status_code == 200
    assert res_resubmit.json()["status_code"] == "review"

    # B reçoit la nouvelle demande de validation.
    stats_b_resubmit = (await client.get("/api/v1/notifications/stats", headers=headers_b)).json()
    assert stats_b_resubmit["unread"] == 1
    assert stats_b_resubmit["total"] == 2

    # 6. Utilisateur B confirme et publie.
    res_approve = await client.post(
        f"/api/v1/publications/{pub_id}/approve",
        headers=headers_b,
        json={"publish_now": True, "comment": "Parfait, c'est publié !"},
    )
    assert res_approve.status_code == 200
    pub_done = res_approve.json()
    assert pub_done["status_code"] == "published"
    assert pub_done["published_at"] is not None

    # Utilisateur A reçoit la notification de publication (plateforme instagram).
    stats_a_final = (await client.get("/api/v1/notifications/stats", headers=headers_a)).json()
    assert stats_a_final["total"] == 2
    assert stats_a_final["internal_count"] == 1
    assert stats_a_final["platform_count"] == 1
    assert stats_a_final["by_platform"]["instagram"] == 1
    assert stats_a_final["by_type"]["publication_published"] == 1

    # 7. Tout marquer comme lu pour A.
    res_read_all = await client.post("/api/v1/notifications/read-all", headers=headers_a)
    assert res_read_all.status_code == 200
    assert res_read_all.json()["updated"] >= 1
    stats_a_read = (await client.get("/api/v1/notifications/stats", headers=headers_a)).json()
    assert stats_a_read["unread"] == 0
