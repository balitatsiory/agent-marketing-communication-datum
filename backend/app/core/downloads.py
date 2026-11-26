"""Téléchargement borné d'une image distante.

Deux usages, deux niveaux de confiance :

- `download_image` n'appelle que les hôtes que l'appelant autorise : c'est celui
  des imports, dont les adresses viennent d'un fichier ou d'un site connu.
- `download_public_image` appelle l'hôte qu'un utilisateur a saisi. Il n'accepte
  que des adresses IP publiques, pour que personne ne fasse interroger par le
  serveur sa propre machine, le réseau interne ou les métadonnées de l'hébergeur.

Les deux exigent le HTTPS, ne suivent aucune redirection et interrompent la
lecture dès le plafond franchi. Vérifier que les octets reçus sont une image
reste à l'appelant.
"""

import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from urllib.parse import urlsplit

import httpx

HostResolver = Callable[[str], Awaitable[list[str]]]

# Préfixe NAT64 : les 32 derniers bits désignent une adresse IPv4, que la
# passerelle joindra, fût-elle interne. Python juge pourtant ces adresses publiques.
_NAT64_PREFIX = ipaddress.IPv6Network("64:ff9b::/96")
# Certains sites refusent un client qui ne se nomme pas. La compression est
# écartée : quelques kilo-octets décompressés pourraient dépasser tout plafond.
_PUBLIC_HEADERS = {"User-Agent": "IAGORA/1.0", "Accept-Encoding": "identity"}


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
    async with (
        httpx.AsyncClient(
            transport=transport, timeout=timeout_seconds, follow_redirects=False
        ) as http,
        http.stream("GET", url) as response,
    ):
        if response.status_code != 200:
            raise DownloadRefusedError(f"Le site répond {response.status_code}.")
        return await _read_bounded(response.aiter_bytes(), max_bytes)


async def resolve_host(host: str) -> list[str]:
    """Adresses IP d'un nom d'hôte, selon le résolveur du système.

    Raises:
        OSError: nom inconnu.
    """
    records = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [str(record[4][0]) for record in records]


async def download_public_image(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None = None,
    resolve: HostResolver = resolve_host,
) -> bytes:
    """Octets servis à une adresse HTTPS saisie par un utilisateur.

    La connexion vise l'adresse IP qui vient d'être contrôlée, et non le nom : un
    second appel au DNS pourrait répondre une adresse interne. Le certificat reste
    vérifié contre le nom demandé.

    Raises:
        DownloadRefusedError: adresse refusée ou injoignable, réponse autre que 200,
            fichier trop lourd ou site trop lent.
    """
    target = _parse_public_url(url)
    try:
        # Les délais de httpx valent par opération : un site qui distille ses octets
        # les respecterait indéfiniment.
        async with asyncio.timeout(timeout_seconds):
            addresses = await _resolve_public_addresses(target.host, resolve)
            return await _fetch_first_reachable(
                target, addresses, max_bytes, timeout_seconds, transport
            )
    except (TimeoutError, httpx.TimeoutException) as error:
        raise DownloadRefusedError("Le site met trop de temps à répondre.") from error
    except httpx.HTTPError as error:
        raise DownloadRefusedError("Le site est injoignable ou la réponse est coupée.") from error


def _parse_public_url(url: str) -> httpx.URL:
    # Un seul analyseur, celui qui enverra la requête : deux lectures différentes
    # d'une même adresse permettraient de contourner le contrôle.
    try:
        target = httpx.URL(url)
    except httpx.InvalidURL as error:
        raise DownloadRefusedError("Cette adresse n'est pas valide.") from error
    if target.scheme != "https" or not target.host:
        raise DownloadRefusedError("L'adresse doit commencer par « https:// ».")
    if target.userinfo:
        raise DownloadRefusedError("L'adresse ne doit contenir ni identifiant ni mot de passe.")
    if target.port is not None:
        raise DownloadRefusedError("L'adresse ne doit pas désigner un autre port que le 443.")
    return target


async def _resolve_public_addresses(host: str, resolve: HostResolver) -> list[str]:
    try:
        addresses = await resolve(host)
    except (OSError, UnicodeError) as error:
        raise DownloadRefusedError("Site introuvable : vérifiez le nom dans l'adresse.") from error
    if not addresses:
        raise DownloadRefusedError("Site introuvable : vérifiez le nom dans l'adresse.")
    # Une seule adresse interne suffit à refuser : le système pourrait la choisir.
    if not all(_is_public_address(address) for address in addresses):
        raise DownloadRefusedError("Cette adresse désigne un réseau interne : elle est refusée.")
    # IPv4 d'abord : beaucoup de postes annoncent de l'IPv6 sans pouvoir l'emprunter.
    return sorted(dict.fromkeys(addresses), key=lambda address: ":" in address)


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = ip.ipv4_mapped or ip.sixtofour
        if ip in _NAT64_PREFIX:
            embedded = ipaddress.IPv4Address(ip.packed[-4:])
        if embedded is not None:
            return _is_public_address(str(embedded))
        if ip.is_site_local:
            return False
    return ip.is_global and not ip.is_multicast


async def _fetch_first_reachable(
    target: httpx.URL,
    addresses: Sequence[str],
    max_bytes: int,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None,
) -> bytes:
    host = target.raw_host.decode("ascii")
    host_header = f"[{host}]" if ":" in host else host
    # trust_env=False : un mandataire déclaré dans l'environnement résoudrait
    # lui-même les noms.
    async with httpx.AsyncClient(
        transport=transport, timeout=timeout_seconds, follow_redirects=False, trust_env=False
    ) as http:
        for position, address in enumerate(addresses, start=1):
            try:
                async with http.stream(
                    "GET",
                    target.copy_with(host=address),
                    headers={**_PUBLIC_HEADERS, "Host": host_header},
                    extensions={"sni_hostname": host},
                ) as response:
                    if response.is_redirect:
                        raise DownloadRefusedError(
                            "Cette adresse renvoie vers une autre : collez l'adresse directe "
                            "de l'image."
                        )
                    if response.status_code != 200:
                        raise DownloadRefusedError(f"Le site répond {response.status_code}.")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise DownloadRefusedError("Le site envoie une réponse compressée.")
                    return await _read_bounded(response.aiter_bytes(), max_bytes)
            except httpx.ConnectError:
                if position == len(addresses):
                    raise
    raise DownloadRefusedError("Le site est injoignable.")


async def _read_bounded(chunks: AsyncIterator[bytes], max_bytes: int) -> bytes:
    received = bytearray()
    async for chunk in chunks:
        received.extend(chunk)
        if len(received) > max_bytes:
            raise DownloadRefusedError("Image trop lourde.")
    return bytes(received)
