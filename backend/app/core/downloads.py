"""Téléchargement borné d'une image distante, depuis des hôtes nommés seulement.

Le serveur n'appelle qu'en HTTPS les hôtes que l'appelant autorise, ne suit
aucune redirection et interrompt la lecture dès le plafond franchi : un fichier
d'import ne doit pouvoir ni faire appeler une adresse quelconque, ni saturer la
mémoire. Vérifier que les octets reçus sont une image reste à l'appelant.
"""

from collections.abc import Sequence
from urllib.parse import urlsplit

import httpx


class DownloadRefusedError(Exception):
    """Fichier qu'on ne rapatrie pas ; le message est affiché tel quel."""


async def download_image(
    url: str,
    *,
    allowed_hosts: Sequence[str],
    max_bytes: int,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Octets servis à cette adresse.

    Le premier hôte autorisé est celui que le message de refus nomme.

    Raises:
        DownloadRefusedError: hôte non autorisé, réponse autre que 200 ou fichier trop lourd.
        httpx.HTTPError: panne réseau.
    """
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in allowed_hosts:
        raise DownloadRefusedError(f"Adresse hors du site {allowed_hosts[0]}.")
    received = bytearray()
    async with (
        httpx.AsyncClient(
            transport=transport, timeout=timeout_seconds, follow_redirects=False
        ) as http,
        http.stream("GET", url) as response,
    ):
        if response.status_code != 200:
            raise DownloadRefusedError(f"Le site répond {response.status_code}.")
        async for chunk in response.aiter_bytes():
            received.extend(chunk)
            if len(received) > max_bytes:
                raise DownloadRefusedError("Image trop lourde.")
    return bytes(received)
