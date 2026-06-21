"""Sérialisation des annonces vers JSON / NDJSON / CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable

from .models import Listing

# Colonnes plates exportées en CSV (les listes sont jointes par « | »).
_CSV_COLUMNS = [
    "id", "estate_type", "transaction_type_id", "price", "price_note",
    "surface", "rooms", "bedrooms", "epc", "city", "district", "zip_code",
    "lat", "lng", "contact_name", "contact_phone", "is_private_seller",
    "is_new", "is_exclusive", "url",
]


def to_json(listings: Iterable[Listing], *, include_raw: bool = False) -> str:
    return json.dumps(
        [l.to_dict(include_raw=include_raw) for l in listings],
        ensure_ascii=False,
        indent=2,
    )


def to_ndjson(listings: Iterable[Listing], *, include_raw: bool = False) -> str:
    """Une annonce JSON par ligne (pratique pour le streaming / big data)."""
    return "\n".join(
        json.dumps(l.to_dict(include_raw=include_raw), ensure_ascii=False)
        for l in listings
    )


def to_csv(listings: Iterable[Listing]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for listing in listings:
        writer.writerow(listing.to_dict())
    return buffer.getvalue()


def serialize(listings: Iterable[Listing], fmt: str, *, include_raw: bool = False) -> str:
    """Sérialise selon ``fmt`` ∈ {``json``, ``ndjson``, ``csv``}."""
    listings = list(listings)
    if fmt == "json":
        return to_json(listings, include_raw=include_raw)
    if fmt == "ndjson":
        return to_ndjson(listings, include_raw=include_raw)
    if fmt == "csv":
        return to_csv(listings)
    raise ValueError(f"Format inconnu : {fmt!r} (json|ndjson|csv)")
