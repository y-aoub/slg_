"""Tests du parser SSR (extraction de window["initialData"])."""

from __future__ import annotations

import json

import pytest

from seloger.exceptions import ParseError
from seloger.parser import extract_initial_data, parse_search_page


def _make_html(data: dict) -> str:
    """Reproduit l'embedding SSR : double encodage JSON dans JSON.parse(...)."""
    inner = json.dumps(data)            # objet -> texte JSON
    literal = json.dumps(inner)         # texte JSON -> littéral chaîne JS
    return (
        "<html><body><div>...</div>"
        f'<script>window["initialData"] = JSON.parse({literal})</script>'
        "</body></html>"
    )


@pytest.fixture
def sample_data() -> dict:
    return {
        "cards": {
            "list": [
                {
                    "id": 111,
                    "cardType": "classified",
                    "title": "Appartement",
                    "estateType": "Appartement",
                    "estateTypeId": 1,
                    "transactionTypeId": 1,
                    "pricing": {"rawPrice": "1 400", "price": "1 400 €", "priceNote": "cc"},
                    "contact": {"contactName": "AGENCE X", "phoneNumber": "06 00", "isPrivateSeller": False},
                    "cityLabel": "Paris 11ème",
                    "zipCode": "75011",
                    "rooms": 2,
                    "surface": 31,
                    "bedroomCount": 1,
                    "epc": "F",
                    "photos": ["/a/b/c.jpg"],
                    "tags": ["2 pièces"],
                    "position": 0,
                    "classifiedURL": "https://www.seloger.com/annonces/111",
                },
                {"id": "native1", "cardType": "native"},          # pub -> filtrée
                {"id": 222, "cardType": "classified", "title": "Maison", "estateTypeId": 2},
            ]
        },
        "navigation": {
            "pagination": {"page": 1, "resultsPerPage": 25, "maxResults": 2500},
            "counts": {"count": 42, "aggregations": {"privateSeller": 5, "professionalSeller": 37}},
        },
    }


def test_extract_initial_data_roundtrip(sample_data):
    html = _make_html(sample_data)
    data = extract_initial_data(html)
    assert data["navigation"]["counts"]["count"] == 42


def test_parse_filters_ads_and_reads_fields(sample_data):
    page = parse_search_page(_make_html(sample_data))
    assert page.total_count == 42
    assert page.private_seller_count == 5
    assert page.pagination.max_results == 2500
    # la carte pub "native1" est filtrée -> 2 annonces réelles
    assert [l.id for l in page.listings] == [111, 222]

    first = page.listings[0]
    assert first.pricing.raw_price == 1400          # "1 400" -> int
    assert first.pricing.price_note == "cc"
    assert first.surface == 31 and first.rooms == 2 and first.bedrooms == 1
    assert first.epc == "F"
    assert first.contact.name == "AGENCE X"
    assert first.position is None                    # 0 -> None
    assert first.photo_urls()[0].endswith("/a/b/c.jpg")


def test_missing_initial_data_raises():
    with pytest.raises(ParseError):
        extract_initial_data("<html>challenge datadome</html>")


def test_parse_externaldata():
    from seloger.parser import parse_externaldata

    data = {
        "listingData": {
            "count": 5917,
            "cards": [
                {"type": 0, "listing": {"id": 111, "title": "Appartement", "surface": 31,
                                        "pricing": {"rawPrice": "1400"}}},
                {"type": 5, "nativeAdvertising": {"highlightingLevel": 2}},  # pub -> ignorée
                {"type": 0, "listing": {"id": 222, "title": "Studio"}},
            ],
        }
    }
    listings, count = parse_externaldata(data)
    assert count == 5917
    assert [l.id for l in listings] == [111, 222]      # la pub est filtrée
    assert listings[0].pricing.raw_price == 1400
