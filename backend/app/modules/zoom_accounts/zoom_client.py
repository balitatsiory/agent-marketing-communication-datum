"""Client HTTP de l'API Zoom.

Deux échanges seulement :

- le **jeton** : `POST https://zoom.us/oauth/token` avec
  `grant_type=account_credentials`, authentifié en « Basic »
  (Client ID : Client Secret). Une application Server-to-Server n'a PAS de
  jeton de renouvellement : quand le jeton d'une heure expire, on en demande un
  autre avec la même requête ;
- les appels à `https://api.zoom.us/v2`, porteurs de ce jeton.

Ce fichier ne connaît ni la base ni l'API IAGORA : il parle à Zoom et traduit
ses refus en `ZoomError`.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.modules.zoom_accounts.constants import ZOOM_TIMEOUT_SECONDS

# Codes d'erreur propres à Zoom que l'on sait expliquer.
ZOOM_CODE_INVALID_TOKEN = 124
ZOOM_CODE_MISSING_SCOPE = 4711


class ZoomError(Exception):
    """Un refus de Zoom, ou une panne sur le chemin."""

    def __init__(self, message: str, status_code: int = 0, zoom_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        self.zoom_code = zoom_code
        super().__init__(message)

    @property
    def is_expired_token(self) -> bool:
        return self.status_code == 401 and self.zoom_code == ZOOM_CODE_INVALID_TOKEN


@dataclass(frozen=True)
class ZoomToken:
    """Jeton d'accès délivré par Zoom."""

    access_token: str
    expires_in: int
    scopes: tuple[str, ...]


class ZoomClient:
    """Appels à Zoom. `transport` permet aux tests de répondre à la place de Zoom."""

    def __init__(
        self,
        oauth_url: str,
        api_base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._oauth_url = oauth_url
        self._api_base_url = api_base_url.rstrip("/")
        self._transport = transport

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=ZOOM_TIMEOUT_SECONDS)

    async def fetch_token(self, account_id: str, client_id: str, client_secret: str) -> ZoomToken:
        """Demande un jeton d'accès Server-to-Server.

        Raises:
            ZoomError: identifiants refusés, application inactive ou Zoom injoignable.
        """
        try:
            async with self._http() as http:
                reponse = await http.post(
                    self._oauth_url,
                    data={"grant_type": "account_credentials", "account_id": account_id},
                    auth=(client_id, client_secret),
                )
        except httpx.HTTPError as erreur:
            raise ZoomError(f"Zoom est injoignable ({type(erreur).__name__}).") from erreur

        corps = _corps_json(reponse)
        if reponse.status_code != 200:
            raison = corps.get("reason") or corps.get("error") or reponse.reason_phrase
            raise ZoomError(f"Zoom refuse de délivrer un jeton : {raison}.", reponse.status_code)

        jeton = corps.get("access_token")
        if not isinstance(jeton, str) or not jeton:
            raise ZoomError("Réponse de Zoom sans jeton d'accès.", reponse.status_code)
        return ZoomToken(
            access_token=jeton,
            expires_in=int(corps.get("expires_in") or 3600),
            scopes=tuple(str(corps.get("scope") or "").split()),
        )

    async def request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: dict[str, str | int] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Appelle l'API Zoom et renvoie son corps JSON.

        Raises:
            ZoomError: réponse en erreur ou Zoom injoignable.
        """
        try:
            async with self._http() as http:
                reponse = await http.request(
                    method,
                    f"{self._api_base_url}{path}",
                    params=params,
                    json=json,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as erreur:
            raise ZoomError(f"Zoom est injoignable ({type(erreur).__name__}).") from erreur

        corps = _corps_json(reponse)
        if reponse.status_code >= 400:
            code = corps.get("code")
            detail = corps.get("message") or reponse.reason_phrase
            # Les erreurs de validation de Zoom détaillent le champ fautif dans
            # `errors` : sans lui, « Validation Failed » ne dit rien.
            champs = "; ".join(
                f"{e.get('field')} : {e.get('message')}"
                for e in corps.get("errors") or []
                if isinstance(e, dict)
            )
            raise ZoomError(
                f"{detail} ({champs})" if champs else str(detail),
                reponse.status_code,
                code if isinstance(code, int) else None,
            )
        return corps


def _corps_json(reponse: httpx.Response) -> dict[str, Any]:
    """Corps JSON de la réponse, ou un dictionnaire vide s'il n'y en a pas."""
    try:
        corps = reponse.json()
    except ValueError:
        return {}
    return corps if isinstance(corps, dict) else {}


def get_zoom_client() -> ZoomClient:
    """Client Zoom construit depuis la configuration (substitué dans les tests)."""
    reglages = get_settings()
    return ZoomClient(reglages.ZOOM_OAUTH_URL, reglages.ZOOM_API_BASE_URL)
