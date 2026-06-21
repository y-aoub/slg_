"""API haut niveau du scraper SeLoger."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator

from .client import SelogerClient
from .config import ScraperConfig
from .detail import ListingDetail
from .models import Listing, SearchPage
from .parser import parse_listing_detail, parse_search_page
from .query import SearchQuery

logger = logging.getLogger("seloger.scraper")

# Plafond imposé par SeLoger (navigation.pagination.maxResults).
HARD_RESULT_CAP = 2500


class SelogerScraper:
    """Point d'entrée principal.

        scraper = SelogerScraper(ScraperConfig(datadome_cookie="..."))
        query = SearchQuery(insee_codes=[750056])
        print(scraper.count(query))
        for listing in scraper.iter_listings(query, max_pages=4):
            ...
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._client = SelogerClient(self.config)

    def __enter__(self) -> "SelogerScraper":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ----- comptage (API directe) ----------------------------------------------

    def count(self, query: SearchQuery) -> int:
        """Nombre total d'annonces (via ``christie/count``)."""
        data = self._client.post_christie_count(query.to_christie_body())
        return int(data.get("nb", 0))

    def count_breakdown(self, query: SearchQuery) -> dict:
        """Réponse brute de ``christie/count`` (nb + agrégations vendeur)."""
        return self._client.post_christie_count(query.to_christie_body())

    # ----- annonces (SSR) ------------------------------------------------------

    def get_listing(self, url_or_listing: "str | Listing") -> ListingDetail:
        """Récupère le **détail complet** d'une annonce (description, critères,
        DPE, transports, toutes les photos, contact agence…).

        Args:
            url_or_listing: l'URL de l'annonce (``Listing.url`` / ``classifiedURL``)
                ou directement un :class:`~seloger.models.Listing`.

        Note: optimisé pour les annonces ``seloger.com``. Les annonces pointant
        vers un site sœur (ex. bellesdemeures.com) peuvent ne pas être supportées.
        """
        url = url_or_listing.url if isinstance(url_or_listing, Listing) else url_or_listing
        if not url:
            raise ValueError("URL d'annonce manquante.")
        html = self._client.get_detail_html(url)
        detail = parse_listing_detail(html, url=url)
        logger.info("Détail %s : %s (%s)", detail.legacy_id or detail.id, detail.title, detail.city)
        return detail

    def search_page(self, query: SearchQuery, page: int = 1) -> SearchPage:
        """Récupère et parse une page de résultats."""
        html = self._client.get_list_html(query.to_querystring(page=page))
        result = parse_search_page(html)
        logger.info(
            "Page %d : %d annonces (total %d)",
            page,
            len(result.listings),
            result.total_count,
        )
        return result

    def iter_listings(
        self, query: SearchQuery, max_pages: int | None = None
    ) -> Iterator[Listing]:
        """Itère sur les annonces, page par page, en respectant le plafond SeLoger.

        Args:
            query: critères de recherche.
            max_pages: limite optionnelle de pages (sinon jusqu'au bout ou au cap).

        Yields:
            Les :class:`Listing` dédupliquées par ``id``.
        """
        first = self.search_page(query, page=1)
        seen: set[int] = set()

        def emit(page: SearchPage) -> Iterator[Listing]:
            for listing in page.listings:
                if listing.id not in seen:
                    seen.add(listing.id)
                    yield listing

        yield from emit(first)

        per_page = first.pagination.results_per_page or 25
        reachable = min(first.total_count, first.pagination.max_results or HARD_RESULT_CAP)
        last_page = math.ceil(reachable / per_page) if per_page else 1
        if max_pages is not None:
            last_page = min(last_page, max_pages)

        for page_num in range(2, last_page + 1):
            yield from emit(self.search_page(query, page=page_num))

        if first.total_count > HARD_RESULT_CAP:
            logger.warning(
                "%d annonces au total mais SeLoger plafonne à %d : affine les filtres "
                "(prix, surface, arrondissement) pour tout couvrir.",
                first.total_count,
                HARD_RESULT_CAP,
            )
