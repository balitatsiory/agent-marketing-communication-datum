"""Dépendances propres au module Média."""

import httpx

from app.core.downloads import HostResolver, resolve_host


def get_image_link_transport() -> httpx.AsyncBaseTransport | None:
    """Transport du rapatriement par lien. Les tests le remplacent par des faux sites."""
    return None


def get_host_resolver() -> HostResolver:
    """Résolution DNS du rapatriement par lien. Les tests la remplacent."""
    return resolve_host
