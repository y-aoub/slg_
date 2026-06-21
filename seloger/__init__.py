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

from .config import ScraperConfig
from .exceptions import (
    DatadomeBlocked,
    ParseError,
    RateLimited,
    SelogerError,
)
from .geocoding import Place, geocode, resolve_insee
from .models import Contact, Listing, Pricing, SearchPage
from .proxy import Proxy
from .query import Range, SearchQuery
from .scraper import SelogerScraper

__version__ = "0.1.0"

__all__ = [
    "SelogerScraper",
    "ScraperConfig",
    "SearchQuery",
    "Range",
    "Proxy",
    "geocode",
    "resolve_insee",
    "Place",
    "Listing",
    "Pricing",
    "Contact",
    "SearchPage",
    "SelogerError",
    "DatadomeBlocked",
    "ParseError",
    "RateLimited",
    "__version__",
]
