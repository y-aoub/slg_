"""Tests des modèles (parsing défensif)."""

from __future__ import annotations

from seloger.models import Listing, Position, _to_int


def test_to_int_handles_strings_and_units():
    assert _to_int("7 980") == 7980
    assert _to_int("281 m²") == 281
    assert _to_int(42) == 42
    assert _to_int(None) is None
    assert _to_int("") is None
    assert _to_int(True) is None        # bool n'est pas un nombre exploitable


def test_position_from_value():
    assert Position.from_value(0) is None
    assert Position.from_value({"lat": 48.85, "lng": 2.35}) == Position(48.85, 2.35)
    assert Position.from_value({}) is None


def test_listing_from_card_minimal():
    listing = Listing.from_card({"id": 5, "cardType": "classified"})
    assert listing.id == 5
    assert listing.surface is None
    assert listing.photo_urls() == []
    assert listing.to_dict()["id"] == 5


def test_listing_to_dict_shape():
    card = {
        "id": 9,
        "cardType": "classified",
        "pricing": {"rawPrice": "500", "price": "500 €"},
        "surface": 25,
        "position": {"lat": 1.0, "lng": 2.0},
        "photos": ["/x.jpg"],
    }
    d = Listing.from_card(card).to_dict()
    assert d["price"] == 500
    assert d["surface"] == 25
    assert d["lat"] == 1.0 and d["lng"] == 2.0
    assert d["photos"][0].endswith("/x.jpg")
    assert "raw" not in d                 # exclu par défaut
