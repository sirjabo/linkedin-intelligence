"""SSRF protection: validate that a URL does not point to private/internal addresses."""
import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_ALLOWED_SCHEMES = {"http", "https"}


def validate_url_not_private(url: str) -> None:
    """Raise HTTP 422 if the URL resolves to a private or loopback address."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=422, detail=f"URL scheme must be http or https, got: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="URL has no hostname")

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname: {hostname!r}")

    for _family, _type, _proto, _canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for network in _PRIVATE_NETWORKS:
            if ip in network:
                raise HTTPException(
                    status_code=422,
                    detail=f"URL resolves to a private/internal address — not allowed for security reasons",
                )
