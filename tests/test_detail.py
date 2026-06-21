"""Tests du parsing du détail d'une annonce (page UFRN)."""

from __future__ import annotations

import json

import pytest

from seloger.detail import ListingDetail, _to_float
from seloger.exceptions import ParseError
from seloger.parser import extract_detail_data, parse_listing_detail

CLASSIFIED = {
    "id": "ABC123",
    "brand": "seloger",
    "metadata": {"legacyId": "211815093", "creationDate": "2023-11-29T15:36:00Z",
                 "status": {"status": True}},
    "rawData": {"distributionType": "RENT", "propertyType": "APARTMENT"},
    "tags": {"isExclusive": True, "has3DVisit": True, "hasBrokerageFee": False, "isNew": True},
    "tracking": {"av_energy_certificate": "F"},
    "sections": {
        "hardFacts": {
            "title": "Appartement à louer",
            "keyfacts": ["2 pièces", "1 chambre", "115,9 m²", "Étage 4/6"],
            "facts": [
                {"type": "numberOfRooms", "splitValue": "2", "value": "2 pièces"},
                {"type": "numberOfBedrooms", "splitValue": "1", "value": "1 chambre"},
                {"type": "livingSpace", "splitValue": "115,9", "value": "115,9 m²"},
                {"type": "numberOfFloors", "splitValue": "Étage", "label": "4/6", "value": "Étage 4/6"},
            ],
        },
        "mainDescription": {"headline": "Montmartre", "description": "Splendide appartement."},
        "price": {"base": {"details": [
            {"label": {"main": "Loyer charges comprises"}, "value": {"main": {"value": "2 895 €/mois"}}},
        ]}},
        "energy": {"features": [{"type": "heatingSystem", "label": "Chauffage", "value": "Radiateur"}],
                   "certificates": []},
        "location": {"address": {"city": "Paris 18ème", "zipCode": "75018", "district": "Montmartre"},
                     "geometry": {"coordinates": [2.3339, 48.8906]},
                     "transport": {"closestLines": [{"type": "METRO", "lines": [{"name": "12"}, {"name": "13"}]}]}},
        "features": {"preview": [{"icon": "elevator", "value": "Pas d'ascenseur"}]},
    },
    "domains": {"medias": {"images": [{"url": "https://mms.seloger.com/a.jpg"},
                                      {"url": "https://mms.seloger.com/b.jpg"}],
                           "virtualTours": [{"url": "https://tour/x"}]}},
    "contactSections": {"agencyId": "RC-1", "contactCard": {
        "title": "UKIO FRANCE", "isPrivateOwner": False, "phoneNumbers": ["+33(0)757902019"],
        "agencyLogo": {"logoUrl": "https://logo.jpg"}}},
}


def _make_detail_html(classified: dict) -> str:
    payload = {"app_cldp": {"data": {"classified": classified}}}
    literal = json.dumps(json.dumps(payload))
    return f'<script>window["__UFRN_LIFECYCLE_SERVERREQUEST__"] = JSON.parse({literal})</script>'


def test_to_float_french_numbers():
    assert _to_float("115,9") == 115.9
    assert _to_float("1 159,5") == 1159.5
    assert _to_float("55") == 55.0
    assert _to_float(None) is None


def test_extract_and_parse_detail():
    detail = parse_listing_detail(_make_detail_html(CLASSIFIED), url="https://x/211815093.htm")
    assert detail.id == "ABC123"
    assert detail.legacy_id == 211815093
    assert detail.url.endswith("211815093.htm")
    assert detail.distribution_type == "RENT"
    assert detail.rooms == 2 and detail.bedrooms == 1
    assert detail.surface == 115.9              # décimale conservée
    assert detail.floor == "4/6"                # composé conservé en str
    assert detail.epc == "F"
    assert detail.description == "Splendide appartement."
    assert detail.prices["Loyer charges comprises"] == "2 895 €/mois"
    assert detail.city == "Paris 18ème" and detail.zip_code == "75018"
    assert (detail.lat, detail.lng) == (48.8906, 2.3339)   # [lng, lat] -> lat, lng
    assert detail.transport[0] == {"type": "METRO", "lines": ["12", "13"]}
    assert detail.photos == ["https://mms.seloger.com/a.jpg", "https://mms.seloger.com/b.jpg"]
    assert detail.virtual_tours == ["https://tour/x"]
    assert detail.contact.name == "UKIO FRANCE"
    assert detail.contact.phones == ["+33(0)757902019"]
    assert detail.is_exclusive and detail.has_3d_visit and detail.is_new


def test_detail_to_dict():
    d = ListingDetail.from_classified(CLASSIFIED).to_dict()
    assert d["legacy_id"] == 211815093
    assert d["contact_phones"] == ["+33(0)757902019"]
    assert "raw" not in d


def test_missing_marker_raises():
    with pytest.raises(ParseError):
        extract_detail_data("<html>no marker</html>")


def test_unavailable_listing_raises():
    html = _make_detail_html(None)  # classified absent -> error
    with pytest.raises(ParseError):
        extract_detail_data(html)
