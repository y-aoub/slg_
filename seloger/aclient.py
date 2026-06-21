"""Client HTTP **asynchrone** pour SeLoger (parallélisation bornée).

Miroir async de :class:`~seloger.client.SelogerClient`. La concurrence est
limitée par un sémaphore (``config.concurrency``) : tu peux lancer des centaines
de récupérations de détail, seules N s'exécutent simultanément.
"""

from __future__ import annotations

import asyncio
import logging
import random

import httpx

from .client import _DATADOME_STATUS, _RETRYABLE_STATUS, SelogerClient
from .config import ScraperConfig
from .exceptions import DatadomeBlocked, ListingUnavailable, RateLimited, SelogerError

logger = logging.getLogger("seloger.aclient")


class AsyncSelogerClient:
    """Enveloppe ``httpx.AsyncClient`` avec Datadome, retries et sémaphore.

        async with AsyncSelogerClient(config) as client:
            html = await client.aget_detail_html(url)
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        datadome = self.config.datadome_cookie
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.request_timeout,
            proxy=self.config.proxy_url(),
            follow_redirects=True,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            cookies={"datadome": datadome} if datadome else None,
        )
        self._datadome = datadome
        self._sem = asyncio.Semaphore(max(1, self.config.concurrency))

    # ----- context manager -----------------------------------------------------

    async def __aenter__(self) -> "AsyncSelogerClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ----- requêtes ------------------------------------------------------------

    async def _arequest(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            async with self._sem:
                # léger jitter pour lisser les rafales concurrentes
                await asyncio.sleep(random.uniform(0, self.config.min_delay))
                try:
                    resp = await self._client.request(method, url, **kwargs)
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning("Erreur réseau (tentative %d) : %s", attempt, exc)
                    await asyncio.sleep(2 ** (attempt - 1) + random.random())
                    continue

            if resp.status_code in _DATADOME_STATUS or SelogerClient._looks_blocked(resp):
                # Souvent transitoire : le cookie Datadome posé par les requêtes
                # réussies est réutilisé (jar partagé) → on retente avec backoff.
                last_exc = DatadomeBlocked(
                    f"Bloqué par Datadome ({resp.status_code}) sur {url}."
                )
                await asyncio.sleep(1.5 * (2 ** (attempt - 1)) + random.random())
                continue
            if resp.status_code == 429:
                last_exc = RateLimited(url)
                await asyncio.sleep(5 * (2 ** (attempt - 1)) + random.random())
                continue
            if resp.status_code in _RETRYABLE_STATUS:
                last_exc = SelogerError(f"HTTP {resp.status_code}")
                await asyncio.sleep(2 ** (attempt - 1) + random.random())
                continue
            if resp.status_code in (404, 410):
                raise ListingUnavailable(f"Annonce indisponible ({resp.status_code}) : {url}")

            resp.raise_for_status()
            return resp

        raise last_exc or SelogerError(f"Échec de la requête {method} {url}")

    # ----- endpoints -----------------------------------------------------------

    async def aget_list_html(self, querystring: str) -> str:
        resp = await self._arequest(
            "GET", f"/list.htm?{querystring}",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return resp.text

    async def aget_detail_html(self, url: str) -> str:
        resp = await self._arequest(
            "GET", url, headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return resp.text

    async def apost_christie_count(self, body: dict) -> dict:
        datadome = self.config.require_datadome()
        resp = await self._arequest(
            "POST", "/search-bff/christie/count", json=body,
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": self.config.base_url,
                "Referer": f"{self.config.base_url}/list.htm",
                "x-datadome-clientid": datadome,
            },
        )
        return resp.json()
