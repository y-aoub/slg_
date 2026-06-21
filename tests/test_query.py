"""Tests de sérialisation des requêtes (querystring + body christie)."""

from __future__ import annotations

from urllib.parse import parse_qs

from seloger.enums import EstateType, ProjectType
from seloger.query import Range, SearchQuery


def test_querystring_verified_params():
    q = SearchQuery(
        project=ProjectType.RENT,
        estate_types=[EstateType.APARTMENT, EstateType.HOUSE],
        insee_codes=[750056],
    )
    qs = parse_qs(q.to_querystring(page=1))
    assert qs["projects"] == ["1"]
    assert qs["types"] == ["1,2"]
    assert qs["places"] == ['[{"inseeCodes":[750056]}]']
    assert qs["enterprise"] == ["0"]
    assert "LISTING-LISTpg" not in qs           # page 1 -> pas de param


def test_querystring_pagination_and_ranges():
    q = SearchQuery(insee_codes=[690123], price=Range(max=2000), surface=Range(min=20))
    qs = q.to_querystring(page=3)
    assert "LISTING-LISTpg=3" in qs
    assert "price=NaN/2000" in qs                # / non encodé
    assert "surface=20/NaN" in qs


def test_christie_body():
    q = SearchQuery(
        project=ProjectType.BUY,
        estate_types=[EstateType.APARTMENT],
        insee_codes=[330063],
        price=Range(100000, 300000),
        rooms_min=3,
    )
    body = q.to_christie_body()
    assert body["projects"] == [2]
    assert body["types"] == [1]
    assert body["places"] == [{"inseeCodes": [330063]}]
    assert body["price"] == {"min": 100000, "max": 300000}
    assert body["rooms"] == [3, 4, 5]            # min étendu jusqu'au palier 5+
    assert body["enterprise"] is False


def test_rooms_buckets_querystring_and_cap():
    # min=3 -> [3,4,5] ; min>=5 -> [5] (palier ouvert "5 et plus")
    assert "rooms=3,4,5" in SearchQuery(insee_codes=[1], rooms_min=3).to_querystring()
    assert "rooms=5" in SearchQuery(insee_codes=[1], rooms_min=7).to_querystring()
    assert SearchQuery(insee_codes=[1], bedrooms_min=2).to_christie_body()["bedrooms"] == [2, 3, 4, 5]
