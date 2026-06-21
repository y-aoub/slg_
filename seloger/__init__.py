"""Scraper SeLoger — récupération d'annonces immobilières via SSR + API christie.

Exemple :

    from seloger import SelogerScraper, ScraperConfig, SearchQuery
    from seloger.enums import ProjectType

    config = ScraperConfig(datadome_cookie="...")  # ou env SELOGER_DATADOME
    query = SearchQuery(project=ProjectType.RENT, insee_codes=[750056])

    with SelogerScraper(config) as scraper:
        print(scraper.count(query))
        for listing in scraper.iter_listings(query, max_pages=3):
            print(listing.id, listing.city, listing.pricing.display_price)
"""

from __future__ import annotations

from .aclient import AsyncSelogerClient
from .ascraper import AsyncSelogerScraper
from .config import ScraperConfig
from .detail import DetailContact, ListingDetail
from .exceptions import (
    DatadomeBlocked,
    ListingUnavailable,
    ParseError,
    RateLimited,
    SelogerError,
)
from .geocoding import Place, geocode, resolve_insee, resolve_place_ids
from .models import Contact, Listing, Pricing, SearchPage
from .proxy import Proxy
from .query import Range, SearchQuery
from .scraper import SelogerScraper

__version__ = "0.1.0"

__all__ = [
    "SelogerScraper",
    "AsyncSelogerScraper",
    "AsyncSelogerClient",
    "ScraperConfig",
    "SearchQuery",
    "Range",
    "Proxy",
    "geocode",
    "resolve_insee",
    "resolve_place_ids",
    "Place",
    "Listing",
    "ListingDetail",
    "DetailContact",
    "Pricing",
    "Contact",
    "SearchPage",
    "SelogerError",
    "DatadomeBlocked",
    "ListingUnavailable",
    "ParseError",
    "RateLimited",
    "__version__",
]
