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

from .aclient import AsyncSelogerClient
from .config import ScraperConfig
from .detail import ListingDetail
from .models import Listing, SearchPage
from .parser import parse_listing_detail, parse_search_page
from .query import SearchQuery
from .scraper import HARD_RESULT_CAP

logger = logging.getLogger("seloger.ascraper")


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

    async def asearch_page(self, query: SearchQuery, page: int = 1) -> SearchPage:
        html = await self._client.aget_list_html(query.to_querystring(page=page))
        return parse_search_page(html)

    async def asearch(
        self, query: SearchQuery, max_pages: int | None = None
    ) -> list[Listing]:
        """Récupère les annonces : page 1 d'abord, puis les autres **en parallèle**."""
        first = await self.asearch_page(query, page=1)

        per_page = first.pagination.results_per_page or 25
        reachable = min(first.total_count, first.pagination.max_results or HARD_RESULT_CAP)
        last_page = math.ceil(reachable / per_page) if per_page else 1
        if max_pages is not None:
            last_page = min(last_page, max_pages)

        pages = [first]
        if last_page > 1:
            rest = await asyncio.gather(
                *(self.asearch_page(query, page=p) for p in range(2, last_page + 1)),
                return_exceptions=True,
            )
            for p in rest:
                if isinstance(p, SearchPage):
                    pages.append(p)
                else:
                    logger.warning("Échec d'une page : %s", p)

        seen: set[int] = set()
        listings: list[Listing] = []
        for page in pages:
            for listing in page.listings:
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
