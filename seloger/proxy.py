"""Configuration d'un proxy HTTP (calqué sur le repo ``lbc``)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Proxy:
    """Proxy HTTP, avec authentification optionnelle.

        Proxy(host="1.2.3.4", port=8080, username="u", password="p")

    Attributes:
        host: hôte du proxy.
        port: port du proxy.
        username / password: identifiants optionnels (proxy authentifié).
    """

    host: str
    port: str | int
    username: str | None = None
    password: str | None = None

    @property
    def url(self) -> str:
        """URL ``http://[user:pass@]host:port`` utilisable par httpx/requests."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

    @classmethod
    def from_url(cls, url: str) -> "Proxy":
        """Construit un :class:`Proxy` depuis une URL ``http://user:pass@host:port``."""
        from urllib.parse import urlparse

        parsed = urlparse(url if "://" in url else f"http://{url}")
        if not parsed.hostname or not parsed.port:
            raise ValueError(f"URL de proxy invalide : {url!r}")
        return cls(
            host=parsed.hostname,
            port=parsed.port,
            username=parsed.username,
            password=parsed.password,
        )
