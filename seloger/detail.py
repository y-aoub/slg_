"""Modèle et parsing du **détail** d'une annonce SeLoger.

La page de détail (``/annonces/.../<id>.htm``) est rendue côté serveur par le
framework « UFRN » et embarque tout l'état dans :

    <script>window["__UFRN_LIFECYCLE_SERVERREQUEST__"] = JSON.parse("<JSON doublement encodé>")</script>

L'annonce complète se trouve sous ``app_cldp.data.classified``. Le parsing est
défensif (le schéma varie selon le type de bien et la business unit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import _to_int


def _to_float(value: Any) -> float | None:
    """Parse un nombre français : « 115,9 » → 115.9, « 1 159,5 » → 1159.5."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = (
            value.replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
        )
        cleaned = "".join(ch for ch in cleaned if ch in "0123456789.")
        try:
            return float(cleaned) if cleaned and cleaned != "." else None
        except ValueError:
            return None
    return None


# Types hardFacts.facts[] traités comme des entiers (via splitValue).
_INT_FACT_TYPES = {
    "numberOfRooms": "rooms",
    "numberOfBedrooms": "bedrooms",
}


@dataclass(slots=True)
class DetailContact:
    name: str | None = None
    subtitle: str | None = None
    is_private: bool = False
    phones: list[str] = field(default_factory=list)
    logo_url: str | None = None
    agency_id: str | None = None

    @classmethod
    def from_sections(cls, contact_sections: dict | None) -> "DetailContact":
        cs = contact_sections or {}
        card = cs.get("contactCard") or cs.get("mobilePhones") or {}
        logo = card.get("agencyLogo") or {}
        return cls(
            name=card.get("title"),
            subtitle=card.get("subtitle"),
            is_private=bool(card.get("isPrivateOwner", False)),
            phones=list(card.get("phoneNumbers") or []),
            logo_url=logo.get("logoUrl") or card.get("logoUrl"),
            agency_id=cs.get("agencyId"),
        )


