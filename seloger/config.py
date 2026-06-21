"""Configuration du scraper SeLoger."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .proxy import Proxy

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.seloger.com"
PHOTO_CDN = "https://v.seloger.com"


@dataclass(slots=True)
class ScraperConfig:
    """Paramètres d'exécution du scraper.

    Le couple anti-bot Datadome est l'élément critique : la valeur du cookie
    ``datadome`` sert à la fois de cookie ET de header ``x-datadome-clientid``.
    Récupère-la depuis une session navigateur loggée (cf. RESEARCH.md) puis
    fournis-la ici ou via la variable d'environnement ``SELOGER_DATADOME``.

    Attributes:
        datadome_cookie: valeur du cookie ``datadome`` (~128 caractères).
        user_agent: doit rester cohérent avec la session ayant émis le cookie.
        base_url: racine du site.
        request_timeout: timeout HTTP en secondes.
        max_retries: tentatives sur erreur transitoire (5xx, 429).
        min_delay / max_delay: bornes du délai aléatoire entre requêtes (politesse).
        proxy: proxy HTTP optionnel — instance :class:`Proxy`, URL string, ou via
            la variable d'environnement ``SELOGER_PROXY``. ⚠️ changer d'IP via un
            proxy peut invalider le cookie Datadome (lié à la session/IP d'origine).
    """

    datadome_cookie: str | None = field(
        default_factory=lambda: os.environ.get("SELOGER_DATADOME")
    )
    user_agent: str = DEFAULT_USER_AGENT
    base_url: str = BASE_URL
    request_timeout: float = 20.0
    max_retries: int = 3
    min_delay: float = 1.0
    max_delay: float = 3.0
    proxy: Proxy | str | None = None

    def __post_init__(self) -> None:
        if self.proxy is None:
            env_proxy = os.environ.get("SELOGER_PROXY")
            if env_proxy:
                self.proxy = env_proxy

    def proxy_url(self) -> str | None:
        """URL du proxy (ou ``None``), quel que soit le type fourni."""
        if self.proxy is None:
            return None
        if isinstance(self.proxy, Proxy):
            return self.proxy.url
        return Proxy.from_url(self.proxy).url

    def require_datadome(self) -> str:
        """Retourne le cookie datadome ou lève une erreur explicite."""
        if not self.datadome_cookie:
            raise ValueError(
                "Cookie Datadome manquant. Renseigne ScraperConfig.datadome_cookie "
                "ou la variable d'environnement SELOGER_DATADOME (valeur récupérée "
                "depuis une session navigateur loggée)."
            )
        return self.datadome_cookie
