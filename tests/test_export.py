"""Tests de sérialisation JSON / NDJSON / CSV."""

from __future__ import annotations

import csv
import io
import json

import pytest

from seloger.export import serialize
from seloger.models import Listing

CARDS = [
    {"id": 1, "cardType": "classified", "pricing": {"rawPrice": "500"}, "surface": 25,
     "cityLabel": "Lyon 3ème", "tags": ["2 pièces"], "photos": ["/a.jpg"]},
    {"id": 2, "cardType": "classified", "pricing": {"rawPrice": "750"}, "surface": 40},
]


@pytest.fixture
def listings() -> list[Listing]:
    return [Listing.from_card(c) for c in CARDS]


def test_json(listings):
    data = json.loads(serialize(listings, "json"))
    assert [d["id"] for d in data] == [1, 2]
    assert data[0]["price"] == 500


def test_ndjson(listings):
    lines = serialize(listings, "ndjson").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["surface"] == 40


def test_csv(listings):
    rows = list(csv.DictReader(io.StringIO(serialize(listings, "csv"))))
    assert len(rows) == 2
    assert rows[0]["id"] == "1"
    assert rows[0]["surface"] == "25"
    assert "photos" not in rows[0]          # listes exclues du CSV plat


def test_unknown_format_raises(listings):
    with pytest.raises(ValueError):
        serialize(listings, "xml")
