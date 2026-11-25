"""Un Zoom de laboratoire : il répond aux appels à la place de zoom.us.

Il reproduit juste ce que le code attend : délivrance du jeton, liste, fiche et
création d'une réunion, inscrits — et les refus utiles aux tests.
"""

import base64
import json
from typing import Any
from urllib.parse import parse_qs

import httpx

OAUTH_URL = "https://zoom.test/oauth/token"
API_URL = "https://api.zoom.test/v2"

CLIENT_ID = "client-essai"
CLIENT_SECRET = "secret-zoom-essai"
HOTE = "hote@iagora.example.com"
DROITS = (
    "meeting:read:list_meetings:admin meeting:read:meeting:admin "
    "meeting:write:meeting:admin meeting:write:registrant:admin "
    "meeting:read:list_registrants:admin"
)


class FauxZoom:
    def __init__(self) -> None:
        self.scopes = DROITS
        self.jetons_delivres = 0
        self.refuser_le_prochain_jeton = False
        self.reunions: dict[int, dict[str, Any]] = {}
        self.inscrits: dict[int, list[dict[str, Any]]] = {}
        self.appels: list[tuple[str, str]] = []
        self.corps: list[dict[str, Any]] = []
        self.refus: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
        self._numero = 85058225147

    def ajouter_reunion(self, **champs: Any) -> dict[str, Any]:
        identifiant = champs.pop("id", self._numero)
        self._numero = max(self._numero, identifiant) + 1
        reunion = {
            "id": identifiant,
            "uuid": f"uuid-{identifiant}",
            "topic": "Réunion d'essai",
            "type": 2,
            "start_time": "2031-03-04T15:00:00Z",
            "duration": 60,
            "timezone": "UTC",
            "join_url": f"https://zoom.test/j/{identifiant}",
            "start_url": f"https://zoom.test/s/{identifiant}?zak=secret",
            "password": "motdepasse",
            "settings": {"approval_type": 2},
            **champs,
        }
        self.reunions[identifiant] = reunion
        return reunion

    def repondre(self, requete: httpx.Request) -> httpx.Response:
        if str(requete.url).startswith(OAUTH_URL):
            return self._jeton(requete)
        chemin = requete.url.path.removeprefix("/v2")
        self.appels.append((requete.method, chemin))
        corps = json.loads(requete.content) if requete.content else {}
        if corps:
            self.corps.append(corps)
        if self.refuser_le_prochain_jeton:
            self.refuser_le_prochain_jeton = False
            return httpx.Response(401, json={"code": 124, "message": "Access token is expired."})
        if (requete.method, chemin) in self.refus:
            statut, reponse = self.refus[(requete.method, chemin)]
            return httpx.Response(statut, json=reponse)

        morceaux = chemin.strip("/").split("/")
        if morceaux[0] == "users":
            return self._reunions_de(requete, morceaux[1], corps)
        reunion = self.reunions.get(int(morceaux[1]))
        if reunion is None:
            return httpx.Response(404, json={"code": 3001, "message": "Meeting does not exist."})
        if len(morceaux) == 2:
            return httpx.Response(200, json=reunion)
        return self._inscrits(requete, reunion, corps)

    def _jeton(self, requete: httpx.Request) -> httpx.Response:
        attendu = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        formulaire = parse_qs(requete.content.decode())
        if requete.headers.get("Authorization") != f"Basic {attendu}":
            return httpx.Response(
                400,
                json={"reason": "Invalid client_id or client_secret", "error": "invalid_client"},
            )
        assert formulaire["grant_type"] == ["account_credentials"]
        assert formulaire["account_id"]
        self.jetons_delivres += 1
        return httpx.Response(
            200,
            json={
                "access_token": f"jeton-{self.jetons_delivres}",
                "token_type": "bearer",
                "expires_in": 3600,
                "scope": self.scopes,
            },
        )

    def _reunions_de(
        self, requete: httpx.Request, hote: str, corps: dict[str, Any]
    ) -> httpx.Response:
        if hote != HOTE:
            return httpx.Response(404, json={"code": 1001, "message": "User does not exist."})
        if requete.method == "POST":
            reglages = corps.get("settings", {})
            reunion = self.ajouter_reunion(
                **{k: v for k, v in corps.items() if k != "settings"}, settings=reglages
            )
            if reglages.get("approval_type") in (0, 1):
                reunion["registration_url"] = f"https://zoom.test/register/{reunion['id']}"
            return httpx.Response(201, json=reunion)
        genre = requete.url.params.get("type")
        liste = list(self.reunions.values()) if genre == "scheduled" else []
        return httpx.Response(200, json={"meetings": liste, "next_page_token": ""})

    def _inscrits(
        self, requete: httpx.Request, reunion: dict[str, Any], corps: dict[str, Any]
    ) -> httpx.Response:
        liste = self.inscrits.setdefault(reunion["id"], [])
        if requete.method == "POST":
            identifiant = f"inscrit-{len(liste) + 1}"
            liste.append({"id": identifiant, "status": "approved", **corps})
            return httpx.Response(
                201,
                json={
                    "registrant_id": identifiant,
                    "join_url": f"https://zoom.test/w/{identifiant}",
                },
            )
        statut = requete.url.params.get("status")
        return httpx.Response(
            200, json={"registrants": [i for i in liste if i["status"] == statut]}
        )