@dataclass(slots=True)
class ListingDetail:
    """Détail complet d'une annonce SeLoger."""

    id: str
    legacy_id: int | None = None
    url: str | None = None
    title: str | None = None
    headline: str | None = None
    description: str | None = None
    distribution_type: str | None = None   # RENT / SALE
    property_type: str | None = None       # APARTMENT / HOUSE ...
    creation_date: str | None = None
    update_date: str | None = None
    is_active: bool | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    surface: float | None = None   # m² (peut être décimal, ex. 115.9)
    floor: str | None = None       # « étage/total », ex. "4/6"
    keyfacts: list[str] = field(default_factory=list)
    prices: dict[str, str] = field(default_factory=dict)   # libellé -> valeur
    epc: str | None = None                                  # DPE (lettre)
    energy: list[dict] = field(default_factory=list)        # [{label, value}]
    city: str | None = None
    zip_code: str | None = None
    district: str | None = None
    lat: float | None = None
    lng: float | None = None
    transport: list[dict] = field(default_factory=list)     # [{type, lines:[...]}]
    features: list[dict] = field(default_factory=list)      # [{icon, value}]
    photos: list[str] = field(default_factory=list)
    floorplans: list[str] = field(default_factory=list)
    virtual_tours: list[str] = field(default_factory=list)
    contact: DetailContact = field(default_factory=DetailContact)
    is_exclusive: bool = False
    has_3d_visit: bool = False
    has_brokerage_fee: bool = False
    is_new: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_classified(cls, c: dict) -> "ListingDetail":
        sections = c.get("sections") or {}
        meta = c.get("metadata") or {}
        raw_data = c.get("rawData") or {}
        tags = c.get("tags") or {}

        detail = cls(
            id=str(c.get("id")),
            legacy_id=_to_int(meta.get("legacyId")),
            title=(sections.get("hardFacts") or {}).get("title"),
            distribution_type=raw_data.get("distributionType"),
            property_type=raw_data.get("propertyType"),
            creation_date=meta.get("creationDate"),
            update_date=meta.get("updateDate"),
            is_active=bool((meta.get("status") or {}).get("status")) if meta.get("status") else None,
            epc=(c.get("tracking") or {}).get("av_energy_certificate"),
            is_exclusive=bool(tags.get("isExclusive", False)),
            has_3d_visit=bool(tags.get("has3DVisit", False)),
            has_brokerage_fee=bool(tags.get("hasBrokerageFee", False)),
            is_new=bool(tags.get("isNew", False)),
            contact=DetailContact.from_sections(c.get("contactSections")),
            raw=c,
        )
        detail._fill_description(sections.get("mainDescription"))
        detail._fill_hardfacts(sections.get("hardFacts"))
        detail._fill_prices(sections.get("price"))
        detail._fill_energy(sections.get("energy"))
        detail._fill_location(sections.get("location"))
        detail._fill_features(sections.get("features"))
        detail._fill_medias(c.get("domains"))
        return detail

    # ----- remplisseurs internes ----------------------------------------------

    def _fill_description(self, main_desc: dict | None) -> None:
        md = main_desc or {}
        self.headline = md.get("headline")
        self.description = md.get("description")

    def _fill_hardfacts(self, hard_facts: dict | None) -> None:
        hf = hard_facts or {}
        self.keyfacts = list(hf.get("keyfacts") or [])
        for fact in hf.get("facts") or []:
            ftype = fact.get("type")
            split = fact.get("splitValue")
            if ftype in _INT_FACT_TYPES:
                setattr(self, _INT_FACT_TYPES[ftype], _to_int(split or fact.get("value")))
            elif ftype == "livingSpace":
                self.surface = _to_float(split or fact.get("value"))
            elif ftype == "numberOfFloors":
                # splitValue vaut "Étage" ; l'info utile (« 4/6 ») est dans label.
                self.floor = fact.get("label") or fact.get("value")

    def _fill_prices(self, price: dict | None) -> None:
        details = ((price or {}).get("base") or {}).get("details") or []
        for item in details:
            label = (item.get("label") or {}).get("main")
            value = ((item.get("value") or {}).get("main") or {}).get("value")
            if label and value:
                self.prices[label] = value

    def _fill_energy(self, energy: dict | None) -> None:
        e = energy or {}
        for feat in e.get("features") or []:
            if feat.get("label") and feat.get("value"):
                self.energy.append({"label": feat["label"], "value": feat["value"]})
        for cert in e.get("certificates") or []:
            for feat in cert.get("features") or []:
                if feat.get("type") == "minMaxEstimation" and feat.get("value"):
                    self.energy.append({"label": feat.get("label"), "value": feat["value"]})

    def _fill_location(self, location: dict | None) -> None:
        loc = location or {}
        addr = loc.get("address") or {}
        self.city = addr.get("city")
        self.zip_code = addr.get("zipCode")
        self.district = addr.get("district")
        coords = (loc.get("geometry") or {}).get("coordinates") or []
        if len(coords) == 2:  # SeLoger renvoie [lng, lat]
            self.lng, self.lat = coords[0], coords[1]
        for line_group in (loc.get("transport") or {}).get("closestLines") or []:
            self.transport.append({
                "type": line_group.get("type"),
                "lines": [ln.get("name") for ln in line_group.get("lines") or []],
            })

    def _fill_features(self, features: dict | None) -> None:
        for item in (features or {}).get("preview") or []:
            if item.get("value"):
                self.features.append({"icon": item.get("icon"), "value": item["value"]})

    def _fill_medias(self, domains: dict | None) -> None:
        medias = (domains or {}).get("medias") or {}
        self.photos = [m.get("url") for m in medias.get("images") or [] if m.get("url")]
        self.floorplans = [m.get("url") for m in medias.get("floorplans") or [] if m.get("url")]
        self.virtual_tours = [
            m.get("url") or m.get("link")
            for m in medias.get("virtualTours") or []
            if (m.get("url") or m.get("link"))
        ]

    # ----- sérialisation -------------------------------------------------------

    def to_dict(self, *, include_raw: bool = False) -> dict:
        return {
            "id": self.id,
            "legacy_id": self.legacy_id,
            "url": self.url,
            "title": self.title,
            "headline": self.headline,
            "description": self.description,
            "distribution_type": self.distribution_type,
            "property_type": self.property_type,
            "creation_date": self.creation_date,
            "update_date": self.update_date,
            "is_active": self.is_active,
            "rooms": self.rooms,
            "bedrooms": self.bedrooms,
            "surface": self.surface,
            "floor": self.floor,
            "keyfacts": self.keyfacts,
            "prices": self.prices,
            "epc": self.epc,
            "energy": self.energy,
            "city": self.city,
            "zip_code": self.zip_code,
            "district": self.district,
            "lat": self.lat,
            "lng": self.lng,
            "transport": self.transport,
            "features": self.features,
            "photos": self.photos,
            "floorplans": self.floorplans,
            "virtual_tours": self.virtual_tours,
            "contact_name": self.contact.name,
            "contact_phones": self.contact.phones,
            "is_private_seller": self.contact.is_private,
            "is_exclusive": self.is_exclusive,
            "has_3d_visit": self.has_3d_visit,
            "has_brokerage_fee": self.has_brokerage_fee,
            "is_new": self.is_new,
            **({"raw": self.raw} if include_raw else {}),
        }
