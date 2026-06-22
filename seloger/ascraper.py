"""API haut niveau **asynchrone** du scraper SeLoger.

Permet de paralléliser :
* les pages d'une recherche (récupérées en parallèle après la 1ʳᵉ) ;
* la récupération du **détail** de nombreuses annonces (le gros gain : 1 requête
  par annonce, exécutées N à la fois).

La concurrence est bornée globalement par ``config.concurrency`` (sémaphore du
client). Exemple :

    async with AsyncSelogerScraper(ScraperConfig(concurrency=12)) as s:
        details = await s.asearch_details(SearchQuery(insee_codes=[750056]), max_pages=2)
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Iterable
from dataclasses import replace

from .aclient import AsyncSelogerClient
from .config import ScraperConfig
from .detail import ListingDetail
from .models import Listing, SearchPage
from .parser import parse_externaldata, parse_listing_detail, parse_search_page
from .query import Range, SearchQuery
from .scraper import HARD_RESULT_CAP

logger = logging.getLogger("seloger.ascraper")

# Plafonds de prix par défaut pour le découpage (loyer mensuel vs prix de vente).
_PRICE_CEILING = {1: 100_000, 2: 100_000_000}  # ProjectType RENT=1, BUY=2


class AsyncSelogerScraper:
    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._client = AsyncSelogerClient(self.config)

    async def __aenter__(self) -> "AsyncSelogerScraper":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ----- comptage / pages ----------------------------------------------------

    async def acount(self, query: SearchQuery) -> int:
        data = await self._client.apost_christie_count(query.to_christie_body())
        return int(data.get("nb", 0))

    # ----- découpage par prix (contourner le plafond de 2500) ------------------

    async def asplit_by_price(
        self, query: SearchQuery, cap: int = HARD_RESULT_CAP
    ) -> list[SearchQuery]:
        """Découpe une recherche en sous-intervalles de prix, chacun ``<= cap``.

        SeLoger plafonne une recherche à ~2500 résultats. En scindant la plage de
        prix (dichotomie guidée par ``count``), on couvre l'intégralité des annonces.
        Retourne la liste des sous-requêtes (une seule si le total tient sous le cap).
        """
        total = await self.acount(query)
        if total <= cap:
            return [query]
        lo = query.price.min if query.price.min is not None else 0
        ceiling = _PRICE_CEILING.get(int(query.project), 100_000_000)
        hi = query.price.max if query.price.max is not None else ceiling
        intervals = await self._split_price(query, lo, hi, cap)
        logger.info(
            "%d annonces > plafond %d : découpé en %d intervalle(s) de prix.",
            total, cap, len(intervals),
        )
        return intervals

    async def _split_price(
        self, query: SearchQuery, lo: int, hi: int, cap: int, depth: int = 0
    ) -> list[SearchQuery]:
        sub = replace(query, price=Range(min=lo or None, max=hi))
        count = await self.acount(sub)
        if count == 0:
            return []
        if count <= cap or hi - lo <= 1 or depth >= 24:
            return [sub]
        mid = (lo + hi) // 2
        left, right = await asyncio.gather(
            self._split_price(query, lo, mid, cap, depth + 1),
            self._split_price(query, mid + 1, hi, cap, depth + 1),
        )
        return left + right

    async def asearch_page(self, query: SearchQuery, page: int = 1) -> SearchPage:
        html = await self._client.aget_list_html(query.to_querystring(page=page))
        return parse_search_page(html)

    async def _apage_listings(self, body: dict, page_num: int, per_page: int) -> list[Listing]:
        data = await self._client.apost_externaldata(
            body, from_=(page_num - 1) * per_page, size=per_page
        )
        listings, _ = parse_externaldata(data)
        return listings

    async def asearch(
        self, query: SearchQuery, max_pages: int | None = None
    ) -> list[Listing]:
        """Récupère les annonces : page 1 (SSR, amorce la session) puis les pages
        suivantes via l'API ``externaldata`` **en parallèle**."""
        first = await self.asearch_page(query, page=1)  # amorce la session Datadome

        per_page = first.pagination.results_per_page or 25
        reachable = min(first.total_count, first.pagination.max_results or HARD_RESULT_CAP)
        last_page = math.ceil(reachable / per_page) if per_page else 1
        if max_pages is not None:
            last_page = min(last_page, max_pages)

        page_lists: list[list[Listing]] = [first.listings]
        if last_page > 1:
            body = query.to_christie_body()
            rest = await asyncio.gather(
                *(self._apage_listings(body, p, per_page) for p in range(2, last_page + 1)),
                return_exceptions=True,
            )
            for r in rest:
                if isinstance(r, list):
                    page_lists.append(r)
                else:
                    logger.warning("Échec d'une page : %s", r)

        seen: set[int] = set()
        listings: list[Listing] = []
        for page_listings in page_lists:
            for listing in page_listings:
                if listing.id not in seen:
                    seen.add(listing.id)
                    listings.append(listing)

        if first.total_count > HARD_RESULT_CAP:
            logger.warning(
                "%d annonces au total mais SeLoger plafonne à %d : affine les filtres.",
                first.total_count, HARD_RESULT_CAP,
            )
        return listings

    # ----- détail (parallèle) --------------------------------------------------

    async def aget_listing(self, url_or_listing: "str | Listing") -> ListingDetail:
        url = url_or_listing.url if isinstance(url_or_listing, Listing) else url_or_listing
        if not url:
            raise ValueError("URL d'annonce manquante.")
        html = await self._client.aget_detail_html(url)
        return parse_listing_detail(html, url=url)

    async def aget_details(
        self, listings: Iterable["str | Listing"]
    ) -> list[ListingDetail]:
        """Récupère le détail de plusieurs annonces **en parallèle** (borné par
        ``config.concurrency``). Les annonces en échec sont ignorées (loggées)."""
        items = list(listings)
        results = await asyncio.gather(
            *(self.aget_listing(item) for item in items),
            return_exceptions=True,
        )
        details: list[ListingDetail] = []
        for item, res in zip(items, results):
            if isinstance(res, ListingDetail):
                details.append(res)
            else:
                ref = item.url if isinstance(item, Listing) else item
                logger.warning("Détail en échec (%s) : %s", ref, res)
        return details

    async def asearch_details(
        self, query: SearchQuery, max_pages: int | None = None
    ) -> list[ListingDetail]:
        """Recherche + détail complet de chaque annonce, le tout parallélisé."""
        listings = await self.asearch(query, max_pages=max_pages)
        logger.info("%d annonces → récupération des détails…", len(listings))
        return await self.aget_details(listings)
