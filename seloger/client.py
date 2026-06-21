"""Client HTTP bas niveau pour SeLoger (gestion Datadome, retries, politesse)."""

from __future__ import annotations

import logging
import random
import time

import httpx

from .config import ScraperConfig
from .exceptions import DatadomeBlocked, RateLimited, SelogerError

logger = logging.getLogger("seloger.client")

# Réponses signalant un challenge anti-bot Datadome.
_DATADOME_STATUS = {403}
_RETRYABLE_STATUS = {500, 502, 503, 504}


class SelogerClient:
    """Enveloppe ``httpx.Client`` qui parle à SeLoger comme le navigateur.

    Gère l'injection du cookie/header Datadome, un délai aléatoire entre requêtes
    (politesse) et des retries exponentiels sur erreurs transitoires.

    Utilisable comme context manager :

        with SelogerClient(config) as client:
            html = client.get_list_html(querystring)
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        # Le cookie est optionnel : pour le SSR, Datadome en émet un au premier
        # contact (utile derrière un proxy résidentiel, ex. sur Apify). Il reste
        # nécessaire pour l'API christie/count (header x-datadome-clientid).
        datadome = self.config.datadome_cookie
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.request_timeout,
            proxy=self.config.proxy_url(),
            follow_redirects=True,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
            },
            cookies={"datadome": datadome} if datadome else None,
        )
        self._datadome = datadome
        self._last_request_at = 0.0

    # ----- context manager -----------------------------------------------------

    def __enter__(self) -> "SelogerClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ----- politesse -----------------------------------------------------------

    def _throttle(self) -> None:
        """Respecte un délai aléatoire entre deux requêtes."""
        elapsed = time.monotonic() - self._last_request_at
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_at = time.monotonic()

    # ----- requêtes ------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Exécute une requête avec throttling, retries et détection Datadome."""
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            self._throttle()
            try:
                resp = self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:  # réseau / timeout
                last_exc = exc
                logger.warning("Erreur réseau (tentative %d) : %s", attempt, exc)
                self._backoff(attempt)
                continue

            if resp.status_code in _DATADOME_STATUS or self._looks_blocked(resp):
                raise DatadomeBlocked(
                    f"Bloqué par Datadome ({resp.status_code}) sur {url}. "
                    "Rafraîchis le cookie datadome depuis la session navigateur."
                )
            if resp.status_code == 429:
                logger.warning("429 Too Many Requests (tentative %d)", attempt)
                last_exc = RateLimited(url)
                self._backoff(attempt, base=5.0)
                continue
            if resp.status_code in _RETRYABLE_STATUS:
                logger.warning("%d sur %s (tentative %d)", resp.status_code, url, attempt)
                last_exc = SelogerError(f"HTTP {resp.status_code}")
                self._backoff(attempt)
                continue

            resp.raise_for_status()
            return resp

        raise last_exc or SelogerError(f"Échec de la requête {method} {url}")

    def _backoff(self, attempt: int, base: float = 1.0) -> None:
        time.sleep(base * (2 ** (attempt - 1)) + random.random())

    @staticmethod
    def _looks_blocked(resp: httpx.Response) -> bool:
        """Détecte un challenge Datadome déguisé en 200 (page JS interstitielle)."""
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype and "datadome" in resp.text[:4000].lower():
            return "geo.captcha-delivery" in resp.text or "dd.seloger.com" in resp.text
        return False

    # ----- endpoints de haut niveau --------------------------------------------

    def get_list_html(self, querystring: str) -> str:
        """GET ``/list.htm?<querystring>`` → HTML SSR brut."""
        resp = self._request(
            "GET",
            f"/list.htm?{querystring}",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return resp.text

    def post_christie_count(self, body: dict) -> dict:
        """POST ``/search-bff/christie/count`` → ``{nb, aggregations, ...}``.

        Nécessite un cookie Datadome (réutilisé comme header ``x-datadome-clientid``).
        """
        datadome = self.config.require_datadome()
        resp = self._request(
            "POST",
            "/search-bff/christie/count",
            json=body,
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": self.config.base_url,
                "Referer": f"{self.config.base_url}/list.htm",
                "x-datadome-clientid": datadome,
            },
        )
        return resp.json()
