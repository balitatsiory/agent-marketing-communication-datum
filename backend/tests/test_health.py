"""Le socle répond-il ?

Ces trois tests ne valident aucune règle métier : ils vérifient que
l'assemblage tient — l'application démarre, la base répond, et une route
inconnue sort dans la bonne enveloppe d'erreur.
"""

from httpx import AsyncClient


async def test_health_repond_ok(client: AsyncClient) -> None:
    reponse = await client.get("/health")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["status"] == "ok"
    assert corps["database"] == "ok"


async def test_racine_redirige_vers_la_documentation(client: AsyncClient) -> None:
    reponse = await client.get("/", follow_redirects=False)
    assert reponse.status_code in (307, 302)
    assert reponse.headers["location"] == "/docs"


async def test_route_inconnue_sort_dans_l_enveloppe(client: AsyncClient) -> None:
    reponse = await client.get("/api/v1/inexistant")
    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "not_found"
