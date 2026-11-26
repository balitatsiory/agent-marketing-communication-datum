"""Téléchargement d'une adresse saisie : ce que le serveur accepte d'appeler.

Ni réseau ni DNS : le transport et le résolveur sont simulés.
"""

import asyncio
from collections.abc import Callable

import httpx
import pytest

from app.core.downloads import DownloadRefusedError, download_public_image

PUBLIC = "93.184.215.14"


def resolving(*addresses: str) -> Callable[[str], object]:
    async def resolve(host: str) -> list[str]:
        return list(addresses)

    return resolve


async def download(
    handler: Callable[[httpx.Request], httpx.Response],
    url: str = "https://images.example.com/logo.png",
    addresses: tuple[str, ...] = (PUBLIC,),
    max_bytes: int = 1000,
    timeout_seconds: float = 5.0,
) -> bytes:
    return await download_public_image(
        url,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        transport=httpx.MockTransport(handler),
        resolve=resolving(*addresses),  # type: ignore[arg-type]
    )


def serve(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"octets")


async def test_download_public_image_connects_to_the_checked_address() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return serve(request)

    content = await download(handler, "https://images.example.com/a%20b.png?v=2")

    assert content == b"octets"
    [request] = requests
    # Le nom ne repasse pas par le DNS, mais reste celui que le certificat doit porter.
    assert str(request.url) == f"https://{PUBLIC}/a%20b.png?v=2"
    assert request.headers["host"] == "images.example.com"
    assert request.extensions["sni_hostname"] == "images.example.com"
    assert request.headers["accept-encoding"] == "identity"


async def test_download_public_image_non_ascii_host_is_sent_encoded() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return serve(request)

    await download(handler, "https://écoles.example.com/logo.png")

    assert requests[0].headers["host"] == "xn--coles-9ra.example.com"


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "0.0.0.0",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.10",
        "169.254.169.254",
        "100.64.0.1",
        "224.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fd00::1",
        "fec0::1",
        "ff0e::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "64:ff9b::7f00:1",
        "2002:a00:1::1",
    ],
)
async def test_download_public_image_internal_address_is_never_called(address: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Une adresse interne a été appelée.")

    with pytest.raises(DownloadRefusedError, match="réseau interne"):
        await download(handler, addresses=(address,))


async def test_download_public_image_one_internal_address_refuses_the_host() -> None:
    with pytest.raises(DownloadRefusedError, match="réseau interne"):
        await download(serve, addresses=(PUBLIC, "10.0.0.1"))


@pytest.mark.parametrize("address", [PUBLIC, "2606:4700::1111", "64:ff9b::5db8:d70e"])
async def test_download_public_image_public_address_is_accepted(address: str) -> None:
    assert await download(serve, addresses=(address,)) == b"octets"


async def test_download_public_image_unreachable_address_tries_the_next_one() -> None:
    called: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request.url.host)
        if ":" in request.url.host:
            return serve(request)
        raise httpx.ConnectError("injoignable", request=request)

    content = await download(handler, addresses=("2606:4700::1111", PUBLIC))

    assert content == b"octets"
    # IPv4 d'abord, quel que soit l'ordre du DNS.
    assert called == [PUBLIC, "2606:4700::1111"]


async def test_download_public_image_unreachable_site_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("injoignable", request=request)

    with pytest.raises(DownloadRefusedError, match="injoignable"):
        await download(handler)


async def test_download_public_image_unknown_host_is_refused() -> None:
    async def resolve(host: str) -> list[str]:
        raise OSError("nom inconnu")

    with pytest.raises(DownloadRefusedError, match="introuvable"):
        await download_public_image(
            "https://absent.example.com/logo.png",
            max_bytes=10,
            timeout_seconds=5.0,
            resolve=resolve,
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(302, headers={"location": "https://10.0.0.1/"}), "renvoie vers une autre"),
        (httpx.Response(403), "403"),
        (httpx.Response(200, headers={"content-encoding": "gzip"}), "compressée"),
        (httpx.Response(200, content=b"x" * 1001), "trop lourde"),
    ],
    ids=["redirection", "refus-du-site", "reponse-compressee", "trop-lourde"],
)
async def test_download_public_image_unusable_response_is_refused(
    response: httpx.Response, message: str
) -> None:
    with pytest.raises(DownloadRefusedError, match=message):
        await download(lambda request: response)


async def test_download_public_image_slow_site_is_interrupted() -> None:
    async def resolve(host: str) -> list[str]:
        await asyncio.sleep(5)
        return [PUBLIC]

    with pytest.raises(DownloadRefusedError, match="trop de temps"):
        await download_public_image(
            "https://lent.example.com/logo.png",
            max_bytes=10,
            timeout_seconds=0.05,
            resolve=resolve,
        )
